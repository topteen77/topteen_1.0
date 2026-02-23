#!/usr/bin/env bash
# Quick performance check for careers pages. Run with: ./scripts/test_careers_performance.sh [BASE_URL]
# Default BASE_URL=http://127.0.0.1:8002
set -e
BASE_URL="${1:-http://127.0.0.1:8002}"
echo "Testing careers endpoints at $BASE_URL"
echo "---"
echo -n "Careers list (view-mode): "
curl -s -o /dev/null -w "%{time_total}s (HTTP %{http_code})\n" --max-time 60 "$BASE_URL/careers/?mode=view-mode" || echo "timeout/fail"
echo -n "Careers list (AI mode):   "
curl -s -o /dev/null -w "%{time_total}s (HTTP %{http_code})\n" --max-time 60 "$BASE_URL/careers/" || echo "timeout/fail"
echo "---"
echo "Done. If times are high, ensure Elasticsearch is running and consider caching (facets are now cached when no filters)."
