"""P2: category-driven multi-source collection for the timeline product.

Generalizes the trial loop (output/second-brain-tests/live/loop_iteration.py)
to the product categories in config.yaml:

- per run, each category advances through its query rotation
  (QUERIES_PER_CATEGORY at a time, cursor persisted per category)
- every query fetches through the real ingestion path — main.ingest →
  auto-discovered sources (HN + arXiv + RSS per config) in parallel
- new articles (URL-deduped against the corpus) are scraped, extractively
  summarized, and tagged with their category + query — the category flows
  through consolidation → snapshots → the site's tabs
- append-only corpus; every record keeps its URL for citing

Run:  python3 -m secondbrain.collect [--max-new-per-category 8] [--lookback-days 14]
Prints one summary line per category (context-cheap by design).
"""

from __future__ import annotations

import argparse
import json
import logging
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

LIVE = Path("output/second-brain-tests/live")
CORPUS_PATH = LIVE / "corpus.json"
STATE_PATH = LIVE / "collect_state.json"

QUERIES_PER_CATEGORY = 2
DEFAULT_MAX_NEW = 8
DEFAULT_LOOKBACK_DAYS = 14


def _load(path: Path, default):
    return json.loads(path.read_text()) if path.exists() else default


def collect_category(
    category: str,
    queries: list[str],
    cursor: int,
    known_urls: set[str],
    sources_config: dict,
    max_new: int,
    fetched_at: str,
) -> tuple[list[dict], int]:
    """One category's collection pass. Returns (new records, new cursor)."""
    from main import ingest
    from scraper import scrape
    from secondbrain.textutil import extractive_summary

    picked = [queries[(cursor + k) % len(queries)] for k in range(QUERIES_PER_CATEGORY)]
    new_records: list[dict] = []

    for query in picked:
        for item in ingest(query, sources_config):
            if item.url in known_urls or len(new_records) >= max_new:
                continue
            known_urls.add(item.url)

            art = scrape(item.url, {"min_body_chars": 200, "timeout": 10})
            body = art.body if art and art.body else (item.summary_raw or item.title)

            new_records.append({
                "url": item.url,                      # kept for citing
                "hn_title": item.title,
                "source": item.source,
                "query": query,
                "category": category,
                "points": item.score,
                "published_at": item.published_at.isoformat(),
                "fetched_at": fetched_at,
                "scraped": bool(art and art.body),
                "summary": extractive_summary(body),
            })

    return new_records, (cursor + QUERIES_PER_CATEGORY) % len(queries)


def main() -> None:
    from config import load_config

    ap = argparse.ArgumentParser(description="Category-driven collection run")
    ap.add_argument("--max-new-per-category", type=int, default=DEFAULT_MAX_NEW)
    ap.add_argument("--lookback-days", type=int, default=DEFAULT_LOOKBACK_DAYS)
    args = ap.parse_args()

    config = load_config()
    categories: dict = config.get("categories") or {}
    if not categories:
        raise RuntimeError("config.yaml has no `categories:` section — nothing to collect")

    now = datetime.now(timezone.utc)
    corpus = _load(CORPUS_PATH, [])
    state = _load(STATE_PATH, {"cursors": {}, "runs": 0})
    known_urls = {a["url"] for a in corpus}

    # historical window for window-honoring sources (HN); RSS/arXiv return
    # their recent items regardless — the dedupe absorbs overlap
    sources_config = dict(config.get("sources", {}))
    date_from = (date.today() - timedelta(days=args.lookback_days)).isoformat()
    for name in sources_config:
        sources_config[name] = {**sources_config[name],
                                "date_from": date_from, "date_to": date.today().isoformat()}

    total_new = 0
    for category, spec in categories.items():
        queries = spec.get("queries") or []
        if not queries:
            continue
        cursor = state["cursors"].get(category, 0)
        records, state["cursors"][category] = collect_category(
            category, queries, cursor, known_urls, sources_config,
            args.max_new_per_category, now.isoformat(),
        )
        corpus.extend(records)
        total_new += len(records)
        print(f"{category}: +{len(records)} new")

    state["runs"] += 1
    LIVE.mkdir(parents=True, exist_ok=True)
    CORPUS_PATH.write_text(json.dumps(corpus, indent=2))
    STATE_PATH.write_text(json.dumps(state, indent=2))
    print(f"collect run {state['runs']}: +{total_new} articles → corpus {len(corpus)}")


if __name__ == "__main__":
    main()
