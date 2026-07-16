"""APScheduler-based job runner for scrape/evaluate cycles."""

import logging
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import select

from dealcourier.ai.evaluator import (
    evaluate_listings,
    generate_search_terms,
)
from dealcourier.config import get_config
from dealcourier.db.engine import get_session
from dealcourier.db.models import Listing, ScrapeRun, SearchItem, Setting
from dealcourier.distance import distance_from_zurich
from dealcourier.notifications.discord import send_notifications_for_passed
from dealcourier.scrapers.anibis import AnibisScraper
from dealcourier.scrapers.base import BaseScraper
from dealcourier.scrapers.ricardo import RicardoScraper
from dealcourier.scrapers.tutti import TuttiScraper

logger = logging.getLogger("dealcourier.scheduler")

_scheduler: BackgroundScheduler | None = None

SCRAPERS: dict[str, type[BaseScraper]] = {
    "tutti": TuttiScraper,
    "ricardo": RicardoScraper,
    "anibis": AnibisScraper,
}

SCRAPE_INTERVAL_KEY = "scrape_interval_minutes"


def _read_persisted_interval() -> int | None:
    """Return the persisted scrape interval in minutes, or None if unset."""
    session = get_session()
    try:
        row = session.get(Setting, SCRAPE_INTERVAL_KEY)
        if row is None:
            return None
        try:
            val = int(row.value)
            return val if val > 0 else None
        except (ValueError, TypeError):
            return None
    finally:
        session.close()


def _persist_interval(minutes: int) -> None:
    """Save the scrape interval to the settings table."""
    session = get_session()
    try:
        row = session.get(Setting, SCRAPE_INTERVAL_KEY)
        if row is None:
            session.add(Setting(key=SCRAPE_INTERVAL_KEY, value=str(minutes)))
        else:
            row.value = str(minutes)
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to persist scrape interval: {e}")
    finally:
        session.close()


def get_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler()
    return _scheduler


def start_scheduler() -> None:
    """Start the scheduler with default jobs.

    Prefers a persisted scrape interval (set via the UI) over the config default,
    so restarts keep the user's chosen cadence.
    """
    cfg = get_config()
    scheduler = get_scheduler()

    persisted = _read_persisted_interval()
    scrape_minutes = persisted if persisted is not None else cfg.scrape_interval_minutes
    source = "persisted" if persisted is not None else "config"

    scheduler.add_job(
        run_scrape_cycle,
        "interval",
        minutes=scrape_minutes,
        id="scrape_cycle",
        replace_existing=True,
        next_run_time=None,  # Don't run immediately on start
        misfire_grace_time=300,  # Still fire if up to 5 min late
    )

    scheduler.add_job(
        regenerate_all_terms,
        "interval",
        hours=cfg.term_regeneration_interval_hours,
        id="term_regeneration",
        replace_existing=True,
        next_run_time=None,
        misfire_grace_time=300,
    )

    scheduler.start()
    logger.info(
        f"Scheduler started. Scrape interval: {scrape_minutes}m ({source}), "
        f"Term regen: every {cfg.term_regeneration_interval_hours}h"
    )


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped")


def get_scheduler_status() -> dict:
    """Get current scheduler status."""
    scheduler = get_scheduler()
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
        })

    return {
        "running": scheduler.running,
        "jobs": jobs,
    }


def update_scrape_interval(minutes: int) -> None:
    """Update the scrape interval and persist it across restarts."""
    scheduler = get_scheduler()
    scheduler.reschedule_job("scrape_cycle", trigger="interval", minutes=minutes)
    _persist_interval(minutes)
    logger.info(f"Scrape interval updated to {minutes} minutes (persisted)")


def trigger_scrape_now() -> None:
    """Trigger an immediate scrape run (runs in scheduler thread)."""
    scheduler = get_scheduler()
    scheduler.add_job(
        run_scrape_cycle,
        id="manual_scrape",
        replace_existing=True,
    )
    logger.info("Manual scrape triggered")


def run_scrape_cycle() -> None:
    """Execute one full scrape -> evaluate -> filter -> notify cycle."""
    cfg = get_config()
    logger.info("=== Starting scrape cycle ===")

    session = get_session()
    try:
        search_items = session.execute(
            select(SearchItem).where(SearchItem.enabled == True)
        ).scalars().all()

        if not search_items:
            logger.info("No enabled search items. Skipping cycle.")
            return

        all_new_listing_ids: list[int] = []

        for search_item in search_items:
            run = ScrapeRun(
                search_item_id=search_item.id,
                started_at=datetime.utcnow(),
            )
            session.add(run)
            session.commit()

            try:
                new_ids = _scrape_search_item(session, search_item, run)
                all_new_listing_ids.extend(new_ids)

                run.finished_at = datetime.utcnow()
                run.status = "completed"
                session.commit()
            except Exception as e:
                run.finished_at = datetime.utcnow()
                run.status = "failed"
                run.error_message = str(e)
                session.commit()
                logger.error(f"Scrape failed for '{search_item.name}': {e}")

        # Evaluate all new listings
        if all_new_listing_ids:
            logger.info(f"Evaluating {len(all_new_listing_ids)} new listings")
            evaluated = evaluate_listings(all_new_listing_ids)
            sent = send_notifications_for_passed(all_new_listing_ids)
            logger.info(
                f"Cycle complete: {len(all_new_listing_ids)} new, "
                f"{evaluated} evaluated, {sent} notified"
            )
        else:
            logger.info("No new listings found this cycle")

    except Exception as e:
        logger.error(f"Scrape cycle failed: {e}")
    finally:
        session.close()

    logger.info("=== Scrape cycle finished ===")


def _scrape_search_item(
    session, search_item: SearchItem, run: ScrapeRun
) -> list[int]:
    """Scrape all platforms for a single search item. Returns new listing IDs."""
    cfg = get_config()

    # Regenerate search terms every cycle. The terms are cheap (single AI
    # call per search item) and fresh terms adapt to evolving listings;
    # the old cache path is kept only in the DB for display in the UI.
    terms = generate_search_terms(search_item)

    from dealcourier.web.routers.config import get_globally_enabled_shops

    all_platforms = search_item.platforms or ["tutti"]
    enabled_shops = get_globally_enabled_shops()
    platforms = [p for p in all_platforms if p in enabled_shops]

    if not platforms:
        logger.info(f"All platforms disabled for '{search_item.name}', skipping")
        return []

    new_ids: list[int] = []

    for platform_name in platforms:
        scraper_cls = SCRAPERS.get(platform_name)
        if scraper_cls is None:
            logger.warning(f"Unknown platform: {platform_name}")
            continue

        scraper = scraper_cls(
            timeout=cfg.request_timeout_seconds,
            delay=cfg.request_delay_seconds,
        )

        logger.info(
            f"Scraping {platform_name} for '{search_item.name}' "
            f"with {len(terms)} terms"
        )
        raw_listings = scraper.search_multiple(terms)
        run.listings_found = (run.listings_found or 0) + len(raw_listings)

        # Insert into DB, skip duplicates
        for raw in raw_listings:
            # Check if already exists
            existing = session.execute(
                select(Listing).where(
                    Listing.platform == raw.platform,
                    Listing.platform_id == raw.platform_id,
                )
            ).scalar_one_or_none()

            if existing:
                continue

            listing = Listing(
                platform=raw.platform,
                platform_id=raw.platform_id,
                search_item_id=search_item.id,
                title=raw.title,
                description=raw.description,
                category=raw.category,
                price=raw.price,
                currency=raw.currency,
                url=raw.url,
                image_url=raw.image_url,
                search_term=raw.platform,  # Could track which term found it
                seller_name=raw.seller_name,
                postcode=raw.postcode,
                location=raw.location,
                shipping_cost=raw.shipping_cost,
                distance_km=distance_from_zurich(raw.postcode),
                listed_at=raw.listed_at,
                auction_end_at=raw.auction_end_at,
                scraped_at=datetime.utcnow(),
            )
            session.add(listing)
            session.flush()  # Get the ID
            new_ids.append(listing.id)

        session.commit()
        run.listings_new = (run.listings_new or 0) + len(new_ids)

    logger.info(
        f"'{search_item.name}': {run.listings_found} found, {len(new_ids)} new"
    )
    return new_ids


def regenerate_all_terms() -> None:
    """Regenerate search terms for all enabled search items."""
    session = get_session()
    try:
        items = session.execute(
            select(SearchItem).where(SearchItem.enabled == True)
        ).scalars().all()

        for item in items:
            logger.info(f"Regenerating terms for '{item.name}'")
            generate_search_terms(item)

    except Exception as e:
        logger.error(f"Term regeneration failed: {e}")
    finally:
        session.close()
