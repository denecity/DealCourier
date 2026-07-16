"""Product knowledge base for improving valuation accuracy."""

import logging
from datetime import datetime

from sqlalchemy import select

from dealcourier.db.engine import get_session
from dealcourier.db.models import Product

logger = logging.getLogger("dealcourier.knowledge.products")


def get_product_context(title: str, description: str) -> str:
    """Build product context string from knowledge base for a listing.

    Searches for known products matching words in the title/description
    and returns a formatted context string for the AI prompt.
    """
    session = get_session()
    try:
        products = session.execute(select(Product)).scalars().all()
        if not products:
            return ""

        # Simple keyword matching: check if product name appears in title or description
        text = f"{title} {description}".lower()
        matches = []

        for product in products:
            if product.name.lower() in text:
                trend_str = ""
                if product.value_trend is not None:
                    if product.value_trend > 0.1:
                        trend_str = " (trending up)"
                    elif product.value_trend < -0.1:
                        trend_str = " (trending down)"

                matches.append(
                    f"- {product.name}: ~{product.estimated_value} CHF "
                    f"(based on {product.sample_count} listings){trend_str}"
                )

        if not matches:
            return ""

        return "Known market data:\n" + "\n".join(matches)

    except Exception as e:
        logger.debug(f"Product context lookup failed: {e}")
        return ""
    finally:
        session.close()


def update_product_knowledge(
    components: list[str], values: list[int]
) -> None:
    """Update the product knowledge base with new component data.

    Uses a rolling average weighted by sample count.
    """
    if len(components) != len(values):
        return

    session = get_session()
    try:
        for name, value in zip(components, values):
            if not name or value <= 0:
                continue

            name = name.strip()
            existing = session.execute(
                select(Product).where(Product.name == name)
            ).scalar_one_or_none()

            if existing:
                # Rolling weighted average
                old_total = existing.estimated_value * existing.sample_count
                existing.sample_count += 1
                new_avg = (old_total + value) / existing.sample_count
                old_value = existing.estimated_value
                existing.estimated_value = int(new_avg)

                # Simple trend: positive if new value > old average
                if old_value > 0:
                    existing.value_trend = round((value - old_value) / old_value, 3)

                existing.last_updated = datetime.utcnow()
            else:
                product = Product(
                    name=name,
                    estimated_value=value,
                    sample_count=1,
                    last_updated=datetime.utcnow(),
                )
                session.add(product)

        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Failed to update product knowledge: {e}")
    finally:
        session.close()
