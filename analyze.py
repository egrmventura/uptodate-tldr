"""Entrypoint for the comparative analysis pipeline.

Usage:
    python analyze.py --run-now
    python analyze.py --backfill --from 2024-01-01 --to 2025-01-01
    python analyze.py --timeline "Anthropic MCP"

Pipeline (--run-now):
1. Ingest from enabled sources (reuses main.ingest).
2. Group items by topic via LLM (grouper.group_items).
3. Analyze each group for agreements/contradictions/debunks (analyst.analyze_all).
4. Persist analyses to SQLite store.
5. Write analysis digest markdown to output/.

Pipeline (--backfill):
Same as above but injects date_from/date_to into source config so HN/arXiv
fetch within a historical window. Analyses are stamped with article publication
dates, not today's date.

Pipeline (--timeline):
Queries the store and renders a chronological markdown file for the given topic.
"""

from __future__ import annotations

import argparse
import logging
from datetime import date, datetime, timezone
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def run_analysis(is_backfill: bool = False, date_from: date | None = None, date_to: date | None = None) -> None:
    from analyst import analyze_all
    from config import load_config
    from delivery import analysis_md
    from grouper import group_items
    from main import ingest
    from store import Store

    config = load_config()
    # Use `topics` list if present; fall back to single `topic` for compatibility.
    topics = config.get("topics") or [config["topic"]]
    sources_config = config.get("sources", {})

    if is_backfill and date_from and date_to:
        logger.info("Backfill mode: %s → %s", date_from, date_to)
        for name in sources_config:
            sources_config[name]["date_from"] = date_from.isoformat()
            sources_config[name]["date_to"] = date_to.isoformat()

    run_date = date.today()
    store = Store()
    all_analyses = []

    for topic in topics:
        logger.info("Ingesting topic=%r (backfill=%s)", topic, is_backfill)
        items = ingest(topic, sources_config)
        if not items:
            logger.warning("No items for topic=%r — skipping", topic)
            continue

        groups = group_items(items, config)
        if not groups:
            logger.info("No multi-source groups for topic=%r — skipping", topic)
            continue

        analyses = analyze_all(groups, config)
        if analyses:
            all_analyses.extend(analyses)
        else:
            logger.warning("All groups failed analysis for topic=%r", topic)

    if not all_analyses:
        logger.warning("No analyses produced across all topics — nothing to persist or deliver")
        return

    store.save_run(all_analyses, run_date, is_backfill=is_backfill)
    analysis_md.deliver(all_analyses, "AI/ML/Data Engineering", config, run_date)
    logger.info("Analysis run complete — %d group(s) across %d topic(s)", len(all_analyses), len(topics))


def run_timeline(topic: str) -> None:
    from config import load_config
    from delivery import timeline_md
    from store import Store

    config = load_config()
    store = Store()
    path = timeline_md.deliver(topic, store, config)
    if path:
        logger.info("Timeline written to %s", path)
    else:
        logger.warning("No timeline data found for topic %r", topic)


def main() -> None:
    parser = argparse.ArgumentParser(description="uptodate-tldr comparative analysis pipeline")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--run-now", action="store_true", help="Run the analysis pipeline immediately")
    mode.add_argument("--backfill", action="store_true", help="Run over a historical date range")
    mode.add_argument("--timeline", metavar="TOPIC", help="Render the stored timeline for a topic")

    parser.add_argument("--from", dest="date_from", metavar="YYYY-MM-DD", help="Backfill start date")
    parser.add_argument("--to", dest="date_to", metavar="YYYY-MM-DD", help="Backfill end date")

    args = parser.parse_args()

    if args.timeline:
        run_timeline(args.timeline)
    elif args.backfill:
        if not args.date_from or not args.date_to:
            parser.error("--backfill requires --from and --to")
        date_from = date.fromisoformat(args.date_from)
        date_to = date.fromisoformat(args.date_to)
        run_analysis(is_backfill=True, date_from=date_from, date_to=date_to)
    else:
        run_analysis()


if __name__ == "__main__":
    main()
