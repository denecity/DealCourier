"""Abstract base scraper interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class RawListing:
    """Common listing shape that all scrapers produce."""

    platform: str
    platform_id: str
    title: str
    description: str | None = None
    category: str | None = None
    price: int = 0
    currency: str = "CHF"
    url: str = ""
    image_url: str | None = None
    seller_name: str | None = None
    postcode: str | None = None
    location: str | None = None
    shipping_cost: float = 0.0
    listed_at: datetime | None = None
    auction_end_at: datetime | None = None


class BaseScraper(ABC):
    """Abstract base class for marketplace scrapers.

    All scrapers must implement the search() method.
    Scrapers should never raise exceptions -- they return empty lists on failure.
    """

    platform: str = ""
    timeout: int = 30
    delay: float = 1.0
    max_terms: int = 0  # 0 = no limit

    @abstractmethod
    def search(self, term: str) -> list[RawListing]:
        """Search the platform for a term. Returns raw listings."""
        ...

    def search_multiple(self, terms: list[str]) -> list[RawListing]:
        """Search multiple terms, deduplicate by platform_id."""
        import time
        import logging

        logger = logging.getLogger(f"dealcourier.scrapers.{self.platform}")
        seen_ids: set[str] = set()
        results: list[RawListing] = []

        effective_terms = terms
        if self.max_terms > 0 and len(terms) > self.max_terms:
            effective_terms = terms[:self.max_terms]
            logger.info(
                f"{self.platform}: capped to {self.max_terms}/{len(terms)} terms"
            )

        for i, term in enumerate(effective_terms):
            try:
                listings = self.search(term)
                for listing in listings:
                    if listing.platform_id not in seen_ids:
                        seen_ids.add(listing.platform_id)
                        results.append(listing)
                logger.info(
                    f"[{i+1}/{len(effective_terms)}] '{term}': {len(listings)} found, "
                    f"{len(results)} total unique"
                )
            except Exception as e:
                logger.warning(f"[{i+1}/{len(effective_terms)}] '{term}' failed: {e}")

            if i < len(effective_terms) - 1:
                time.sleep(self.delay)

        return results
