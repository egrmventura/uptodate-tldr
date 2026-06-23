"""Composite signal ranking for merged source items.

Score = recency-weighted engagement
      + citation_weight * citations (arXiv only)
      then multiplied by cross_source_bonus if the same story was found
      in 2+ sources.

Recency weighting uses exponential decay with a configurable half-life so a
high-score post from yesterday doesn't permanently outrank a similarly
popular post from this morning.

Cross-source matching is intentionally simple: items are grouped by a
normalized title (lowercased, punctuation stripped, whitespace collapsed)
or by exact URL. This catches the common case — the same article submitted
to HN and discussed on Reddit — without needing a fuzzy-matching/embedding
pipeline. See README "Known limitations" for tradeoffs.
"""

from __future__ import annotations

import math
import re
from datetime import datetime, timezone
from typing import Any

from sources.base import Item

_PUNCTUATION_RE = re.compile(r"[^\w\s]")
_WHITESPACE_RE = re.compile(r"\s+")


def _normalize_title(title: str) -> str:
    normalized = _PUNCTUATION_RE.sub("", title.lower())
    return _WHITESPACE_RE.sub(" ", normalized).strip()


def _dedup_key(item: Item) -> str:
    normalized = _normalize_title(item.title)
    return normalized if normalized else item.url.rstrip("/")


def _recency_weight(published_at: datetime, half_life_hours: float, now: datetime) -> float:
    if published_at.tzinfo is None:
        published_at = published_at.replace(tzinfo=timezone.utc)
    age_hours = max((now - published_at).total_seconds() / 3600, 0)
    return math.pow(0.5, age_hours / half_life_hours)


def rank_items(items: list[Item], ranking_config: dict[str, Any], top_n: int) -> list[Item]:
    """Return the top `top_n` items sorted by composite score, descending."""
    now = datetime.now(timezone.utc)
    half_life_hours = ranking_config.get("recency_half_life_hours", 24)
    cross_source_bonus = ranking_config.get("cross_source_bonus", 1.5)
    citation_weight = ranking_config.get("citation_weight", 2.0)

    # Group items that represent the same story across sources.
    groups: dict[str, list[Item]] = {}
    for item in items:
        groups.setdefault(_dedup_key(item), []).append(item)

    scored: list[tuple[float, Item]] = []
    for group in groups.values():
        # Keep the highest-engagement representative for display, but score
        # using the combined signal from every source that surfaced it.
        representative = max(group, key=lambda i: i.score + citation_weight * i.extra.get("citations", 0))
        sources_seen = {i.source for i in group}

        base_score = 0.0
        for member in group:
            recency = _recency_weight(member.published_at, half_life_hours, now)
            citations = member.extra.get("citations", 0)
            base_score += member.score * recency + citation_weight * citations

        if len(sources_seen) >= 2:
            base_score *= cross_source_bonus

        scored.append((base_score, representative))

    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [item for _, item in scored[:top_n]]
