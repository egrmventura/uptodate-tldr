"""Tests for the secondbrain layer (milestones M1–M4 of the launch plan).

Offline throughout — no network, no LLM. Run:
    python3 -m pytest test_secondbrain.py -v
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sources.base import Item


def _item(day: int, title: str = "t", month: int = 1) -> Item:
    return Item(source="hn", title=title, url=f"https://x/{month}-{day}-{title}",
                score=1, published_at=datetime(2026, month, day, tzinfo=timezone.utc),
                summary_raw="s")


# ---------- M1: H1 sliding windowing ----------

def test_sliding_windows_basic():
    from secondbrain.windowing import sliding_windows
    items = [_item(1), _item(5), _item(14), _item(15), _item(29)]
    buckets = sliding_windows(items, 14)
    # window 1 opens Jan 1, spans through Jan 14 → items 1,5,14
    # window 2 opens Jan 15 → item 15 (Jan 29 is beyond Jan 15+13=Jan 28)
    # window 3 opens Jan 29
    assert [len(b) for b in buckets] == [3, 1, 1]


def test_sliding_windows_anchor_free():
    """Shifting every date by the same offset must shift windows identically —
    the anchor-invariance property that won H1 the study."""
    from secondbrain.windowing import sliding_windows
    base = [_item(d) for d in (1, 5, 14, 15, 29)]
    shifted = [Item(source=i.source, title=i.title, url=i.url, score=i.score,
                    published_at=i.published_at + timedelta(days=3),
                    summary_raw=i.summary_raw) for i in base]
    shape = lambda items: [len(b) for b in sliding_windows(items, 14)]
    assert shape(base) == shape(shifted)


def test_sliding_windows_edges():
    from secondbrain.windowing import sliding_windows
    assert sliding_windows([], 14) == []
    one = [_item(7)]
    assert [len(b) for b in sliding_windows(one, 14)] == [1]
    try:
        sliding_windows(one, 0)
        assert False, "window_days=0 must raise"
    except ValueError:
        pass


def test_window_bounds_from_publication_dates():
    from secondbrain.windowing import sliding_windows, window_bounds
    items = [_item(3), _item(1), _item(9)]
    (bucket,) = sliding_windows(items, 14)
    start, end = window_bounds(bucket)
    assert start == datetime(2026, 1, 1, tzinfo=timezone.utc)
    assert end == datetime(2026, 1, 9, tzinfo=timezone.utc)
