"""LinkedIn source — fragile by nature, isolated and disabled by default.

LinkedIn has no public search API. The only practical options are:

1. A third-party RapidAPI scraper (e.g. "linkedin-data-api",
   "linkedin-bulk-data-scraper") that wraps an unofficial scrape of
   LinkedIn's internal search endpoints.
2. A headless-browser scraper (Apify actor, Playwright, etc.) that logs
   into a real account and scrapes search results directly.

Both approaches scrape an interface LinkedIn doesn't intend to expose and
can break without notice when LinkedIn changes its frontend or a provider's
scraper falls behind. This module implements option (1) — a configurable
RapidAPI endpoint — because it requires no session/cookie management on our
side and degrades to "feature unavailable" rather than a silent auth
failure when the key is missing or invalid.

Swapping implementations: this module's only contract is `fetch() ->
list[Item]`. To switch to an Apify actor or another RapidAPI host, replace
the body of `fetch` (or `_call_rapidapi`) — no changes to `ranker.py`,
`summarizer.py`, or `config.yaml`'s `sources.linkedin` block are required
beyond whatever new env vars your provider needs.

Because of this fragility, `sources.linkedin.enabled` defaults to `false`
in config.yaml.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import requests

from sources.base import Item, Source, parse_timestamp

logger = logging.getLogger(__name__)

REQUEST_TIMEOUT_SECONDS = 15


class LinkedInSource(Source):
    name = "linkedin"

    def fetch(self, topic: str, config: dict[str, Any]) -> list[Item]:
        api_key = os.environ.get("RAPIDAPI_KEY")
        api_host = os.environ.get("RAPIDAPI_HOST")

        if not api_key or not api_host:
            logger.warning(
                "LinkedIn source enabled but RAPIDAPI_KEY/RAPIDAPI_HOST not set; skipping"
            )
            return []

        max_results = config.get("max_results", 15)

        try:
            # Endpoint path/params are provider-specific; this matches the
            # shape of common "linkedin-data-api"-style RapidAPI listings.
            # Adjust the path and response parsing below to match whichever
            # provider you register with.
            response = requests.get(
                f"https://{api_host}/search-posts",
                params={"keywords": topic, "count": max_results},
                headers={
                    "X-RapidAPI-Key": api_key,
                    "X-RapidAPI-Host": api_host,
                },
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
        except requests.RequestException:
            logger.warning("LinkedIn (RapidAPI) request failed", exc_info=True)
            return []

        try:
            posts = response.json().get("data", [])
        except ValueError:
            logger.warning("LinkedIn (RapidAPI) returned non-JSON response")
            return []

        items: list[Item] = []
        for post in posts[:max_results]:
            title = post.get("text", "")[:120] or "(untitled LinkedIn post)"
            url = post.get("postUrl") or post.get("url", "")
            if not url:
                logger.debug("Dropping LinkedIn item without URL: %s", title[:60])
                continue

            items.append(
                Item(
                    source=self.name,
                    title=title,
                    url=url,
                    score=post.get("numLikes", 0) or 0,
                    published_at=parse_timestamp(post.get("postedAt"), epoch_ms=True),
                    summary_raw=(post.get("text") or "")[:500],
                )
            )

        return items


