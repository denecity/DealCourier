"""Anibis.ch scraper via HTML __NEXT_DATA__ parsing.

Note: Anibis keyword search does not work server-side — the HTML page always
returns the latest unfiltered listings regardless of the query parameter.
Keyword filtering happens client-side via GraphQL (behind Cloudflare).
This scraper still fetches the search URL so the results are at least from the
correct category/context, but results are NOT filtered by search term.
"""

import json
import logging
import re
from datetime import datetime
from urllib.parse import quote

import httpx

from dealcourier.scrapers.base import BaseScraper, RawListing

logger = logging.getLogger("dealcourier.scrapers.anibis")


class AnibisScraper(BaseScraper):
    platform = "anibis"

    def __init__(self, timeout: int = 30, delay: float = 1.0):
        from dealcourier.config import get_config
        cfg = get_config()
        self.timeout = timeout
        self.delay = cfg.anibis_delay_seconds
        self.max_terms = cfg.anibis_max_terms
        self._client = httpx.Client(
            timeout=timeout,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "de-CH,de;q=0.9",
            },
            follow_redirects=True,
        )

    def search(self, term: str) -> list[RawListing]:
        encoded = quote(term)
        url = f"https://www.anibis.ch/de/q/{encoded}"

        try:
            response = self._client.get(url)
            response.raise_for_status()
        except httpx.HTTPError as e:
            logger.warning(f"Anibis HTTP error for '{term}': {e}")
            return []

        return self._parse_html(response.text, term)

    def _parse_html(self, html: str, search_term: str) -> list[RawListing]:
        pattern = re.compile(
            r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
            re.DOTALL,
        )
        match = pattern.search(html)
        if not match:
            logger.warning("Could not find __NEXT_DATA__ in Anibis HTML")
            return []

        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse Anibis JSON: {e}")
            return []

        # Navigate to listings — same structure as tutti.ch:
        # props.pageProps.dehydratedState.queries[N].state.data.listings.edges[]
        edges = self._extract_edges(data)
        if not edges:
            logger.warning(f"No listing edges found in Anibis __NEXT_DATA__ for '{search_term}'")
            return []

        results = []
        for edge in edges:
            listing = self._parse_edge(edge)
            if listing is not None:
                results.append(listing)

        logger.info(f"Anibis '{search_term}': {len(results)} listings parsed from {len(edges)} edges")
        return results

    def _extract_edges(self, data: dict) -> list[dict]:
        """Extract listing edges from __NEXT_DATA__, trying multiple paths."""
        try:
            props = data.get("props", {}).get("pageProps", {})

            # Path 1: dehydratedState.queries[].state.data.listings.edges
            dehydrated = props.get("dehydratedState", {})
            for query in dehydrated.get("queries", []):
                state_data = query.get("state", {}).get("data", {})
                listings = state_data.get("listings", {})
                if isinstance(listings, dict):
                    edges = listings.get("edges", [])
                    if isinstance(edges, list) and edges:
                        return edges

            # Path 2: direct pageProps.listings.edges
            listings = props.get("listings", {})
            if isinstance(listings, dict):
                edges = listings.get("edges", [])
                if isinstance(edges, list) and edges:
                    return edges

        except (KeyError, TypeError, IndexError) as e:
            logger.debug(f"Edge extraction failed: {e}")

        return []

    def _parse_edge(self, edge: dict) -> RawListing | None:
        """Parse a single edge/node into a RawListing. Same format as tutti.ch."""
        node = edge.get("node", {})
        if not node:
            return None

        try:
            listing_id = node.get("listingID", "")
            if not listing_id:
                return None

            title = node.get("title", "")
            if not title:
                return None

            # Price — Swiss format like "250.-" or "1'500.-"
            price = self._extract_price(node.get("formattedPrice", ""))
            if price is None:
                return None

            # Thumbnail
            try:
                image_url = node["thumbnail"]["normalRendition"]["src"]
            except (KeyError, TypeError):
                image_url = None

            # URL — format is /de/vi/{deSlug}/{listingID}
            seo = node.get("seoInformation", {}) or {}
            slug = seo.get("deSlug", "")
            url = f"https://www.anibis.ch/de/vi/{slug}/{listing_id}" if slug else f"https://www.anibis.ch/de/vi/{listing_id}"

            # Location
            postcode_info = node.get("postcodeInformation", {}) or {}
            postcode = str(postcode_info.get("postcode", "")) or None
            location = postcode_info.get("locationName")

            # Seller
            seller = (node.get("sellerInfo", {}) or {}).get("alias")

            # Timestamp
            listed_at = None
            ts = node.get("timestamp")
            if ts:
                try:
                    listed_at = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                except (ValueError, TypeError):
                    pass

            return RawListing(
                platform="anibis",
                platform_id=str(listing_id),
                title=title,
                description=node.get("body", ""),
                category=str((node.get("primaryCategory", {}) or {}).get("categoryID", "")),
                price=price,
                url=url,
                image_url=image_url,
                seller_name=seller,
                postcode=postcode if postcode and postcode != "0" else None,
                location=location,
                listed_at=listed_at,
            )
        except Exception as e:
            logger.debug(f"Failed to parse Anibis edge: {e}")
            return None

    @staticmethod
    def _extract_price(value: str) -> int | None:
        """Parse Swiss price format: '250.-', '1'500.-', plain numbers."""
        if not value:
            return None
        value = value.replace("'", "").replace("\u2019", "")
        import re
        match = re.match(r"^(\d+)\.-$", value)
        if match:
            return int(match.group(1))
        match = re.match(r"^(\d+)$", value)
        if match:
            return int(match.group(1))
        return None
