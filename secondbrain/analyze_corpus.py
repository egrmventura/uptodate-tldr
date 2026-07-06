"""M3: run the comparative analyst over the consolidated corpus.

Bridges the second-brain corpus into the production analysis pipeline:

  consolidated groups ──H1 sliding-14d windows──► TopicGroup units
      ──analyst (LLM, retry/backoff)──► GroupAnalysis rows
      ──store.save_run (idempotent)──► output/analyses.db
      ──timeline.render_timeline──► markdown timelines

Only multi-doc, on-topic window buckets are analyzed (comparative analysis
needs 2+ sources; singletons carry no compare/contrast signal). LLM spend is
bounded by --max-calls. Periods come from article publication dates via
windowing.window_bounds — the backfill-correctness rule.

Run:  python3 -m secondbrain.analyze_corpus [--max-calls 40] [--db PATH] [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import date
from pathlib import Path

from grouper import TopicGroup
from sources.base import Item, parse_timestamp
from secondbrain.windowing import DEFAULT_WINDOW_DAYS, sliding_windows

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

CONSOLIDATED = Path("output/second-brain-tests/consolidated/consolidated_groups.json")
CORPUS = Path("output/second-brain-tests/live/corpus.json")
TIMELINE_DIR = Path("output/second-brain-tests/timelines")


def _to_item(article: dict) -> Item:
    return Item(
        source="hackernews",
        title=article.get("hn_title") or article.get("title") or "?",
        url=article["url"],
        score=article.get("points", 0),
        published_at=parse_timestamp(article.get("published_at")),
        summary_raw=(article.get("summary") or "")[:300],
        extra={"query": article.get("query", "")},
    )


def build_units(window_days: int = DEFAULT_WINDOW_DAYS) -> list[TopicGroup]:
    """Consolidated groups → windowed TopicGroup units with 2+ items each."""
    data = json.loads(CONSOLIDATED.read_text())
    corpus = {a["url"]: a for a in json.loads(CORPUS.read_text())}

    units: list[TopicGroup] = []
    for g in data["groups"]:
        if g["singleton"] or g["off_topic"]:
            continue
        items = [_to_item(corpus[u]) for u in g["urls"] if u in corpus]
        for bucket in sliding_windows(items, window_days):
            if len(bucket) >= 2:
                units.append(TopicGroup(label=g["label"], items=bucket))
    return units


def main() -> None:
    ap = argparse.ArgumentParser(description="Analyst pass over the consolidated corpus")
    ap.add_argument("--max-calls", type=int, default=40, help="LLM spend cap (units analyzed)")
    ap.add_argument("--db", type=Path, default=None, help="Store db path (default: production)")
    ap.add_argument("--window-days", type=int, default=DEFAULT_WINDOW_DAYS)
    ap.add_argument("--dry-run", action="store_true", help="List units; no LLM calls, no writes")
    args = ap.parse_args()

    units = build_units(args.window_days)
    units = units[: args.max_calls]
    logger.info("Analyst pass: %d unit(s) (cap %d)", len(units), args.max_calls)

    if args.dry_run:
        for u in units:
            start, end = u.date_range
            print(f"{len(u.items)} items  {start.date()} → {end.date()}  {u.label}")
        return

    from analyst import analyze_all
    from config import load_config
    from store import Store
    from timeline import render_timeline

    config = load_config()
    analyses = analyze_all(units, config)
    if not analyses:
        raise RuntimeError("Analyst produced no analyses — nothing to persist")

    store = Store(args.db) if args.db else Store()
    store.save_run(analyses, date.today(), is_backfill=True)

    TIMELINE_DIR.mkdir(parents=True, exist_ok=True)
    rendered = 0
    for topic in sorted({a.topic for a in analyses}):
        md = render_timeline(topic, store)
        if md:
            safe = "".join(c if c.isalnum() or c in "-_" else "-" for c in topic)[:60]
            (TIMELINE_DIR / f"{safe}.md").write_text(md)
            rendered += 1

    logger.info("Analyst pass complete: %d analyses persisted, %d timeline(s) rendered",
                len(analyses), rendered)


if __name__ == "__main__":
    main()
