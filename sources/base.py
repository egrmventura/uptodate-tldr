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
from datetime import datetime
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
