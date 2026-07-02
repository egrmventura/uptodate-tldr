"""Entrypoint for the comparative analysis pipeline.

Usage:
    python analyze.py --run-now
    python analyze.py --backfill --from 2024-01-01 --to 2025-01-01
    python analyze.py --seed --from 2024-01-01 --to 2025-01-01 [--window-days 30]
    python analyze.py --batch spec.yaml
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

Pipeline (--seed):
Repeatable timeline seeding: splits [--from, --to] into consecutive windows of
--window-days each and runs the backfill pipeline once per window. Idempotent —
persistence relies on the store's UNIQUE(topic, period_start, period_end) +
INSERT OR IGNORE, so re-running the same range adds no duplicate rows. A window
failure is logged and the remaining windows still run. Seeding only persists
history — the per-run digest delivery is skipped.

Pipeline (--batch):
Coordinated batch run across many (topic × date-window) units, driven by a
declarative YAML spec (see load_batch_spec for the format). Units are isolated
(one failure logs and continues), parallelism is bounded by the spec's
max_workers (default 1), and re-running the same spec is idempotent.

Pipeline (--timeline):
Queries the store and renders a chronological markdown file for the given topic.
"""

from __future__ import annotations

import argparse
import logging
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from grouper import TopicGroup
    from sources.base import Item
    from store import GroupAnalysis, Store

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


# ---------- stage hand-off contracts ----------
#
# Each stage has one explicit contract:
#   ingest  : (topic, sources_config, scraping_config)  -> list[Item]
#   group   : (list[Item], config)                      -> list[TopicGroup]
#   analyze : (list[TopicGroup], config)                -> list[GroupAnalysis]
#   persist : (list[GroupAnalysis], run_date, backfill) -> run_id
#   deliver : (list[GroupAnalysis], config, run_date)   -> None
#
# A violated hand-off raises TypeError immediately — it is never silently
# passed downstream. Failure semantics inside a stage are unchanged: source/
# enrichment failures are isolated by the sources layer, empty group/analysis
# hand-offs skip the topic, and an empty final hand-off skips persist+deliver.

def _check_handoff(stage: str, value: Any, elem_type: type) -> None:
    """Raise TypeError if a stage hand-off is not a list of `elem_type`."""
    if not isinstance(value, list):
        raise TypeError(
            f"Stage {stage!r} hand-off violation: expected list[{elem_type.__name__}], "
            f"got {type(value).__name__}"
        )
    for v in value:
        if not isinstance(v, elem_type):
            raise TypeError(
                f"Stage {stage!r} hand-off violation: element is "
                f"{type(v).__name__}, expected {elem_type.__name__}"
            )


def _stage_ingest(topic: str, sources_config: dict[str, Any], scraping_config: dict[str, Any]) -> list[Item]:
    from main import ingest
    from sources.base import Item
    items = ingest(topic, sources_config, scraping_config)
    _check_handoff("ingest", items, Item)
    return items


def _stage_group(items: list[Item], config: dict[str, Any]) -> list[TopicGroup]:
    from grouper import TopicGroup, group_items
    groups = group_items(items, config)
    _check_handoff("group", groups, TopicGroup)
    return groups


def _stage_analyze(groups: list[TopicGroup], config: dict[str, Any]) -> list[GroupAnalysis]:
    from analyst import analyze_all
    from store import GroupAnalysis
    analyses = analyze_all(groups, config)
    _check_handoff("analyze", analyses, GroupAnalysis)
    return analyses


def _stage_persist(analyses: list[GroupAnalysis], store: Store, run_date: date, is_backfill: bool) -> int:
    return store.save_run(analyses, run_date, is_backfill=is_backfill)


def _stage_deliver(analyses: list[GroupAnalysis], config: dict[str, Any], run_date: date) -> None:
    from delivery import analysis_md
    analysis_md.deliver(analyses, "AI/ML/Data Engineering", config, run_date)


# ---------- orchestrator ----------

def run_analysis(
    is_backfill: bool = False,
    date_from: date | None = None,
    date_to: date | None = None,
    db_path: Path | None = None,
    deliver: bool = True,
    topics_override: list[str] | None = None,
) -> None:
    from config import load_config
    from store import Store

    config = load_config()
    # Use `topics` list if present; fall back to single `topic` for compatibility.
    # `topics_override` (used by --batch units) takes precedence over both.
    topics = topics_override or config.get("topics") or [config["topic"]]
    sources_config = config.get("sources", {})
    scraping_config = config.get("scraping", {})

    if is_backfill and date_from and date_to:
        logger.info("Backfill mode: %s → %s", date_from, date_to)
        for name in sources_config:
            sources_config[name]["date_from"] = date_from.isoformat()
            sources_config[name]["date_to"] = date_to.isoformat()

    run_date = date.today()
    store = Store(db_path) if db_path else Store()
    all_analyses: list[GroupAnalysis] = []

    for topic in topics:
        logger.info("Ingesting topic=%r (backfill=%s)", topic, is_backfill)
        items = _stage_ingest(topic, sources_config, scraping_config)
        if not items:
            logger.warning("No items for topic=%r — skipping", topic)
            continue

        groups = _stage_group(items, config)
        if not groups:
            logger.info("No multi-source groups for topic=%r — skipping", topic)
            continue

        analyses = _stage_analyze(groups, config)
        if analyses:
            all_analyses.extend(analyses)
        else:
            logger.warning("All groups failed analysis for topic=%r", topic)

    if not all_analyses:
        logger.warning("No analyses produced across all topics — nothing to persist or deliver")
        return

    _stage_persist(all_analyses, store, run_date, is_backfill)
    if deliver:
        _stage_deliver(all_analyses, config, run_date)
    logger.info("Analysis run complete — %d group(s) across %d topic(s)", len(all_analyses), len(topics))


def seed_windows(date_from: date, date_to: date, window_days: int) -> list[tuple[date, date]]:
    """Split [date_from, date_to] (inclusive) into consecutive windows of at
    most `window_days` days. The final window is truncated at `date_to`.
    """
    if date_to < date_from:
        raise ValueError(f"--to ({date_to}) must not precede --from ({date_from})")
    if window_days < 1:
        raise ValueError(f"--window-days must be >= 1, got {window_days}")

    windows: list[tuple[date, date]] = []
    start = date_from
    while start <= date_to:
        end = min(start + timedelta(days=window_days - 1), date_to)
        windows.append((start, end))
        start = end + timedelta(days=1)
    return windows


def run_seed(
    date_from: date,
    date_to: date,
    window_days: int = 30,
    db_path: Path | None = None,
) -> None:
    """Seed the analysis timeline: run the backfill pipeline once per window.

    Idempotent — re-running the same range relies on the store's
    UNIQUE(topic, period_start, period_end) + INSERT OR IGNORE, so no
    duplicate analysis rows are created. A failed window is logged and the
    remaining windows still run.
    """
    windows = seed_windows(date_from, date_to, window_days)
    logger.info(
        "Seeding %d window(s) of %d day(s) from %s to %s",
        len(windows), window_days, date_from, date_to,
    )

    failures = 0
    for start, end in windows:
        try:
            # deliver=False: seeding persists history; per-window daily digests
            # would just overwrite each other at output/analysis-<today>.md.
            run_analysis(is_backfill=True, date_from=start, date_to=end,
                         db_path=db_path, deliver=False)
        except Exception:
            failures += 1
            logger.warning("Seed window %s → %s failed; continuing", start, end, exc_info=True)

    logger.info("Seeding complete: %d/%d window(s) succeeded", len(windows) - failures, len(windows))


# ---------- batch orchestration ----------

def load_batch_spec(spec_path: Path) -> tuple[list[tuple[str, date, date]], int]:
    """Parse a declarative batch spec into (topic, date_from, date_to) units.

    Spec format (YAML):
        topics:
          - "AI Tools"
          - "Data Engineering"
        windows:
          - {from: 2025-01-01, to: 2025-01-31}
          - {from: 2025-02-01, to: 2025-02-28}
        max_workers: 1   # optional; bounded unit parallelism (default 1)

    Units are the topics × windows cross product. Raises ValueError on a
    malformed spec — a bad spec aborts before any unit runs.
    """
    import yaml

    spec = yaml.safe_load(Path(spec_path).read_text())
    if not isinstance(spec, dict):
        raise ValueError(f"Batch spec must be a YAML mapping, got {type(spec).__name__}")

    topics = spec.get("topics")
    windows = spec.get("windows")
    if not topics or not isinstance(topics, list) or not all(isinstance(t, str) and t.strip() for t in topics):
        raise ValueError("Batch spec 'topics' must be a non-empty list of strings")
    if not windows or not isinstance(windows, list):
        raise ValueError("Batch spec 'windows' must be a non-empty list of {from, to} mappings")

    parsed_windows: list[tuple[date, date]] = []
    for i, w in enumerate(windows):
        if not isinstance(w, dict) or "from" not in w or "to" not in w:
            raise ValueError(f"Batch spec window #{i} must be a mapping with 'from' and 'to'")
        w_from, w_to = w["from"], w["to"]
        # yaml parses bare dates natively; accept ISO strings too
        w_from = w_from if isinstance(w_from, date) else date.fromisoformat(str(w_from))
        w_to = w_to if isinstance(w_to, date) else date.fromisoformat(str(w_to))
        if w_to < w_from:
            raise ValueError(f"Batch spec window #{i}: 'to' ({w_to}) precedes 'from' ({w_from})")
        parsed_windows.append((w_from, w_to))

    max_workers = spec.get("max_workers", 1)
    if not isinstance(max_workers, int) or max_workers < 1:
        raise ValueError(f"Batch spec 'max_workers' must be a positive int, got {max_workers!r}")

    units = [(t, w_from, w_to) for t in topics for w_from, w_to in parsed_windows]
    return units, max_workers


def run_batch(spec_path: Path, db_path: Path | None = None) -> tuple[int, int]:
    """Run the analysis pipeline for every (topic, window) unit in the spec.

    Resilient and resumable:
    - each unit is isolated — a failure logs and the batch continues
    - unit parallelism is bounded by the spec's max_workers (default 1,
      sequential, to stay inside arXiv rate limits; source-level fetches
      within a unit keep their existing ThreadPoolExecutor parallelism)
    - re-running the same spec is idempotent via the store's
      UNIQUE(topic, period_start, period_end) + INSERT OR IGNORE

    Returns (succeeded, failed). Raises RuntimeError only if *every* unit
    failed — mirroring the total-source-failure abort semantics.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    units, max_workers = load_batch_spec(spec_path)
    logger.info("Batch: %d unit(s), max_workers=%d, spec=%s", len(units), max_workers, spec_path)

    def _run_unit(topic: str, w_from: date, w_to: date) -> None:
        # deliver=False: like seeding, batch runs persist history; per-unit
        # digests would overwrite each other at output/analysis-<today>.md.
        run_analysis(
            is_backfill=True, date_from=w_from, date_to=w_to,
            db_path=db_path, deliver=False, topics_override=[topic],
        )

    failed = 0
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(_run_unit, topic, w_from, w_to): (topic, w_from, w_to)
            for topic, w_from, w_to in units
        }
        for future in as_completed(futures):
            topic, w_from, w_to = futures[future]
            try:
                future.result()
                logger.info("Batch unit ok: %r %s → %s", topic, w_from, w_to)
            except Exception:
                failed += 1
                logger.warning(
                    "Batch unit failed: %r %s → %s — continuing", topic, w_from, w_to, exc_info=True,
                )

    succeeded = len(units) - failed
    logger.info("Batch complete: %d/%d unit(s) succeeded", succeeded, len(units))
    if units and succeeded == 0:
        raise RuntimeError(f"All {len(units)} batch units failed")
    return succeeded, failed


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
    mode.add_argument("--seed", action="store_true", help="Seed the timeline: backfill across consecutive windows")
    mode.add_argument("--batch", metavar="SPEC_YAML", help="Run a declarative (topic × window) batch spec")
    mode.add_argument("--timeline", metavar="TOPIC", help="Render the stored timeline for a topic")

    parser.add_argument("--from", dest="date_from", metavar="YYYY-MM-DD", help="Backfill/seed start date")
    parser.add_argument("--to", dest="date_to", metavar="YYYY-MM-DD", help="Backfill/seed end date")
    parser.add_argument("--window-days", type=int, default=30, metavar="N",
                        help="Seed window size in days (default: 30)")

    args = parser.parse_args()

    if args.timeline:
        run_timeline(args.timeline)
    elif args.batch:
        run_batch(Path(args.batch))
    elif args.backfill or args.seed:
        flag = "--seed" if args.seed else "--backfill"
        if not args.date_from or not args.date_to:
            parser.error(f"{flag} requires --from and --to")
        date_from = date.fromisoformat(args.date_from)
        date_to = date.fromisoformat(args.date_to)
        if args.seed:
            run_seed(date_from, date_to, window_days=args.window_days)
        else:
            run_analysis(is_backfill=True, date_from=date_from, date_to=date_to)
    else:
        run_analysis()


if __name__ == "__main__":
    main()
