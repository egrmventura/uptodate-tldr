# Campaign 2 Report — 60-Day Buffer, 10-Minute Cadence

_Iterations 25–72 (48 runs) over 8.6 hours, 2026-07-02 19:23 → 2026-07-03 03:59 UTC. Change under test: `LOOKBACK_DAYS` 3 → 60._

## Totals
- **+183 new articles** this campaign (corpus 66 → 249, all URL-cited)
- **Groups 24 → 83**
- **Full-text scraped: 200/249 (80%)**
- Publication dates span **2026-05-03 → 2026-07-02** — the 60-day buffer reached the backlog as intended

## Buffer comparison (3-day vs 60-day)
| | Campaign 1 (3d buffer, 15m) | Campaign 2 (60d buffer, 10m) |
|---|---|---|
| Iterations | 24 | 48 |
| New articles | 66 | 183 |
| Yield/iteration | 2.75 | 3.81 |
| Saturation point | iter ~12 (3h) | iter ~30 (5h) |
| Post-saturation trickle | fresh posts only | fresh posts only |

## Yield curve (new per iteration, campaign 2)
```
666666666666666666666665666563200240000000000000   (iters 25→72)
```
Flat +6/iter (the MAX_NEW_PER_RUN cap) for ~30 iterations — the backlog kept
the pipeline saturated far longer than the 3-day run — then dedupe exhaustion
at iter ~55, matching campaign 1's saturation pattern at a 2.5× larger scale.

## Largest topic groups
- **build / prompt / thing** — 42 articles (g000)
- **claude / code / network** — 39 articles (g002)
- **x2f / agent / view** — 13 articles (g026)
- **typescript / lsp / claude** — 9 articles (g020)
- **plugin / intelligence / repository** — 7 articles (g054)
- **ouijit / terminal / agent** — 6 articles (g001)
- **claude / microsoft / foundry** — 6 articles (g019)
- **down / same / way** — 5 articles (g008)

## Observations
- The per-iteration cap (MAX_NEW_PER_RUN=6), not the buffer, was the binding
  constraint for the first 5 hours — a bulk-backfill mode without the cap would
  drain a 60-day backlog in minutes instead of hours.
- Group count grew linearly with corpus (24→83 at ~1 group per 2.2 articles);
  GROUP_THRESHOLD=0.15 on short summaries is likely too strict — many singleton
  groups. Candidate fix: batch re-cluster with the trial's vector_edges method.
- Context stayed ~38% peak — the 85% compaction trigger was never approached.
