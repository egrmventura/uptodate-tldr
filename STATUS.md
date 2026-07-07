# STATUS

_Last updated: 2026-07-06_

## Where things stand

- **Branch:** `feature/timeline-product` (clean tree), HEAD `a65758c` — feat(P5) GitHub Actions daily refresh
- **PRs:** #23 (secondbrain M1–M5) **merged to staging**; **#25 (timeline product P1–P5) OPEN**, stacked on #23 — diff collapses now that #23 landed
- **Tests:** 81 passed (`test_pipeline.py` 62 + `test_secondbrain.py` 19), offline
- **Live preview:** https://claude.ai/code/artifact/b55a7071-e5ed-4010-b6d2-4b74029cd87d (embedded-mode site, v3)

## Done this session (2026-07-05 → 07-06)

- **secondbrain/ layer (PR #23, merged):** `windowing.py` (H1 sliding-14d), `vectors.py` + `consolidate.py` (batch re-cluster, change-log events), `analyze_corpus.py` (LLM analyst bridge → `output/analyses.db`), `retrieval.py` (cited cosine search), `serve.py` (stdlib JSON API), `site_build.py`, `refresh_daily.sh`
- **Timeline product (PR #25, open):**
  - P1 `export_snapshots.py` → `snapshots/*.json`; site client-side rendered, embedded + `--data-url` (Vercel Blob) modes; data files untracked (`.gitignore`)
  - P2 `collect.py` — 4 product categories (config.yaml `categories:`) × HN+arXiv+curated-RSS; provenance-based relevance fix in `consolidate.py`
  - P3 category-tab timeline UI, live on the artifact URL
  - P4 `api/check.py` freshness checker + `vercel.json`; live-validated both directions (outdated→outdated, current→current)
  - P5 `.github/workflows/refresh.yml` daily 07:00 UTC chain; `refresh_daily.sh` now runs the same chain (laptop fallback)
- **Corpus:** 313 articles, 18 storylines, 37 analyses, 5 categories (snapshots/meta.json)

## Pending / next

1. **Merge PR #25** into `staging` (review-gated).
2. **Go-live provisioning (user steps, gate deployment):** Vercel project at **repo root**; Blob store; secrets `ANTHROPIC_API_KEY`, `BLOB_READ_WRITE_TOKEN`, `VERCEL_TOKEN` (GH) + `SNAPSHOT_BASE_URL` (GH variable + Vercel env).
3. **First CI run:** Actions → `daily-refresh` → *Run workflow* (manual validation before trusting cron).
4. Later: embedding upgrade for `vectors.py` (documented swap point); keyword-walk refresh per category; `experiment/date-windowing` branch findings already adopted (H1-14d) — branch can be closed or kept as archive.

## Known issues

- Mobile push disabled in `/config` — agent notifications reach desktop only.
- `output/second-brain-tests/` legacy trial scripts remain (superseded by `secondbrain/collect.py`); harmless, tracked docs/timelines only — data files are gitignored.
- Vercel root changed from `site/` to **repo root** (vercel.json handles output + api/) — old instruction in PR #23 body is stale.

## Recommended next command

Review & merge PR #25, complete the provisioning checklist in its description, then trigger `daily-refresh` manually once.
