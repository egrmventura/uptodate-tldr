# STATUS

_Last updated: 2026-07-01_

## Where things stand

- **Branch:** `feature/test-eval` (PR pending to `staging`)
- **`staging` HEAD:** `d08192c` — Merge PR #10 (orchestration commands + STATUS.md)

## Done

- **Comparative analysis pipeline** (`analyze.py`) merged to `staging` (PR #6): `ingest → group → analyze → persist → deliver`, parallel to the untouched TLDR pipeline in `main.py`. Modules: `grouper.py`, `analyst.py`, `store.py` (SQLite at `output/analyses.db`), `timeline.py`, `delivery/analysis_md.py`, `delivery/timeline_md.py`.
- **Analyst token fix:** `max_tokens` scales dynamically `min(1500 + n_items * 300, 3000)` — resolved the truncation that skipped large groups. Documented in `CLAUDE.md`.
- **Goal-prompt command files** merged (PR #9): `goal-scraper`, `goal-rss`, `goal-scraper-wire`, `goal-timeline-seed`, `goal-auto-discovery`, plus `.claude/commands/README.md`.
- **Orchestration/workflow commands** merged (PR #10): `goal-batch-orchestration`, `summarize`, `goal-pipeline-glue`, `goal-resilience-pass`, `goal-test-eval`, `iterate`, `session-status`, plus the `STATUS.md` method.
- **`goal-test-eval` executed (this session):** fixed the 4 pytest fixture errors via `topic`/`config` fixtures; suite is now **28 passed, 0 errors, 0 warnings** (script mode 94/94). Added `eval_harness.py` — offline LLM-output eval scoring grouper/analyst parsing against recorded responses (8/8), wired into pytest via `test_eval_harness_all_pass`.

## Pending / next

- **Full-text scraping** not yet built. → run `/goal-scraper`, then `/goal-scraper-wire`.
- **RSS source** not yet built. → run `/goal-rss`.
- **Timeline never seeded** with real historical data. → run `/goal-timeline-seed` (or `--backfill`).
- **Source auto-discovery** still a dual registry (`_SOURCES` in `main.py` + `config.yaml`). → run `/goal-auto-discovery` last.

## Known issues

- arXiv returns HTTP 429 under rapid repeated runs; `safe_fetch` returns `[]` and the pipeline continues. Clears after a few hours.
- Local git identity is auto-derived (`MATTHEW VENTURA <...@MATTHEWs-MBP...>`); set `user.name`/`user.email` if you want clean authorship.

## Recommended next command

`/goal-scraper` — build the full-text article scraper now that the suite is green; then `/goal-rss` (parallel) and `/goal-scraper-wire`.
