#!/usr/bin/env bash
# Test a reverted version (previous git commit or Docker image)
# Usage:
#   ./scripts/test-reverted-version.sh git [commit]   - checkout commit, rebuild, run
#   ./scripts/test-reverted-version.sh docker         - rollback to :previous image

set -e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

case "${1:-}" in
  git)
    COMMIT="${2:-HEAD~1}"
    echo "[test-revert] Stashing current changes..."
    git stash push -u -m "WIP before revert test" 2>/dev/null || true
    echo "[test-revert] Checking out $COMMIT..."
    git checkout "$COMMIT" -- .
    echo "[test-revert] Rebuilding Docker images..."
    docker compose -f docker-compose.yml -f docker-compose.db-external.yml build --no-cache web 2>/dev/null || \
    docker compose -f docker-compose.yml build --no-cache web 2>/dev/null || true
    echo "[test-revert] Run: ./deploy.sh deploy  (or docker compose up -d)"
    echo "[test-revert] To restore: git checkout master -- . && git stash pop"
    ;;
  docker)
    echo "[test-revert] Rolling back to :previous image..."
    ./deploy.sh rollback
    ;;
  *)
    echo "Usage: $0 {git [commit]|docker}"
    echo "  git [commit]  - Revert code to commit (default: HEAD~1), rebuild"
    echo "  docker        - Rollback to topteens-web:previous image"
    exit 1
    ;;
esac
