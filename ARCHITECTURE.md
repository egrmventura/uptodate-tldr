# ARCHITECTURE.md — uptodate-tldr: Comparative Analysis Extension

## Goal

Extend the existing scraping pipeline to serve two distinct purposes:

1. **Daily digest** — blunt, TLDR compare/contrast on what is being said *right now* across AI, ML, and Data Engineering topics, organized by topic group rather than individual article.

2. **Topic timeline** — a persistent, queryable record of how the consensus on a specific topic (e.g. "Anthropic MCP") has evolved across time. This is the core value: in fast-moving fields, today's truth often directly contradicts last month's truth. The timeline makes that visible.

Timelines are seeded with a one-time **historical backfill** — a deeper scrape of older articles that establishes static foundation points. The daily pipeline then builds dynamic entries on top of that foundation.

---

## How it extends the existing pipeline

The current flow:
```
ingest → rank (top N items) → summarize (per-item TLDR) → deliver
```

The new flow branches after ingest:
```
ingest → group (by topic) → analyze (per group: agree / contradict / debunk) → persist → deliver
                                                                                    ↓
                                                                             timeline view
```

The existing `Source`, `Item`, and `safe_fetch` contract is unchanged. The ranking step is replaced by grouping. The summarizer is replaced (or augmented) by an analyst.

---

## New modules

### `grouper.py` — `list[Item]` → `list[TopicGroup]`

Takes all ingested items and clusters them into topic groups. Each group contains 2+ items that address the same underlying claim, story, or question.

**Implementation approach:** Ask the LLM to assign each item a canonical topic label and return a grouped structure. LLM-based grouping handles paraphrase better than the existing title-normalization dedup in `ranker.py`, and topic labels must be stable across runs (e.g. always "Anthropic MCP", never "Claude MCP integration") so that timeline continuity can be maintained in the store.

```python
@dataclass
class TopicGroup:
    label: str                              # canonical, stable topic name
    items: list[Item]
    date_range: tuple[datetime, datetime]
```

Singleton items (no match found) are dropped by default — they carry no comparative signal.

### `analyst.py` — `TopicGroup` → `GroupAnalysis`

Produces the structured analysis for one topic group. The prompt instructs the model to:
1. Identify the core claim or question the group addresses.
2. Enumerate what sources **agree** on.
3. Enumerate **contradictions** — where sources make conflicting factual claims.
4. Flag **debunks** — where one source explicitly refutes another.
5. Note **unresolved tensions** — disagreements that can't be resolved from available evidence.

```python
@dataclass
class GroupAnalysis:
    topic: str
    run_date: date
    agreements: list[str]
    contradictions: list[str]
    debunks: list[str]
    unresolved: list[str]
    sources: list[Item]         # originating items, for citation links
```

`run_date` is the field that enables the timeline — every analysis record is stamped and stored.

### `store.py` — SQLite persistence

Persists `GroupAnalysis` records across runs. Required (not optional) because the timeline view depends on querying historical analyses by topic.

Schema (two tables):
- `runs(id, run_date, is_backfill)` — one row per pipeline execution; `is_backfill` distinguishes seed runs from daily runs
- `analyses(id, run_id, topic, period_start, period_end, agreements_json, contradictions_json, debunks_json, unresolved_json, sources_json)` — one row per topic group per run

`period_start` / `period_end` are the publication date range of the source articles in that group — **not** the date the pipeline ran. This is what makes backfill records accurate: 2024 content is stamped 2024, not the day the seed job ran.

Primary query patterns:
- All analyses for a given topic, ordered by `period_start` → timeline view (chronological by content date)
- All analyses for a given run → daily digest

### `timeline.py` — topic history view

Queries `store.py` for all `GroupAnalysis` records for a given topic and renders a chronological view showing how the consensus has shifted. The reader can see, for example, that in April sources agreed MCP was experimental, in May they contradicted each other on adoption, and in June one source explicitly debunked an earlier claim.

---

## Folder structure (additions only)

```
grouper.py              # Item[] → TopicGroup[]
analyst.py              # TopicGroup → GroupAnalysis
store.py                # SQLite read/write for GroupAnalysis records
timeline.py             # renders per-topic history from store
analyze.py              # entrypoint: python analyze.py --run-now
                        #             python analyze.py --timeline "Anthropic MCP"
delivery/
  analysis_md.py        # daily digest: renders GroupAnalysis list to markdown
  timeline_md.py        # timeline: renders topic history to markdown
output/
  analyses.db           # SQLite store (gitignored)
```

The existing `main.py` / `summarizer.py` / `ranker.py` are untouched — both pipelines coexist.

---

## Output formats

**Daily digest** (`delivery/analysis_md.py`):
```markdown
## Anthropic MCP  ·  3 sources  ·  Jun 29

**Agreement**
- All sources confirm MCP is now stable in Claude 3.7+.

**Contradictions**
- HackerNews claims adoption is widespread; arXiv study finds <5% of production deployments use it.

**Debunks**
- [arXiv:2506.xxxxx] directly refutes the "MCP replaces function calling" claim in [HN post].

**Unresolved**
- Whether MCP performance overhead is acceptable at scale is not addressed by any source.

Sources: [title](url), [title](url), [title](url)
```

**Timeline view** (`delivery/timeline_md.py`):
```markdown
# Topic Timeline: Anthropic MCP

## Jun 29, 2026
**Agreement:** MCP now stable in Claude 3.7+.
**Contradictions:** Adoption claims conflict.

## May 14, 2026
**Agreement:** MCP in beta, experimental use recommended.
**Unresolved:** Production readiness unknown.

## Apr 2, 2026
**Contradictions:** Sources disagree whether MCP supersedes function calling.
**Debunks:** Anthropic blog refutes third-party benchmark claims.
```

---

## Key decisions

| Decision | Choice | Reason |
|----------|--------|--------|
| Grouping method | LLM-based with canonical labels | Stable labels are required for cross-run topic continuity |
| Persistence | SQLite (required) | Timeline view is core, not optional — needs cross-run query |
| Timeline date field | `period_start`/`period_end` (article dates, not run date) | Backfill records must reflect when content was written, not when the pipeline ran |
| Singleton handling | Drop by default | No comparative signal without 2+ sources |
| Scraping libraries | Unchanged | Sources return structured data; no raw HTML scraping needed |
| Backfill idempotency | Skip existing records for same topic + period | Re-running a date range should not duplicate entries |
| Existing pipeline | Untouched | TLDR flow and analysis flow coexist independently |

---

## Backfill mode

Sources that support date-range queries (HackerNews Algolia, arXiv) will accept a `date_from` / `date_to` parameter in their config when running in backfill mode. The entrypoint exposes this as:

```
python analyze.py --backfill --from 2024-01-01 --to 2025-01-01
```

Backfill runs stamp analyses with the article publication date range (`period_start`/`period_end`), not today's date. They are marked `is_backfill=True` in the `runs` table so they can be distinguished from live daily runs. A backfill run is intended to be done once per date range — re-running the same range is idempotent (existing records for that period are not duplicated).

---

## What to build first

1. `grouper.py` — validate that LLM-assigned topic labels are stable and consistent across runs before building anything that depends on them.
2. `store.py` — schema and read/write before analyst, so analyses can be persisted from day one. Include `period_start`/`period_end` from the start.
3. `analyst.py` — compare/contrast prompt, tested against a known set of conflicting articles.
4. `delivery/analysis_md.py` — daily digest renderer.
5. `analyze.py` — entrypoint wiring ingest → group → analyze → persist → deliver, plus `--backfill` mode.
6. `timeline.py` + `delivery/timeline_md.py` — query and render the historical view.
7. Backfill runs against historical date ranges to seed the timeline.
