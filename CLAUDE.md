# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Token Conservation

- Do not spawn subagents unless the user explicitly asks for them or names an agent type.
- Maximum 2 parallel agents at any time.
- Prefer inline work (grep, Read, Edit) over spawning Explore agents for simple lookups.
- Do not use MCP tools (Gmail, Google Drive, Google Calendar) unless the user specifically requests them.
- Do not load deferred tool schemas unless needed for the current task.
- Keep effort level consistent with the global setting — do not escalate on your own.

## Commands

```bash
# Run the pipeline immediately
python main.py --run-now

# Start the daily scheduler (blocks; prefers cron + --run-now in prod)
python main.py

# Run all tests
python -m pytest test_pipeline.py -v

# Run a single test
python -m pytest test_pipeline.py -v -k "test_name"
```

No build or lint step is configured. Install deps with `pip install -r requirements.txt`.

## Architecture

The pipeline runs in four sequential stages: **ingest → rank → summarize → deliver**.

**`main.py`** owns the orchestration. Sources are auto-discovered from the `sources/` package (`sources/discovery.py`): any concrete `Source` subclass defined there is found at startup, but only instantiated if its `name` is enabled in `config.yaml`'s `sources:` section — the config is the single registry. Adding a new source = drop a module in `sources/` + add a config entry. Sources are fetched in parallel via `ThreadPoolExecutor`. A source failure is isolated (returns `[]`); total source failure aborts the run.

**`sources/base.py`** defines the shared `Item` dataclass and the `Source` ABC. Every source must implement `fetch(topic, config) -> list[Item]` and must never raise — all I/O belongs in a try/except that logs and returns `[]`. `safe_fetch` wraps `fetch` as a final backstop. `parse_timestamp()` is a shared utility here.

**`ranker.py`** scores items with: `recency_weighted_score + citation_weight * citations`, then applies a `cross_source_bonus` multiplier if the same story appears in 2+ sources. Cross-source dedup groups by normalized title (lowercased, punctuation stripped), falling back to exact URL.

**`summarizer.py`** calls the Anthropic API. The persona (voice/tone) is a config-only system prompt — changing how the digest sounds is a `config.yaml` edit, not a code change. Summarization failure raises (unlike source failure) because there is nothing to deliver without a digest.

**`config.py`** merges `config.yaml` with env var overrides (`TOPIC`, `TOP_N`, `PERSONA_PROMPT`). Adding a new overridable key means adding an entry to `_ENV_OVERRIDES`.

**`delivery/`** modules (`markdown`, `email`, `substack`) each expose `deliver(digest_markdown, topic, config, run_date)`. Channel failures are isolated; if every enabled channel fails the run exits non-zero.

**`scheduler.py`** is an APScheduler wrapper around `run_pipeline`. Prefer `cron + python main.py --run-now` in server/container environments.

## Analysis Pipeline (`analyze.py`)

A parallel entrypoint that runs **ingest → group → analyze → persist → deliver**. `main.py` is untouched.

**`grouper.py`** — LLM assigns canonical, stable labels to articles. Singletons (no matching peer) are dropped. Uses `max_tokens=1024`; grouping responses are short JSON.

**`analyst.py`** — LLM produces per-group compare/contrast JSON: `agreements`, `contradictions`, `debunks`, `unresolved`. `max_tokens` scales dynamically: `min(1500 + n_items * 300, 3000)` — this was validated after a truncation failure at the fixed 1500 limit. Do not lower this formula without testing on groups of 5+ items.

**`store.py`** — SQLite at `output/analyses.db`. Owns the `GroupAnalysis` dataclass (imported by `analyst.py` to avoid circular imports). Idempotent via `UNIQUE(topic, period_start, period_end) + INSERT OR IGNORE`. `period_start`/`period_end` use article publication dates, not run date — essential for backfill correctness.

**`timeline.py` / `delivery/timeline_md.py`** — Render stored history for a topic chronologically by `period_start`.

**`delivery/analysis_md.py`** — Daily digest; output at `output/analysis-YYYY-MM-DD.md`.

### `analyze.py` modes
```bash
python analyze.py --run-now
python analyze.py --backfill --from 2024-01-01 --to 2025-01-01
python analyze.py --seed --from 2024-01-01 --to 2025-01-01 --window-days 30
python analyze.py --batch spec.yaml
python analyze.py --timeline "Anthropic MCP"
```

`--seed` splits the range into consecutive `--window-days` windows and runs the backfill pipeline per window. Idempotent (store's `UNIQUE + INSERT OR IGNORE`); a failed window logs and continues; digest delivery is skipped (seeding persists history only).

`--batch` runs the topics × windows cross product from a declarative YAML spec (see `batch.example.yaml`). Units are isolated (one failure logs and continues; all-units failure raises), parallelism is bounded by the spec's `max_workers` (default 1 — keep sequential for arXiv rate limits), and re-running a spec is idempotent. Like `--seed`, digest delivery is skipped.

### LLM token budget rules
- Grouper: fixed 1024 (grouping JSON is compact).
- Analyst: dynamic `min(1500 + n_items * 300, 3000)`. Increase the cap (3000) only if groups regularly exceed 6 items with long excerpts; stay ≤ 4096.
- If JSON is still truncated at the cap, shorten per-item excerpts in `_format_items` before raising the cap further.
- Both modules strip markdown code fences (`_strip_fences`) before parsing — the model ignores "no fences" instructions intermittently.

### Resilience rules (`resilience.py`)
- Transient failures (429/5xx, timeouts, connection drops, Anthropic rate limits/overload) are retried with exponential backoff via `retry_with_backoff` (3 attempts, 1s base). Permanent failures (4xx, auth, parse) are never retried.
- Wired at: HN + arXiv fetches, and all three Anthropic call sites (grouper/analyst/summarizer). After retries are exhausted, each caller keeps its documented contract: sources log-and-return-`[]`, grouper returns `[]`, analyst returns `None` (group skipped), summarizer raises.
- Deliberately not retried: RSS (feedparser captures errors in `bozo`), scraper enrichment (per-item best-effort; failures are mostly paywalls), SQLite (handled by `PRAGMA busy_timeout` in `store.py`, default 5s; a still-locked write raises and `_conn` rolls back).
- No bare `except: pass` anywhere; every swallowed exception logs with context.

### Known limitations
- arXiv returns HTTP 429 under rapid repeated runs; it is retried with backoff, then `safe_fetch` returns `[]` and the pipeline continues. A sustained block clears after a few hours.
- The LLM model used is set via `config.yaml → llm.model`; defaults to `claude-sonnet-4-6`.

## Project Constraints

- Python 3.12, flat layout at repo root.
- All secrets live in `.env` (symlinked outside repo). Never read `.env` contents into conversation.
- LinkedIn source is disabled by default and documented as fragile — do not enable it without a working RapidAPI key.
- Reddit source was permanently removed (June 2026); do not re-add without confirmed API access.
- Branching: cut from `staging`, PR back to `staging`. Never open PRs directly to `main`.
- Sources are auto-discovered (`sources/discovery.py`); `config.yaml`'s `sources:` section is the single registry. A source absent from config (or `enabled: false`) is never instantiated. Adding a source = new module in `sources/` + a config entry.
