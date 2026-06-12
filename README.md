# uptodate-tldr

A configurable daily content-intelligence pipeline: scrape what's trending
on a topic across multiple sources, rank it by a composite signal score,
summarize the top items with an LLM in a tunable voice, and ship the result
to one or more delivery channels — markdown file, email, or a Substack
draft.

## The problem

Staying current on a fast-moving topic (AI research, a specific tech stack,
an industry) means checking several feeds a day — Hacker News, relevant
subreddits, arXiv, LinkedIn — and most of what's there is noise. This
project automates the "first pass": pull what's currently getting attention
across sources, collapse duplicates, rank by actual signal (not just
recency or just raw score), and produce a short, opinionated digest of the
handful of items worth a human's attention.

It's built to be a "set TOPIC and forget it" tool — every source, the
ranking weights, the LLM persona, and the delivery targets are config, not
code.

## Architecture

```
sources/        one module per content source, each implementing
                 Source.fetch(topic, config) -> list[Item]
ranker.py        merges items from all sources, dedupes cross-source
                 stories, scores by composite signal, returns top N
summarizer.py    sends top N to Claude (claude-sonnet-4-6) with a
                 persona-configured system prompt, returns digest markdown
delivery/        one module per output channel, each implementing
                 deliver(digest_markdown, topic, config, run_date)
main.py          orchestrates ingest -> rank -> summarize -> deliver
scheduler.py     APScheduler wrapper that runs main.run_pipeline daily
config.py        loads config.yaml, applies env var overrides
```

### Why these four sources

- **Hacker News (Algolia API)** — free, unauthenticated, stable, and a
  reliable proxy for "the tech industry is currently talking about this."
  Chosen as the reference implementation because it's the lowest-risk
  integration in the project; if you're adding a fifth source, this is the
  module to copy.
- **Reddit** — broader and noisier than HN, but covers topics HN doesn't
  (e.g. niche subreddits for a specific tool or community). Supports both
  PRAW (authenticated, recommended) and Reddit's public `.json` endpoints
  (unauthenticated, rate-limited, useful for quick testing).
- **arXiv** — the only source with a *quality* signal independent of social
  engagement (citations, eventually). Important for technical topics where
  "what's trending on social media" and "what's actually a significant
  result" diverge.
- **LinkedIn** — included because professional/industry commentary often
  surfaces stories before they hit HN/Reddit, but it's the least stable
  integration by a wide margin (see Known Limitations). **Disabled by
  default.**

### How ranking works

Every item gets a composite score:

```
score = Σ over sources reporting this story of:
            (engagement_score * recency_decay) + (citation_weight * citations)
        then × cross_source_bonus if 2+ distinct sources reported it
```

- **Recency decay** is exponential with a configurable half-life
  (`ranking.recency_half_life_hours`, default 24h). A 500-point HN post from
  6 hours ago should usually beat a 600-point post from yesterday; a flat
  cutoff (e.g. "only last 24h") would either miss the slow-burn story or
  treat a 23-hour-old post the same as a 1-hour-old one.
- **Cross-source bonus** (`ranking.cross_source_bonus`, default 1.5×): if
  the same story (matched by exact URL or normalized title) appears on, say,
  both HN and Reddit, that's a stronger signal than either platform alone.
  Matching is intentionally simple — exact URL or whitespace/punctuation-
  normalized title — rather than fuzzy/embedding-based, trading some recall
  for predictability and zero extra dependencies/cost.
- **Citation weight** (`ranking.citation_weight`, default 2.0): arXiv papers
  don't have an "upvote" analog, so their score is driven by citation count
  instead. As shipped, the arXiv API doesn't return citation counts, so this
  is currently a no-op — see Known Limitations.

This is a heuristic, not a learned ranking model, by design: it's legible
(you can explain why item X beat item Y), has zero training/maintenance
cost, and the three weights are config knobs you can tune per-topic without
touching code.

### Why the persona is configurable

The summarization step is the part most likely to need iteration — "direct
and opinionated" might be exactly right for one topic and too brusque for
another (e.g. a digest meant for external readers). Putting the persona
entirely in the system prompt (`persona.prompt` in config.yaml, or
`PERSONA_PROMPT` env var) means tone changes are a config edit + redeploy,
not a code change — and the same pipeline can run multiple times with
different personas/topics for different audiences.

## Setup

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# edit .env: at minimum set ANTHROPIC_API_KEY
```

Run once immediately:

```bash
python main.py --run-now
```

Run the daily scheduler (long-running process):

```bash
python main.py
```

## Configuration reference

All settings live in `config.yaml`; most can be overridden by environment
variables (see `.env.example`). Key fields:

| Key | Description |
| --- | --- |
| `topic` | Search/filter string applied to every source. Override with `TOPIC` env var. |
| `top_n` | Number of items to summarize (2–6 recommended). |
| `sources.<name>.enabled` | Toggle each source independently. |
| `sources.reddit.subreddits` | Subreddits to search in addition to topic search. |
| `sources.arxiv.category` | arXiv category to scope results (e.g. `cs.AI`, `cs.LG`). |
| `ranking.*` | Recency half-life, cross-source bonus, citation weight (see above). |
| `persona.prompt` | System prompt defining the digest's voice. Override with `PERSONA_PROMPT` env var. |
| `llm.model` / `llm.max_tokens` | Anthropic model and output budget. |
| `delivery.<channel>.enabled` | Toggle markdown / email / Substack independently; any combination can run. |
| `schedule.daily_time` | 24h local time for the scheduler to run the pipeline. |

## Known limitations

- **LinkedIn scraping is fundamentally fragile.** There is no public
  LinkedIn API for this use case. `sources/linkedin.py` uses a RapidAPI
  scraper endpoint, configured via `RAPIDAPI_KEY`/`RAPIDAPI_HOST`, and is
  **disabled by default**. Any such provider is scraping an interface
  LinkedIn doesn't support and can break without notice. The module's
  contract (`fetch(topic, config) -> list[Item]`) is the only thing other
  code depends on — swapping to a different RapidAPI host, an Apify actor,
  or a cookie-based session scraper means editing only this file.
- **arXiv citation counts are not implemented.** The arXiv API doesn't
  expose citation counts, so `extra["citations"]` is always 0 and
  `ranking.citation_weight` is currently inert for arXiv items. To make this
  signal real, add a lookup against a citation API (e.g. Semantic Scholar's
  `/graph/v1/paper/{arxiv_id}` endpoint) inside `sources/arxiv.py` and
  populate `extra["citations"]` — no other module needs to change.
- **Cross-source deduplication is exact/near-exact**, not semantic. Two
  articles covering the same underlying story with different titles and
  URLs (e.g. a press release vs. a blog post about it) won't be merged, and
  won't receive the cross-source bonus. A semantic approach (embedding
  similarity) would catch more of these at the cost of an extra model call
  per run and less predictable/explainable matching.
- **Substack delivery uses an undocumented, unofficial API** that requires
  manually extracting a session cookie from a browser (`SUBSTACK_COOKIE`).
  It's the most likely channel to silently break (expired cookie, changed
  endpoint shape) and is disabled by default; treat it as best-effort.
- **The Reddit public-JSON fallback** (used when `REDDIT_CLIENT_ID`/`SECRET`
  aren't set) is unauthenticated and aggressively rate-limited by Reddit —
  fine for local testing, not recommended for a scheduled daily run.

## Extending with a new source

1. Create `sources/<name>.py` with a class extending `sources.base.Source`,
   setting `name` and implementing `fetch(self, topic, config) -> list[Item]`.
   Catch all exceptions internally (or rely on `safe_fetch`) and return `[]`
   on failure — one bad source must never abort the run.
2. Map every result into the shared `Item` schema (`source`, `title`, `url`,
   `score`, `published_at`, `summary_raw`, optional `extra` dict). `score`
   should be whatever engagement metric is most comparable to upvotes/points
   for that platform.
3. Register the source in `main.py`'s `_SOURCES` dict.
4. Add a `sources.<name>` block to `config.yaml` (at minimum `enabled` and
   any source-specific knobs like `max_results`), and document any required
   env vars in `.env.example`.

No changes to `ranker.py`, `summarizer.py`, or `delivery/` are needed — they
operate purely on the `Item` schema.
