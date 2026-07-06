"""Fetch 1-3 real HN articles per week (2026-01-01 → 2026-06-30) on Claude tool expansion.

Queries the Algolia HN API with explicit per-week created_at_i ranges (the
repo's HackerNewsSource hardcodes a trailing-7-day filter, so historical
windows need direct queries — see README finding F1). Results are filtered
for tool-expansion relevance, ranked by points, and capped at 3/week.

Run:  python3 output/second-brain-tests/fetch_articles.py
Out:  output/second-brain-tests/data/articles_raw.json
"""

from __future__ import annotations

import json
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO))

from resilience import is_transient_http, retry_with_backoff  # noqa: E402

ALGOLIA_URL = "https://hn.algolia.com/api/v1/search"  # relevance-ranked variant
START = date(2026, 1, 1)
END = date(2026, 6, 30)
QUERY = "Claude"
MAX_PER_WEEK = 3

# "Tool expansion" relevance: the title must mention Claude/Anthropic AND at
# least one capability-surface term.
_CAPABILITY_TERMS = (
    "tool", "mcp", "code", "agent", "skill", "plugin", "api", "sdk",
    "integration", "extension", "connector", "computer use", "browser",
    "hook", "slash command", "artifact", "memory",
)


def week_windows(start: date, end: date) -> list[tuple[date, date]]:
    windows = []
    cur = start
    while cur <= end:
        w_end = min(cur + timedelta(days=6), end)
        windows.append((cur, w_end))
        cur = w_end + timedelta(days=1)
    return windows


def _epoch(d: date, end_of_day: bool = False) -> int:
    dt = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
    if end_of_day:
        dt += timedelta(days=1)
    return int(dt.timestamp())


def relevant(title: str) -> bool:
    t = title.lower()
    if "claude" not in t and "anthropic" not in t:
        return False
    return any(term in t for term in _CAPABILITY_TERMS)


def fetch_week(w_start: date, w_end: date) -> list[dict]:
    def _request() -> requests.Response:
        resp = requests.get(
            ALGOLIA_URL,
            params={
                "query": QUERY,
                "tags": "story",
                "numericFilters": (
                    f"created_at_i>={_epoch(w_start)},created_at_i<{_epoch(w_end, end_of_day=True)}"
                ),
                "hitsPerPage": 50,
            },
            timeout=10,
        )
        resp.raise_for_status()
        return resp

    resp = retry_with_backoff(_request, label=f"HN week {w_start}", is_transient=is_transient_http)
    hits = resp.json().get("hits", [])

    picked = []
    for hit in sorted(hits, key=lambda h: h.get("points") or 0, reverse=True):
        title = hit.get("title") or ""
        if not relevant(title):
            continue
        url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
        picked.append({
            "week_start": w_start.isoformat(),
            "week_end": w_end.isoformat(),
            "title": title,
            "url": url,
            "hn_url": f"https://news.ycombinator.com/item?id={hit.get('objectID')}",
            "points": hit.get("points") or 0,
            "num_comments": hit.get("num_comments") or 0,
            "created_at": hit.get("created_at"),
            "story_text": (hit.get("story_text") or "")[:500],
        })
        if len(picked) >= MAX_PER_WEEK:
            break
    return picked


def main() -> None:
    articles: list[dict] = []
    empty_weeks: list[str] = []
    for w_start, w_end in week_windows(START, END):
        picked = fetch_week(w_start, w_end)
        if not picked:
            empty_weeks.append(w_start.isoformat())
        articles.extend(picked)
        print(f"{w_start} → {w_end}: {len(picked)} article(s)")
        time.sleep(0.3)  # be polite to Algolia

    out = HERE / "data" / "articles_raw.json"
    out.write_text(json.dumps({
        "query": QUERY,
        "window": [START.isoformat(), END.isoformat()],
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "empty_weeks": empty_weeks,
        "articles": articles,
    }, indent=2))
    print(f"\nTotal: {len(articles)} articles across {len(week_windows(START, END))} weeks "
          f"({len(empty_weeks)} empty). Wrote {out}")


if __name__ == "__main__":
    main()
