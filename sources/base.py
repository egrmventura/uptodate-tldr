"""Shared schema and abstract base class for content sources.

Every source module implements `Source.fetch(topic) -> list[Item]` and is
responsible for catching its own exceptions: a source that times out, hits
a rate limit, or returns malformed data should log a warning and return an
empty list rather than raising. This lets the pipeline keep running on
partial data when any single source is unavailable.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Item:
    """A single piece of content, normalized across all sources."""

    source: str
    title: str
    url: str
    score: int
    published_at: datetime
    summary_raw: str
    # Optional, source-specific extras (e.g. arXiv citation count).
    extra: dict[str, Any] = field(default_factory=dict)


def parse_timestamp(value: int | float | str | None, epoch_ms: bool = False) -> datetime:
    """Best-effort timestamp parse — shared across all source modules.

    Handles Unix epoch (seconds or milliseconds), ISO 8601 strings, and None.
    Falls back to now(UTC) rather than failing the item.
    """
    if value is None:
        return datetime.now(timezone.utc)

    if isinstance(value, (int, float)):
        try:
            ts = value / 1000 if epoch_ms else value
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        except (ValueError, OSError):
            return datetime.now(timezone.utc)

    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return datetime.now(timezone.utc)

    return datetime.now(timezone.utc)


class Source(ABC):
    """Abstract base class for a content source.

    Implementations must set `name` and implement `fetch`. `fetch` must
    never raise: wrap all I/O in try/except, log a warning on failure, and
    return `[]` so one bad source can't abort the run.
    """

    name: str = "base"

    @abstractmethod
    def fetch(self, topic: str, config: dict[str, Any]) -> list[Item]:
        """Return items matching `topic`, using this source's section of `config`."""
        raise NotImplementedError

    def safe_fetch(self, topic: str, config: dict[str, Any]) -> list[Item]:
        """Call `fetch`, catching and logging any unexpected exception."""
        try:
            return self.fetch(topic, config)
        except Exception:
            logger.warning("Source %r failed unexpectedly", self.name, exc_info=True)
            return []
