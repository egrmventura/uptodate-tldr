"""H1 sliding-window assignment — the date-windowing study winner.

Scheme (see experiments/date_windowing/FINDINGS.md): windows have a static
magnitude (default 14 days) but dynamic positions — a new window opens at the
first unassigned item, chronologically, and spans the next `window_days` days.
Anchor-free by construction: assignments depend only on the items' own
publication dates, never on a calendar anchor, so idempotency keys derived
from window bounds are stable across re-runs.

Study numbers that picked this default: tied-best boundary split rate (0.84),
zero anchor churn, zero first-doc churn at 14d, max window bounded (8 docs on
the trial corpus).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Sequence

DEFAULT_WINDOW_DAYS = 14


def sliding_windows(
    items: Sequence[Any],
    window_days: int = DEFAULT_WINDOW_DAYS,
    key=lambda item: item.published_at,
) -> list[list[Any]]:
    """Bucket `items` into H1 sliding windows of `window_days`, oldest first.

    Each bucket's span starts at its earliest item and covers window_days-1
    further days; the next bucket opens at the first later item. Items inside
    a bucket keep chronological order. Empty input → empty list.
    """
    if window_days < 1:
        raise ValueError(f"window_days must be >= 1, got {window_days}")
    if not items:
        return []

    ordered = sorted(items, key=key)
    buckets: list[list[Any]] = []
    window_end: datetime | None = None

    for item in ordered:
        ts = key(item)
        if window_end is None or ts > window_end:
            buckets.append([])
            window_end = ts + timedelta(days=window_days - 1)
        buckets[-1].append(item)
    return buckets


def window_bounds(bucket: Sequence[Any], key=lambda item: item.published_at):
    """(period_start, period_end) from a bucket's actual publication dates —
    the backfill-correctness rule: periods come from the articles, never the
    run date."""
    if not bucket:
        raise ValueError("window_bounds of an empty bucket")
    stamps = [key(item) for item in bucket]
    return min(stamps), max(stamps)
