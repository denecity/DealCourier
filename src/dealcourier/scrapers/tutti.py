"""Tutti.ch scraper."""

import json
import logging
import re
from datetime import datetime
from urllib.parse import quote

import httpx

from dealcourier.scrapers.base import BaseScraper, RawListing

logger = logging.getLogger("dealcourier.scrapers.tutti")


class TuttiScraper(BaseScraper):
    platform = "tutti"

    def __init__(self, timeout: int = 30, delay: float = 1.0):
        from dealcourier.config import get_config
        cfg = get_config()
        self.timeout = timeout
        self.delay = cfg.tutti_delay_seconds
        self.max_terms = cfg.tutti_max_terms
        self._client = httpx.Client(
            timeout=timeout,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            },
            follow_redirects=True,
        )

    def search(self, term: str) -> list[RawListing]:
        encoded = quote(term)
        url = f"https://www.tutti.ch/de/q/suche?query={encoded}&lang=de"

        try:
            response = self._client.get(url)
            response.raise_for_status()
        except httpx.HTTPError as e:
            logger.warning(f"HTTP error for '{term}': {e}")
            return []

        return self._parse_html(response.text, term)

    def _parse_html(self, html: str, search_term: str) -> list[RawListing]:
        # Extract __NEXT_DATA__ JSON blob
        pattern = re.compile(
            r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
            re.DOTALL,
        )
        match = pattern.search(html)
        if not match:
            logger.warning("Could not find __NEXT_DATA__ in HTML")
            return []

        try:
            data = json.loads(match.group(1))
            edges = (
                data["props"]["pageProps"]["dehydratedState"]["queries"][0]["state"][
                    "data"
                ]["listings"]["edges"]
            )
        except (json.JSONDecodeError, KeyError, IndexError, TypeError) as e:
            logger.warning(f"Failed to parse __NEXT_DATA__: {e}")
            return []

        results = []
        for edge in edges:
            listing = self._parse_edge(edge, search_term)
            if listing is not None:
                results.append(listing)

        return results

    def _parse_edge(self, edge: dict, search_term: str) -> RawListing | None:
        node = edge.get("node", {})
        if not node:
            return None

        # Extract price
        price = self._extract_price(node.get("formattedPrice", ""))
        if price is None:
            return None  # Skip free/unparseable listings

        # Extract thumbnail
        try:
            image_url = node["thumbnail"]["normalRendition"]["src"]
        except (KeyError, TypeError):
            image_url = None

        # Build URL
        listing_id = node.get("listingID", "")
        slug = node.get("seoInformation", {}).get("deSlug", "")
        url = f"https://www.tutti.ch/de/vi/{slug}/{listing_id}" if slug else ""

        # Parse timestamp
        listed_at = None
        ts = node.get("timestamp")
        if ts:
            try:
                listed_at = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                pass

        postcode_info = node.get("postcodeInformation", {}) or {}

        return RawListing(
            platform="tutti",
            platform_id=str(listing_id),
            title=node.get("title", ""),
            description=node.get("body", ""),
            category=str(node.get("primaryCategory", {}).get("categoryID", "")),
            price=price,
            url=url,
            image_url=image_url,
            seller_name=(node.get("sellerInfo", {}) or {}).get("alias"),
            postcode=str(postcode_info.get("postcode", "")),
            location=postcode_info.get("locationName"),
            listed_at=listed_at,
        )

    @staticmethod
    def _extract_price(value: str) -> int | None:
        if not value:
            return None
        value = value.replace("'", "").replace("\u2019", "")
        match = re.match(r"^(\d+)\.-$", value)
        if match:
            return int(match.group(1))
        # Try plain number
        match = re.match(r"^(\d+)$", value)
        if match:
            return int(match.group(1))
        return None
