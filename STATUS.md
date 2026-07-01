# STATUS

_Last updated: 2026-06-30_

## Where things stand

- **Branch:** `feature/orchestration-commands` (PR pending to `staging`)
- **`staging` HEAD:** `2c5f811` — Merge PR #9 (goal-prompt command files)

## Done

- **Comparative analysis pipeline** (`analyze.py`) merged to `staging` (PR #6): `ingest → group → analyze → persist → deliver`, parallel to the untouched TLDR pipeline in `main.py`. Modules: `grouper.py`, `analyst.py`, `store.py` (SQLite at `output/analyses.db`), `timeline.py`, `delivery/analysis_md.py`, `delivery/timeline_md.py`.
- **Analyst token fix:** `max_tokens` scales dynamically `min(1500 + n_items * 300, 3000)` — resolved the truncation that skipped large groups. Documented in `CLAUDE.md`.
- **Goal-prompt command files** merged (PR #9): `goal-scraper`, `goal-rss`, `goal-scraper-wire`, `goal-timeline-seed`, `goal-auto-discovery`, plus `.claude/commands/README.md`.
- **This session:** added orchestration/workflow commands — `goal-batch-orchestration`, `summarize`, `goal-pipeline-glue`, `goal-resilience-pass`, `goal-test-eval`, `iterate`, `session-status` — and this `STATUS.md` method.

## Pending / next

- **Fix 4 pre-existing pytest fixture errors** (`test_config_topic`, `test_hn_source`, `test_arxiv_source`, `test_e2e_ingest_and_rank` expect undefined `topic`/`config` fixtures). Currently 23 pass / 4 error. → run `/goal-test-eval`.
- **Full-text scraping** not yet built. → run `/goal-scraper`, then `/goal-scraper-wire`.
- **RSS source** not yet built. → run `/goal-rss`.
- **Timeline never seeded** with real historical data. → run `/goal-timeline-seed` (or `--backfill`).
- **Source auto-discovery** still a dual registry (`_SOURCES` in `main.py` + `config.yaml`). → run `/goal-auto-discovery` last.

## Known issues

- arXiv returns HTTP 429 under rapid repeated runs; `safe_fetch` returns `[]` and the pipeline continues. Clears after a few hours.
- Local git identity is auto-derived (`MATTHEW VENTURA <...@MATTHEWs-MBP...>`); set `user.name`/`user.email` if you want clean authorship.

## Recommended next command

`/goal-test-eval` — get the suite fully green before building new sources.
