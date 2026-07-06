# Second-Brain Tests — Real Seed Trial + Topic-Relation Experiments

_2026-07-01. Real-data trial: 26 weeks (2026-01-01 → 2026-06-30) of Hacker News
articles on **Claude tool expansion**, scraped, summarized, clustered two ways
(concept **nodes** vs TF-IDF **vectors**), and seeded into a real `Store`
timeline db with idempotency verified._

## Pipeline (run in order)

```bash
python3 output/second-brain-tests/fetch_articles.py     # 1. Algolia HN, per-week windows → data/articles_raw.json
python3 output/second-brain-tests/scrape_summarize.py   # 2. scraper.scrape + extractive summary → data/articles.json
python3 output/second-brain-tests/topic_graph.py        # 3. node & vector graphs → data/{nodes,edges_*,clusters,metrics}.json
python3 output/second-brain-tests/seed_trial.py         # 4. seed Store db twice, assert idempotent → data/analyses-trial.db
python3 -m pytest output/second-brain-tests/test_second_brain.py -v   # 5. validate (10 tests)
```

Everything after step 1–2 (network) is offline, LLM-free, and dependency-free
(pure Python — no sklearn/numpy). The trial db is separate from production
`output/analyses.db`.

## Trial results

| Stage | Result |
|---|---|
| Fetch | **78 articles**, 3/week × 26 weeks, **0 empty weeks** (relevance filter: Claude/Anthropic + capability term) |
| Scrape | **68/78 (87%)** full-text; 10 fell back to HN excerpt (paywall/403/429 — isolation held, no crashes) |
| Summaries | Extractive, ≤600 chars each; whole corpus ≈ 45 KB — comfortably context-cheap |
| Seed | **31 GroupAnalysis rows across 11 topics**; re-run added **0 rows** (UNIQUE + INSERT OR IGNORE) |
| Timeline | Biggest topic spans 5 periods, rendered chronologically by `period_start` (real publication dates) |
| Validation | 10/10 pytest checks pass |

## Findings

### F1 — `HackerNewsSource` ignores backfill windows (bug, production-relevant)
`sources/hackernews.py` hardcodes `created_at_i > now-7d` and never reads the
`date_from`/`date_to` keys that `analyze.py --backfill/--seed` injects into
source config. **Historical seeding through the normal pipeline silently
returns only last-week data.** This trial worked around it by querying Algolia
with explicit `created_at_i>=X,created_at_i<Y` per week (`fetch_articles.py`).
→ **Fixed 2026-07-02** (branch `fix/hn-backfill-window`): `HackerNewsSource`
now honors `date_from`/`date_to` (inclusive window), falling back to trailing
7 days when absent/malformed. Validated offline (6 filter cases + query-param
regression test) and live (30/30 items inside a requested 2026-03 window).

### F2 — Vector method (TF-IDF + cosine) is the better topic-relation primitive
On 78 docs: **25 edges → 11 multi-doc clusters**, avg temporal span **2.9
weeks** — clusters track real ongoing storylines rather than single-week
bursts. Examples (label = top shared terms):

- `teams / sessions / subagent` — 5 docs / 4 weeks (Claude Code orchestration arc)
- `skills / forgets / memory` — 5 docs / 5 weeks (memory & skills arc)
- `microsoft / copilot` — 4 docs / 4 weeks (Microsoft adoption arc)

### F3 — Concept-node method is high-precision / low-recall
Promoting each doc's top-8 TF-IDF terms to explicit concept nodes and linking
docs by Jaccard overlap produced only **5 edges → 3 clusters** (71 singletons).
It needs ≥2 shared *top* terms, which almost never happens across differently
worded headlines. Its edges were clean, but as the sole relation mechanism it
misses most storylines. **Best use: concept nodes for explainability + labels,
vector similarity for recall.** (Pairwise cluster agreement between methods:
0.986 — they rarely disagree, concept is simply a subset.)

### F4 — Hybrid recommendation for a real "second brain"
1. **Edges from vectors** (cosine ≥ ~0.18 + top-k floor so no doc strands).
2. **Labels/explanations from concept nodes** (top shared TF-IDF terms already
   produce human-readable labels like `skills / forgets / memory` — no LLM
   needed for a first pass).
3. **Store topics as the cluster label**, one `GroupAnalysis` per
   (cluster × week) with periods from publication dates — slots directly into
   the existing timeline schema, proven idempotent here.
4. Token hygiene: strip HTML entities (`x2f` artifacts) and trailing
   punctuation during tokenization before productionizing.

### F5 — Extractive summaries were enough for clustering
Clusters formed on title + ≤600-char lead-biased extractive summaries. No LLM
summarization was needed for *relating* articles — save the LLM budget for the
analysis stage (agreements/contradictions), which extractive methods can't do.

## Context-usage notes
All article bodies stayed on disk; only titles/labels/metrics ever entered the
working context (session stayed ~20%, far below the 75% compaction trigger).

## Files
```
fetch_articles.py      weekly Algolia fetch (works around F1)
scrape_summarize.py    scrape + offline extractive summaries
topic_graph.py         node & vector graph builders + comparison metrics
seed_trial.py          Store seeding, idempotency + chronology assertions
test_second_brain.py   10 offline validation tests
data/                  articles*.json, nodes/edges/clusters/metrics.json,
                       analyses-trial.db, timeline-*.md
```
