# STATUS

_Last updated: 2026-07-01_

## Where things stand

- **Branch:** `feature/scraper-wire` (PR pending to `staging`)
- **`staging` HEAD:** `db59dbc` — Merge PR #13 (RSS/Atom source)

## Done

- **Comparative analysis pipeline** (`analyze.py`) merged to `staging` (PR #6): `ingest → group → analyze → persist → deliver`, parallel to the untouched TLDR pipeline in `main.py`. Modules: `grouper.py`, `analyst.py`, `store.py` (SQLite at `output/analyses.db`), `timeline.py`, `delivery/analysis_md.py`, `delivery/timeline_md.py`.
- **Analyst token fix:** `max_tokens` scales dynamically `min(1500 + n_items * 300, 3000)`. Documented in `CLAUDE.md`.
- **Goal-prompt command files** (PR #9) and **orchestration/workflow commands + STATUS.md method** (PR #10) merged under `.claude/commands/`.
- **`goal-test-eval`** (PR #11): fixed the 4 pytest fixture errors via `topic`/`config` fixtures; added `eval_harness.py` (offline LLM-output eval). Suite fully green.
- **`goal-scraper`** (PR #12): `scraper.py` — URL → title/author/date/body, strips boilerplate, never raises, paywalled/blocked → `None`. 3 offline HTML fixtures + mocked-network tests.
- **`goal-rss`** (PR #13): `sources/rss.py` — feedparser-backed Atom/RSS source, mapped to `Item`, dual-registered (`_SOURCES` + `config.yaml`, disabled by default). 3 offline feed fixtures.
- **`goal-scraper-wire` (this session):** wired the scraper into `ingest()` as optional best-effort enrichment (`enrich_items`), gated by `scraping.enabled`, running through `ThreadPoolExecutor`. Attaches full body to `item.extra["body"]`; blocked/failed fetches leave the excerpt intact; both `main.py` and `analyze.py` pass scraping config. **Suite: 42 passed.**

## Pending / next

- **Timeline never seeded** with real historical data. → run `/goal-timeline-seed` (or `--backfill`).
- **Source auto-discovery** still a dual registry (`_SOURCES` in `main.py` + `config.yaml`). → run `/goal-auto-discovery` last.
- **Downstream body adoption:** enrichment populates `item.extra["body"]`, but grouper/analyst/summarizer still read `summary_raw`. A future `/goal-pipeline-glue` pass could route `extra["body"]` into those formatters for richer analysis.

## Known issues

- arXiv returns HTTP 429 under rapid repeated runs; `safe_fetch` returns `[]` and the pipeline continues. Clears after a few hours.
- Local git identity is auto-derived (`MATTHEW VENTURA <...@MATTHEWs-MBP...>`); set `user.name`/`user.email` if you want clean authorship.

## Recommended next command

`/goal-timeline-seed` — seed the analysis timeline with historical backfill now that sources (HN, arXiv, RSS) and full-text enrichment are in place.
