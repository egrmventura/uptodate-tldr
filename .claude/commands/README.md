# Goal Prompts — Development Loop

Single-responsibility, implementation-ready goal prompts for the next build loop.
Each is a slash command (`/goal-<name>`) describing what to build, the key
constraint, and the test that proves it works.

## Recommended order

Prompts are sequenced by dependency:

1. **`goal-scraper`** — Full-text article scraper (URL → title, author, date, body).
   Foundation for richer analysis; no dependencies.
2. **`goal-rss`** — RSS/Atom feed source via `feedparser`. Independent of the scraper;
   can run in parallel with (1).
3. **`goal-scraper-wire`** — Wire the scraper into the ingestion stage as optional,
   best-effort enrichment. Depends on `goal-scraper`.
4. **`goal-timeline-seed`** — Seed the analysis timeline with real historical data.
   Benefits from richer sources (2, 3) before backfilling.
5. **`goal-auto-discovery`** — Replace the dual `_SOURCES`/`config.yaml` registry with
   auto-discovery. A refactor best done last, once the source list is stable.

## Orchestration & workflow commands

Cross-cutting commands, not tied to a single build target:

- **`goal-batch-orchestration`** — resilient, resumable batch runner over many
  (topic × date-window) units in one invocation.
- **`summarize`** — produce/refresh a TLDR digest on demand for a topic.
- **`goal-pipeline-glue`** — tighten the hand-off contracts between pipeline stages.
- **`goal-resilience-pass`** — audit every I/O and LLM boundary for tested failure handling.
- **`goal-test-eval`** — fix the pre-existing fixture errors and add an offline LLM-output eval harness.
- **`iterate`** — tight refine loop on the current diff until it meets its goal.
- **`session-status`** — write `STATUS.md` at the end of a session for context restoration.

## The STATUS.md method

`session-status` writes a short, skimmable `STATUS.md` at the repo root summarizing
what's done, what's pending (with the next concrete step), and known issues — using
the same module vocabulary as `ARCHITECTURE.md` and `CLAUDE.md` so a fresh session can
restore context in one read. Run it at the end of each working session.

## Constraints inherited by every prompt

- Sources must never raise — log and return `[]` per the `Source` ABC contract.
- New sources register in **both** `_SOURCES` (`main.py`) and `config.yaml` until
  `goal-auto-discovery` lands.
- Tests run offline against saved fixtures — no network in the test suite.
