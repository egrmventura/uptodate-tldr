"""Hacker News source, via the Algolia HN Search API.

Algolia's HN index (https://hn.algolia.com/api) is free, unauthenticated,
and has no documented rate limit for reasonable use, making it the most
stable source in this project. We search stories by topic and sort by
points within the last 7 days to capture "recently viral".

Backfill/seed windows: when `date_from` and `date_to` (ISO dates) are present
in the source config — analyze.py injects them for --backfill/--seed/--batch —
the query filters to that historical window (inclusive of both endpoints)
instead of the trailing-7-days default.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import requests

from resilience import is_transient_http, retry_with_backoff
from sources.base import Item, Source, parse_timestamp

logger = logging.getLogger(__name__)

ALGOLIA_SEARCH_URL = "https://hn.algolia.com/api/v1/search"
REQUEST_TIMEOUT_SECONDS = 10


class HackerNewsSource(Source):
    name = "hackernews"

    def fetch(self, topic: str, config: dict[str, Any]) -> list[Item]:
        max_results = config.get("max_results", 30)
        window_filter = _window_filter(config.get("date_from"), config.get("date_to"))

        def _request() -> requests.Response:
            response = requests.get(
                ALGOLIA_SEARCH_URL,
                params={
                    "query": topic,
                    "tags": "story",
                    "numericFilters": window_filter,
                    "hitsPerPage": max_results,
                },
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            return response

        try:
            # Transient failures (timeout, connection drop, 429/5xx) are
            # retried with backoff; a still-failing source stays isolated.
            response = retry_with_backoff(_request, label="HackerNews", is_transient=is_transient_http)
        except requests.RequestException:
            logger.warning("HackerNews request failed", exc_info=True)
            return []

        hits = response.json().get("hits", [])
        items: list[Item] = []
        for hit in hits:
            title = hit.get("title")
            object_id = hit.get("objectID")
            if not title or not object_id:
                continue

            # Prefer the linked URL; fall back to the HN discussion page for
            # "Ask HN" / "Show HN" text posts that have no external link.
            url = hit.get("url") or f"https://news.ycombinator.com/item?id={object_id}"

            created_at = parse_timestamp(hit.get("created_at_i"))
            story_text = hit.get("story_text") or ""

            items.append(
                Item(
                    source=self.name,
                    title=title,
                    url=url,
                    score=hit.get("points", 0) or 0,
                    published_at=created_at,
                    summary_raw=story_text[:500],
                )
            )

        return items


def _seven_days_ago_timestamp() -> int:
    return int(datetime.now(timezone.utc).timestamp()) - 7 * 24 * 60 * 60


def _window_filter(date_from: str | None, date_to: str | None) -> str:
    """Build the created_at_i numericFilters value.

    With both `date_from` and `date_to` (ISO dates, inclusive), filter to that
    historical window: [date_from 00:00 UTC, date_to+1day 00:00 UTC). Otherwise
    — including on malformed dates, which log and fall through — keep the
    original trailing-7-days behavior.
    """
    if date_from and date_to:
        try:
            start = datetime.fromisoformat(date_from).replace(tzinfo=timezone.utc)
            end = datetime.fromisoformat(date_to).replace(tzinfo=timezone.utc) + timedelta(days=1)
            if start < end:
                return f"created_at_i>={int(start.timestamp())},created_at_i<{int(end.timestamp())}"
            logger.warning(
                "HackerNews: date_from %r not before date_to %r — using trailing 7 days",
                date_from, date_to,
            )
        except ValueError:
            logger.warning(
                "HackerNews: malformed date window (%r, %r) — using trailing 7 days",
                date_from, date_to,
            )
    return "created_at_i>" + str(_seven_days_ago_timestamp())


