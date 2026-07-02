# STATUS

_Last updated: 2026-07-01 (evening session)_

## Where things stand

- **Branch:** `feature/auto-discovery` (top of a 5-PR stack; `staging` is the merge target)
- **Tests:** 60 passed (offline; `python3 -m pytest test_pipeline.py`)
- **Awaiting human review/merge, in order:** PR #15 → #16 → #17 → #18 → #19 (each stacked on the previous; diffs collapse as predecessors land)

## Done this session (all 5 pending items)

1. **`goal-timeline-seed`** (PR #15): `python analyze.py --seed --from A --to B [--window-days N]` — splits the range into consecutive windows, runs the backfill pipeline per window. Idempotent via store `UNIQUE + INSERT OR IGNORE`; failed window logs and continues; digest delivery skipped. `run_analysis` gained `db_path`/`deliver` params.
2. **`goal-pipeline-glue`** (PR #16): `run_analysis` refactored into a linear typed stage sequence (`_stage_ingest/_group/_analyze/_persist/_deliver`); `_check_handoff` raises `TypeError` on contract violations. Behavior preserved exactly; seed-test fakes corrected to real contracts (`list[TopicGroup]`).
3. **`goal-batch-orchestration`** (PR #17): `python analyze.py --batch spec.yaml` — topics × windows cross product from a declarative spec (`batch.example.yaml`); unit isolation, bounded parallelism (`max_workers`, default 1), idempotent re-runs, all-units-failure raises. `run_analysis` gained `topics_override`.
4. **`goal-resilience-pass`** (PR #18): `resilience.py` — `retry_with_backoff` + transient classifiers (requests/arxiv/anthropic), wired at HN/arXiv fetches and all three Anthropic call sites; `PRAGMA busy_timeout` in store. Post-retry contracts unchanged. Fault-injection tests (timeout, 429, malformed LLM JSON, locked db).
5. **`goal-auto-discovery`** (PR #19): `sources/discovery.py` — `Source` subclasses auto-discovered from `sources/`; `config.yaml` is the single registry; disabled/unconfigured sources never instantiated; `_SOURCES` dict removed from `main.py`.

## Pending / next

- **Merge the PR stack** (#15 → #19, in order) into `staging`. All are review-gated (agent cannot merge).
- **Run a real seed** once merged: `python analyze.py --seed --from 2026-01-01 --to 2026-07-01 --window-days 30` (or drive `--batch` with a spec) to populate `output/analyses.db` with live history.
- **Downstream body adoption** still open: enrichment populates `item.extra["body"]`, but grouper/analyst/summarizer formatters still read `summary_raw`.

## Known issues

- arXiv 429 under rapid repeated runs — now retried with backoff, then isolated (`[]`); sustained blocks clear after a few hours.
- Local git identity is auto-derived (`MATTHEW VENTURA <...@MATTHEWs-MBP...>`); set `user.name`/`user.email` for clean authorship.

## Recommended next command

Review & merge PRs #15–#19 (in order), then `python analyze.py --seed` against a real date range.
