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

# 1. collect: one loop pass over the factual keywords (URL-deduped)
python3 output/second-brain-tests/live/loop_iteration.py

# 2. consolidate: batch re-cluster; appends change events
python3 -m secondbrain.consolidate

# 3. analyze: LLM compare/contrast for new (topic, window) units only —
#    the store's UNIQUE + INSERT OR IGNORE makes re-analysis of old units free,
#    but cap spend anyway
python3 -m secondbrain.analyze_corpus --max-calls 20

# 4. rebuild the site artifact
python3 -m secondbrain.site_build

echo "=== refresh complete ==="
