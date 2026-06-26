"""Entrypoint for the uptodate-tldr pipeline.

Usage:
    python main.py --run-now

Pipeline stages:
1. Ingest from each enabled source (independently, failures isolated).
2. Rank merged items, take the top N.
3. Summarize the top N with the Anthropic API into a persona-tuned digest.
4. Deliver the digest to each enabled channel (independently, failures
   isolated and logged).

If every source fails, the run aborts (there's nothing to summarize). If
every delivery channel fails, the run still exits non-zero so a scheduler
can alert, but the markdown artifact (if enabled) will still be on disk.
"""

from __future__ import annotations

import argparse
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from typing import Any

from config import load_config
from ranker import rank_items
from sources.arxiv import ArxivSource
from sources.base import Item, Source
from sources.hackernews import HackerNewsSource
from sources.linkedin import LinkedInSource
from summarizer import summarize

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

_SOURCES: dict[str, Source] = {
    "hackernews": HackerNewsSource(),
    "arxiv": ArxivSource(),
    "linkedin": LinkedInSource(),
}

_DELIVERY_MODULES = {
    "markdown": "delivery.markdown",
    "email": "delivery.email",
    "substack": "delivery.substack",
}


def ingest(topic: str, sources_config: dict[str, Any]) -> list[Item]:
    enabled = {
        name: source
        for name, source in _SOURCES.items()
        if sources_config.get(name, {}).get("enabled", False)
    }

    items: list[Item] = []

    def _fetch(name: str, source: Source) -> tuple[str, list[Item]]:
        return name, source.safe_fetch(topic, sources_config.get(name, {}))

    with ThreadPoolExecutor(max_workers=len(enabled) or 1) as pool:
        futures = {pool.submit(_fetch, n, s): n for n, s in enabled.items()}
        for future in as_completed(futures):
            name, fetched = future.result()
            logger.info("Source %r returned %d items", name, len(fetched))
            items.extend(fetched)

    return items


def deliver_all(digest_markdown: str, topic: str, config: dict[str, Any], run_date: date) -> None:
    import importlib

    delivery_config = config.get("delivery", {})
    any_succeeded = False

    for name, module_path in _DELIVERY_MODULES.items():
        channel_config = delivery_config.get(name, {})
        if not channel_config.get("enabled", False):
            continue

        try:
            module = importlib.import_module(module_path)
            module.deliver(digest_markdown, topic, config, run_date)
            any_succeeded = True
        except Exception:
            logger.warning("Delivery channel %r failed", name, exc_info=True)

    if not any_succeeded:
        raise RuntimeError("All enabled delivery channels failed (or none are enabled)")


def run_pipeline() -> None:
    config = load_config()
    topic = config["topic"]

    logger.info("Starting run for topic=%r", topic)

    raw_items = ingest(topic, config.get("sources", {}))
    if not raw_items:
        raise RuntimeError("All sources failed or returned no results; aborting run")

    top_items = rank_items(raw_items, config.get("ranking", {}), config.get("top_n", 4))
    logger.info("Ranked down to top %d items", len(top_items))

    digest_markdown = summarize(top_items, config)

    deliver_all(digest_markdown, topic, config, date.today())
    logger.info("Run complete")


def main() -> None:
    parser = argparse.ArgumentParser(description="uptodate-tldr pipeline")
    parser.add_argument(
        "--run-now",
        action="store_true",
        help="Run the pipeline immediately instead of starting the scheduler",
    )
    args = parser.parse_args()

    if args.run_now:
        run_pipeline()
    else:
        from scheduler import start_scheduler

        start_scheduler()


if __name__ == "__main__":
    main()
