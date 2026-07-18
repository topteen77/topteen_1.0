#!/usr/bin/env bash
# Test a reverted version (previous git commit or Docker image)
# Usage:
#   ./scripts/test-reverted-version.sh git [commit]   - checkout commit, rebuild, run
#   ./scripts/test-reverted-version.sh docker         - restart stack with current images

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
    ./docker_files/deploy.sh build
    echo "[test-revert] Run: ./docker_files/deploy.sh up"
    echo "[test-revert] To restore: git checkout master -- . && git stash pop"
    ;;
  docker)
    echo "[test-revert] Restarting stack with current images..."
    ./docker_files/deploy.sh restart
    ;;
  *)
    echo "Usage: $0 {git [commit]|docker}"
    echo "  git [commit]  - Revert code to commit (default: HEAD~1), rebuild"
    echo "  docker        - Restart docker_files stack"
    exit 1
    ;;
esac
