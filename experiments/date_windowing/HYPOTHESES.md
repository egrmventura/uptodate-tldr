# Date-Windowing Hypotheses — Article-Relation Reliability

_Base branch for the study. Question: when relating articles into topic
storylines (the second-brain graph from `output/second-brain-tests/`), which
date-separation scheme groups them most reliably — statistically (cluster
quality metrics) and intuitively (do clusters read as one storyline)?_

Builds on trial findings **F2/F3** (vectors for recall, concept nodes for
labels) and requires the **F1 fix** (`fix/hn-backfill-window`, PR #21) so
`HackerNewsSource` can actually fetch arbitrary historical windows — this
branch is cut from that fix.

## The three schemes under test

| ID | Scheme | Definition | Intuition |
|----|--------|------------|-----------|
| **H1** | Dynamic ranges, static magnitude | Sliding window of fixed size W (e.g. 7d), advanced per article/cluster; window *positions* float, size doesn't | Storylines start whenever news breaks, not on Mondays — but stay bounded |
| **H2** | Static ranges | Fixed calendar buckets (ISO weeks, fortnights, months) | Simple, idempotent, what `--seed` does today; risks splitting a storyline across a bucket boundary |
| **H3** | Dynamic magnitude, anchored at first article | Window opens at a cluster's first article and extends while related articles keep arriving (gap-based close, e.g. close after G quiet days); size is data-driven | Storylines live exactly as long as the news does; risks runaway windows on hot topics |

## Metrics (per scheme, same corpus)

**Statistical**
- `boundary_split_rate` — fraction of vector-similarity edges (cosine ≥ 0.18)
  whose two articles land in *different* windows: lower = the scheme cuts
  fewer real storylines. Primary metric.
- `intra_window_cohesion` / `inter_window_separation` — mean pairwise cosine
  inside vs across windows (silhouette-style ratio).
- `window_count` and `window_size_dispersion` — cost/parsimony of the scheme.
- Stability: re-run with jittered start date (±3d); measure assignment churn.

**Intuitive**
- For the known storylines from the trial (`skills/memory`, `teams/subagent`,
  `microsoft/copilot`): does each land in one window (or a clean chain), or
  is it shredded? Reported as a per-storyline table in the findings.

## Design constraints

- Same corpus for all three schemes: the 78-article trial corpus
  (`output/second-brain-tests/data/articles.json`), extendable by refetching
  with `harness.py --refetch` now that F1 is fixed.
- Vector method (TF-IDF + cosine, from `topic_graph.py`) is the fixed
  relation primitive — only the windowing varies.
- Idempotency rule unchanged: whatever wins must still produce deterministic
  `(topic, period_start, period_end)` keys for the Store.

## Predictions (to be confirmed/refuted)

- H2 will show the highest `boundary_split_rate` (calendar cuts are blind).
- H3 will have the best cohesion but the worst size dispersion (and needs a
  gap parameter G tuned; try G ∈ {3, 5, 7} days).
- H1 lands between; jitter stability is its expected weakness vs H2.

## Status

- [x] Base branch cut from `fix/hn-backfill-window` (F1)
- [x] Harness skeleton (`harness.py`) — loads corpus, implements the three
      window assigners, computes `boundary_split_rate` end-to-end
- [ ] Full metric suite (cohesion/separation, jitter stability)
- [ ] Findings report with per-storyline intuition table
- [ ] Decision: adopt winner into `--seed`/`--batch` windowing
