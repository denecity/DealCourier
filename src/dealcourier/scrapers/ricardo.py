"""Ricardo.ch scraper using their public JSON search API."""

import logging
from datetime import datetime, timezone
from urllib.parse import quote

import httpx

from dealcourier.scrapers.base import BaseScraper, RawListing

logger = logging.getLogger("dealcourier.scrapers.ricardo")

RICARDO_API_URL = "https://www.ricardo.ch/api/mfa/search"


class RicardoScraper(BaseScraper):
    platform = "ricardo"

    def __init__(self, timeout: int = 30, delay: float = 1.0):
        from dealcourier.config import get_config
        cfg = get_config()
        self.timeout = timeout
        self.delay = cfg.ricardo_delay_seconds
        self.max_terms = cfg.ricardo_max_terms
        self.auction_max_hours = cfg.ricardo_auction_max_hours
        self.include_auctions = cfg.ricardo_include_auctions
        self.include_buy_now = cfg.ricardo_include_buy_now
        self._client = httpx.Client(
            timeout=timeout,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json",
                "Accept-Language": "de-CH,de;q=0.9",
                "Referer": "https://www.ricardo.ch/",
            },
            follow_redirects=True,
        )

    def search(self, term: str) -> list[RawListing]:
        encoded = quote(term)
        url = f"{RICARDO_API_URL}/{encoded}"

        try:
            response = self._client.get(url)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPError as e:
            logger.warning(f"Ricardo API error for '{term}': {e}")
            return []
        except Exception as e:
            logger.warning(f"Ricardo parse error for '{term}': {e}")
            return []

        articles = data.get("articles", [])
        if not isinstance(articles, list):
            logger.warning(f"No articles array in Ricardo response for '{term}'")
            return []

        results = []
        skipped_auctions = 0
        for article in articles:
            listing = self._parse_article(article)
            if listing is None and article.get("hasAuction"):
                skipped_auctions += 1
            if listing is not None:
                results.append(listing)

        if skipped_auctions:
            logger.info(f"Ricardo '{term}': skipped {skipped_auctions} auctions not ending soon")

        return results

    def _parse_article(self, article: dict) -> RawListing | None:
        try:
            article_id = str(article.get("id", ""))
            if not article_id:
                return None

            title = article.get("title", "")
            if not title:
                return None

            # --- Auction / Buy-now filtering ---
            is_auction = article.get("hasAuction", False)
            has_buy_now = article.get("hasBuyNow", False)

            # Skip buy-now-only if disabled
            if has_buy_now and not is_auction and not self.include_buy_now:
                return None

            auction_end_at: datetime | None = None

            # Handle auctions
            if is_auction:
                if not self.include_auctions and not has_buy_now:
                    return None

                # Parse end date for any auction (used for auction_end_at and filtering)
                end_date_str = article.get("endDate")
                parsed_end: datetime | None = None
                if end_date_str:
                    try:
                        parsed_end = datetime.fromisoformat(
                            end_date_str.replace("Z", "+00:00")
                        )
                    except (ValueError, TypeError):
                        parsed_end = None

                # Auction-only (no buy-now): check end time
                if not has_buy_now:
                    if parsed_end is None:
                        return None
                    now = datetime.now(timezone.utc)
                    hours_left = (parsed_end - now).total_seconds() / 3600
                    if hours_left > self.auction_max_hours:
                        return None

                if parsed_end is not None:
                    # Store as naive UTC (DB column is DATETIME without tz)
                    auction_end_at = parsed_end.astimezone(timezone.utc).replace(tzinfo=None)

            # Price: prefer buyNowPrice, fall back to bidPrice for near-ending auctions
            price = None
            buy_now = article.get("buyNowPrice")
            bid = article.get("bidPrice")
            if buy_now is not None:
                try:
                    price = int(float(buy_now))
                except (ValueError, TypeError):
                    pass
            if price is None and bid is not None:
                try:
                    price = int(float(bid))
                except (ValueError, TypeError):
                    pass

            if not price or price <= 0:
                return None

            # Image
            image_url = article.get("image")

            # Location from shipping info
            location = None
            postcode = None
            shipping = article.get("shipping")
            if isinstance(shipping, list) and shipping:
                ship = shipping[0]
                location = ship.get("city", "")
                postcode = str(ship.get("zipCode", "")) if ship.get("zipCode") else None

            # Build URL
            url = f"https://www.ricardo.ch/de/a/{article_id}"

            # Seller
            seller_id = article.get("sellerId")
            seller_name = str(seller_id) if seller_id else None

            return RawListing(
                platform="ricardo",
                platform_id=article_id,
                title=title,
                description="",
                price=price,
                url=url,
                image_url=image_url,
                seller_name=seller_name,
                postcode=postcode,
                location=location or None,
                auction_end_at=auction_end_at,
            )
        except Exception as e:
            logger.debug(f"Failed to parse Ricardo article: {e}")
            return None
