"""RSS / Atom feed source, via feedparser.

Reads one or more feed URLs from this source's config section and maps each
entry to the shared `Item` schema. Unlike HackerNews/arXiv, the `topic` is not
a query parameter here — a feed is itself the curation, so every entry from the
configured feeds is returned (capped at `max_results`). The `topic` argument is
accepted to honor the `Source` contract.

Per that contract, `fetch` never raises: feedparser does not throw on malformed
input (it sets `bozo`), and any unexpected error while reading a feed is caught,
logged, and that feed is skipped. A feed that yields no usable entries
contributes nothing rather than aborting the run.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import feedparser

from sources.base import Item, Source, parse_timestamp

logger = logging.getLogger(__name__)


class RSSSource(Source):
    name = "rss"

    def fetch(self, topic: str, config: dict[str, Any]) -> list[Item]:
        feeds: list[str] = config.get("feeds", []) or []
        max_results = config.get("max_results", 20)

        items: list[Item] = []
        for feed_url in feeds:
            items.extend(self._fetch_feed(feed_url))

        return items[:max_results]

    def _fetch_feed(self, feed_url: str) -> list[Item]:
        try:
            parsed = feedparser.parse(feed_url)
        except Exception:
            logger.warning("RSS: failed to read feed %s", feed_url, exc_info=True)
            return []

        if getattr(parsed, "bozo", 0) and not parsed.entries:
            logger.warning(
                "RSS: feed %s is malformed and yielded no entries (%s)",
                feed_url,
                getattr(parsed, "bozo_exception", "unknown error"),
            )
            return []

        items: list[Item] = []
        for entry in parsed.entries:
            item = self._entry_to_item(entry)
            if item is not None:
                items.append(item)
        return items

    def _entry_to_item(self, entry: Any) -> Item | None:
        title = (entry.get("title") or "").strip()
        url = (entry.get("link") or "").strip()
        if not title or not url:
            return None

        published_at = self._entry_timestamp(entry)
        summary = (entry.get("summary") or entry.get("description") or "").strip()
        author = (entry.get("author") or "").strip()

        return Item(
            source=self.name,
            title=title,
            url=url,
            score=0,  # RSS entries carry no popularity signal
            published_at=published_at,
            summary_raw=summary[:500],
            extra={"author": author} if author else {},
        )

    @staticmethod
    def _entry_timestamp(entry: Any) -> datetime:
        # Prefer the raw date string (parsed via the shared util); fall back to
        # feedparser's pre-parsed struct_time, then to now().
        raw = entry.get("published") or entry.get("updated")
        if raw:
            return parse_timestamp(raw)
        struct = entry.get("published_parsed") or entry.get("updated_parsed")
        if struct:
            try:
                return datetime(*struct[:6], tzinfo=timezone.utc)
            except (ValueError, TypeError):
                pass
        return datetime.now(timezone.utc)
