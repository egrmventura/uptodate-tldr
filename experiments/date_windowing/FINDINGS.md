# Date-Windowing Study — Findings & Decision

_2026-07-02. Grid: H1/H2 at W ∈ {7,14,21}d, H3 at gap ∈ {3,5,7}d, on the
78-doc / 25-edge trial corpus. Full numbers: `study_results.json`; method:
`study.py`; hypotheses: `HYPOTHESES.md`._

## Headline results

| config | split_rate ↓ | cohesion_ratio ↑ | anchor_churn ↓ | max_window ↓ |
|---|---|---|---|---|
| H1-sliding-14d | **0.84** | 1.42 | **0** | **8** |
| H2-calendar-7d | 0.92 | **2.33** | 0.024 | 3 |
| H2-calendar-14d | 0.84 | 1.56 | 0.032 | 6 |
| H3-gap-5d | 0.84 | 1.07 | 0 | 24 |
| H3-gap-7d | **0.60** | 1.10 | 0 | **42 (runaway)** |

## What held / what didn't

1. **Prediction confirmed — H2 is anchor-fragile.** Calendar bucketing is the
   *only* scheme whose assignments change when the anchor date shifts ±1–3d
   (churn 0.024–0.038, growing with W). H1/H3 are anchor-free by construction.
2. **Prediction confirmed — H3 has the best raw split rate and the worst
   dispersion.** gap-7d cuts only 60% of storyline edges but collapses half
   the corpus (42/78 docs) into one window; its cohesion_ratio (1.10) says
   those windows are barely better than random. Corpus-global gap-closing is
   the wrong granularity — H3 only makes sense *per storyline* (anchor at a
   cluster's first article), which is follow-up work, not a windowing default.
3. **Magnitude beats positioning.** Moving W from 7→14d improves split rate
   for both H1 (0.88→0.84) and H2 (0.92→0.84) — a bigger effect than switching
   scheme at fixed W. Real storylines here span ~3–5 weeks; no 7-day scheme
   can keep them whole (per-storyline table: every config still splits the
   4-week arcs into ≥3 windows).
4. **Intuitive check.** `skills/memory` (5 docs, 5 weeks): H1-14d → 3 windows,
   H2-7d → 5 windows (fully shredded), H3-7d → 2 windows. Matches the
   statistical ordering.

## Decision

**Adopt H1 — sliding windows with static 14-day magnitude — as the default
windowing for `--seed`/`--batch`.** Rationale: ties for best split rate,
zero anchor sensitivity (deterministic from data, so idempotency keys stay
stable), bounded window sizes, negligible first-doc churn (0.0 at 14d).

- Keep H2 calendar buckets available for strict-idempotency contexts where
  windows must be knowable *before* fetching (current `--seed` behavior) —
  it's the only scheme whose (topic, period) keys are independent of corpus
  contents.
- Revisit H3 as a *per-storyline* second pass (cluster first, then gap-close
  within each cluster) — its corpus-global form is disqualified.

Adoption itself (wiring an H1 option into `analyze.py --seed`) is a separate
PR off `staging` once this branch's conclusions are reviewed.
