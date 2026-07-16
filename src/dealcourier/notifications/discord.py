"""Discord webhook notifications."""

import logging
from datetime import datetime

from discord_webhook import DiscordWebhook, DiscordEmbed
from sqlalchemy import select

from dealcourier.config import get_config
from dealcourier.db.engine import get_session
from dealcourier.db.models import Listing

logger = logging.getLogger("dealcourier.notifications.discord")


def send_listing_notification(listing: Listing) -> bool:
    """Send a Discord notification for a single listing.

    Returns True if the notification was sent successfully.
    """
    cfg = get_config()
    if not cfg.discord_enabled:
        return False
    if not cfg.discord_webhook_url:
        logger.warning("Discord webhook URL not configured")
        return False

    # Config-based notification filters
    if cfg.discord_min_value_factor > 0 and (
        listing.value_factor is None or listing.value_factor < cfg.discord_min_value_factor
    ):
        return False
    if cfg.discord_min_profit > 0 and listing.estimated_value is not None:
        profit = listing.estimated_value - listing.price
        if profit < cfg.discord_min_profit:
            return False
    if cfg.discord_max_distance_km > 0 and (
        listing.distance_km is not None and listing.distance_km > cfg.discord_max_distance_km
    ):
        return False

    webhook = DiscordWebhook(url=cfg.discord_webhook_url)

    # Color based on value factor
    if listing.value_factor and listing.value_factor >= 2.0:
        color = "2ecc71"  # Green - great deal
    elif listing.value_factor and listing.value_factor >= 1.5:
        color = "f39c12"  # Yellow/orange - good deal
    else:
        color = "3498db"  # Blue - standard

    profit = (
        (listing.estimated_value - listing.price)
        if listing.estimated_value
        else None
    )

    confidence_str = (
        f"{int(listing.confidence * 100)}%"
        if listing.confidence is not None
        else "N/A"
    )

    distance_str = (
        f"{listing.distance_km} km"
        if listing.distance_km is not None
        else "N/A"
    )

    embed = DiscordEmbed(
        title=listing.title[:256],
        url=listing.url,
        color=color,
    )

    embed.add_embed_field(name="Price", value=f"{listing.price} CHF", inline=True)
    embed.add_embed_field(
        name="Est. Value",
        value=f"{listing.estimated_value} CHF" if listing.estimated_value else "N/A",
        inline=True,
    )
    embed.add_embed_field(
        name="Profit",
        value=f"{profit} CHF" if profit is not None else "N/A",
        inline=True,
    )
    embed.add_embed_field(
        name="Value Factor",
        value=f"{listing.value_factor:.1f}x" if listing.value_factor else "N/A",
        inline=True,
    )
    embed.add_embed_field(name="Confidence", value=confidence_str, inline=True)
    embed.add_embed_field(
        name="Platform",
        value=listing.platform.capitalize(),
        inline=True,
    )
    embed.add_embed_field(
        name="Location",
        value=listing.location or listing.postcode or "N/A",
        inline=True,
    )
    embed.add_embed_field(
        name="Distance from Zurich",
        value=distance_str,
        inline=True,
    )

    if listing.image_url:
        embed.set_thumbnail(url=listing.image_url)

    if listing.eval_reasoning:
        embed.set_footer(text=listing.eval_reasoning[:2048])

    webhook.add_embed(embed)

    try:
        response = webhook.execute()
        if response and (response.status_code == 200 or response.status_code == 204):
            logger.info(f"Notification sent for listing {listing.id}: '{listing.title}'")
            return True
        else:
            status = response.status_code if response else "no response"
            logger.warning(f"Discord webhook returned status {status}")
            return False
    except Exception as e:
        logger.error(f"Failed to send Discord notification: {e}")
        return False


def send_notifications_for_passed(listing_ids: list[int]) -> int:
    """Send notifications for all passed, un-notified listings.

    Returns the number of notifications sent.
    """
    session = get_session()
    sent = 0

    try:
        listings = session.execute(
            select(Listing).where(
                Listing.id.in_(listing_ids),
                Listing.passed_filters == True,
                Listing.notified == False,
            )
        ).scalars().all()

        for listing in listings:
            if send_listing_notification(listing):
                listing.notified = True
                listing.notified_at = datetime.utcnow()
                sent += 1

        session.commit()
        logger.info(f"Sent {sent}/{len(listings)} notifications")
        return sent

    except Exception as e:
        session.rollback()
        logger.error(f"Notification batch failed: {e}")
        return 0
    finally:
        session.close()
