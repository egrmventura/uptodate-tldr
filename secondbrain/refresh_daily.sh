#!/usr/bin/env bash
# Daily second-brain refresh: collect → consolidate → analyze → rebuild site.
#
# Install (user-approved step; not auto-installed):
#   crontab -e   →   0 7 * * *  cd /path/to/uptodate-tldr && ./secondbrain/refresh_daily.sh >> output/refresh.log 2>&1
#
# Each stage is idempotent; a stage failure aborts the refresh (set -e) so the
# previous day's site keeps serving rather than publishing a half-built one.

set -euo pipefail
cd "$(dirname "$0")/.."

echo "=== second-brain refresh $(date -u +%FT%TZ) ==="

# 1. collect: category-driven pass over HN + arXiv + RSS (URL-deduped)
python3 -m secondbrain.collect

# 2. consolidate: batch re-cluster; appends change events
python3 -m secondbrain.consolidate

# 3. analyze: LLM compare/contrast for new (topic, window) units only —
#    the store's UNIQUE + INSERT OR IGNORE makes re-analysis of old units free,
#    but cap spend anyway
python3 -m secondbrain.analyze_corpus --max-calls 20

# 4. export the JSON snapshots the site/checker read
python3 -m secondbrain.export_snapshots

# 5. upload snapshots to Vercel Blob (requires BLOB_READ_WRITE_TOKEN in env)
if [ -n "${BLOB_READ_WRITE_TOKEN:-}" ]; then
  for f in snapshots/*.json; do
    npx vercel blob put "$f" --pathname "snapshots/$(basename "$f")" --force
  done
else
  echo "BLOB_READ_WRITE_TOKEN not set — skipping blob upload (local-only refresh)"
fi

# 6. rebuild the site page (site/index.html — the Vercel root)
#    Once Blob is live, switch to: --data-url "$SNAPSHOT_BASE_URL"
python3 -m secondbrain.site_build ${SNAPSHOT_BASE_URL:+--data-url "$SNAPSHOT_BASE_URL"}

# 7. (optional) redeploy to Vercel — uncomment once the project is linked:
# npx vercel deploy --prod --cwd site --yes

echo "=== refresh complete ==="
