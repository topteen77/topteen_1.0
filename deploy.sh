#!/usr/bin/env bash
# TopTeens deployment: build, up, health check, rollback on failure.
# Production: topteen.in (HTTPS). Dev: demo.topteen.in or http://43.204.127.118:8005/ (HTTP).
# Run from project root: ./deploy.sh [deploy|rebuild|rollback|stop]

set -e

export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-topteens}"
DEPLOY_HEALTH_URL="${DEPLOY_HEALTH_URL:-http://localhost}"
HEALTH_RETRIES="${HEALTH_RETRIES:-12}"
HEALTH_INTERVAL="${HEALTH_INTERVAL:-5}"
HEALTH_STARTUP_DELAY="${HEALTH_STARTUP_DELAY:-15}"

PRODUCTION_PATH="${PRODUCTION_PATH:-/home/ubuntu/git-project/topteens}"
LOG_PATH="${LOG_PATH:-/home/ubuntu/git-project/logs}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

# DB_MODE: local = MySQL container; external = join 0innerdb network; host = MySQL on host:3306; remote = DB_HOST from .env
DB_MODE="${DB_MODE:-remote}"
[ -f .env ] && DB_MODE=$(grep -E '^DB_MODE=' .env 2>/dev/null | cut -d= -f2- | tr -d ' "') || true
[ -z "$DB_MODE" ] && DB_MODE=remote

COMPOSE_FILES="-f docker-compose.yml"
ROLLBACK_FILES="-f docker-compose.rollback.yml"
if [ "$DB_MODE" = "local" ]; then
  COMPOSE_FILES="-f docker-compose.yml -f docker-compose.db-local.yml"
  ROLLBACK_FILES="-f docker-compose.rollback.yml -f docker-compose.rollback.db-local.yml"
elif [ "$DB_MODE" = "external" ]; then
  COMPOSE_FILES="-f docker-compose.yml -f docker-compose.db-external.yml"
  ROLLBACK_FILES="-f docker-compose.rollback.yml -f docker-compose.rollback.db-external.yml"
elif [ "$DB_MODE" = "host" ]; then
  COMPOSE_FILES="-f docker-compose.yml -f docker-compose.db-host.yml"
  ROLLBACK_FILES="-f docker-compose.rollback.yml -f docker-compose.rollback.db-host.yml"
fi

COMPOSE_CMD=""
for cmd in "docker compose" "docker-compose"; do
  if $cmd version >/dev/null 2>&1; then
    COMPOSE_CMD="$cmd"
    break
  fi
done
if [ -z "$COMPOSE_CMD" ]; then
  echo "[deploy] ERROR: docker and docker-compose (or 'docker compose') must be installed." >&2
  exit 1
fi

log() { echo "[deploy] $*"; }
err() { echo "[deploy] ERROR: $*" >&2; }

print_urls() {
  log "App (HTTP):     $DEPLOY_HEALTH_URL"
  if [ -f "${SSL_CERT_PATH:-./ssl}/cert.pem" ]; then
    HTTPS_PORT="${HTTPS_PORT:-443}"
    log "App (HTTPS):    https://topteen.in (production) or https://$(hostname -I 2>/dev/null | awk '{print $1}'):${HTTPS_PORT}"
    log "Note: Self-signed cert will show browser warning unless using Let's Encrypt."
  fi
}

preflight() {
  log "Preflight checks..."
  if ! command -v docker >/dev/null 2>&1; then
    err "Docker is not installed or not in PATH."
    exit 1
  fi
  if [ ! -f "docker-compose.yml" ]; then
    err "docker-compose.yml not found in $ROOT"
    exit 1
  fi
  if [ ! -f ".env" ]; then
    err ".env file not found."
    echo "" >&2
    echo "  Create from example:" >&2
    echo "    cp docker/.env.example .env" >&2
    echo "  Edit .env (ALLOWED_HOSTS, DB_*, etc.) and run again." >&2
    exit 1
  fi
  if [ -f .env ]; then
    [ -z "${APP_PORT}" ] && APP_PORT=$(grep -E '^APP_PORT=' .env 2>/dev/null | cut -d= -f2- | tr -d ' "')
    [ -z "${PRODUCTION_PATH}" ] && PRODUCTION_PATH=$(grep -E '^PRODUCTION_PATH=' .env 2>/dev/null | cut -d= -f2- | tr -d ' "')
    [ -z "${PRODUCTION_PATH}" ] && PRODUCTION_PATH="/home/ubuntu/git-project/topteens"
    [ -z "${LOG_PATH}" ] && LOG_PATH=$(grep -E '^LOG_PATH=' .env 2>/dev/null | cut -d= -f2- | tr -d ' "')
    [ -z "${LOG_PATH}" ] && LOG_PATH="/home/ubuntu/git-project/logs"
  fi
  APP_PORT="${APP_PORT:-80}"
  if [ "$APP_PORT" != "80" ] && [ "$DEPLOY_HEALTH_URL" = "http://localhost" ]; then
    DEPLOY_HEALTH_URL="http://localhost:${APP_PORT}"
  fi
  log "Deployment path: $ROOT"
  if [ "$ROOT" != "$PRODUCTION_PATH" ]; then
    log "WARNING: Current path ($ROOT) differs from production path ($PRODUCTION_PATH)"
  else
    log "Running from production path: $PRODUCTION_PATH"
  fi
  mkdir -p "$LOG_PATH" 2>/dev/null || { LOG_PATH="./logs"; mkdir -p "$LOG_PATH" || true; }
  [ -f .env ] && DB_MODE=$(grep -E '^DB_MODE=' .env 2>/dev/null | cut -d= -f2- | tr -d ' "') || true
  [ -z "$DB_MODE" ] && DB_MODE=remote
  COMPOSE_FILES="-f docker-compose.yml"
  ROLLBACK_FILES="-f docker-compose.rollback.yml"
  [ "$DB_MODE" = "local" ] && COMPOSE_FILES="-f docker-compose.yml -f docker-compose.db-local.yml" && ROLLBACK_FILES="-f docker-compose.rollback.yml -f docker-compose.rollback.db-local.yml"
  [ "$DB_MODE" = "external" ] && COMPOSE_FILES="-f docker-compose.yml -f docker-compose.db-external.yml" && ROLLBACK_FILES="-f docker-compose.rollback.yml -f docker-compose.rollback.db-external.yml"
  [ "$DB_MODE" = "host" ] && COMPOSE_FILES="-f docker-compose.yml -f docker-compose.db-host.yml" && ROLLBACK_FILES="-f docker-compose.rollback.yml -f docker-compose.rollback.db-host.yml"
  log "DB_MODE=$DB_MODE (local=MySQL container, external=0innerdb network, host=MySQL on host:3306, remote=DB_HOST)"
  log "Preflight OK."
}

tag_previous() {
  log "Tagging current images as :previous (for rollback)..."
  for img in topteens-web topteens-nginx; do
    if docker image inspect "$img:latest" >/dev/null 2>&1; then
      docker tag "$img:latest" "$img:previous" 2>/dev/null || true
      log "  $img:latest -> :previous"
    else
      log "  $img:latest not present (first deploy); skip :previous"
    fi
  done
}

tag_previous_web() {
  log "Tagging current web image as :previous (for rollback)..."
  if docker image inspect "topteens-web:latest" >/dev/null 2>&1; then
    docker tag "topteens-web:latest" "topteens-web:previous" 2>/dev/null || true
    log "  topteens-web:latest -> :previous"
  else
    log "  topteens-web:latest not present (first deploy); skip :previous"
  fi
}

do_build() {
  local build_flags="${1:-}"
  log "Building images (DB_MODE=$DB_MODE)${build_flags:+ $build_flags}..."
  if ! $COMPOSE_CMD $COMPOSE_FILES build $build_flags; then
    err "Build failed. Fix errors and re-run. No containers started."
    exit 1
  fi
  log "Build OK."
  print_urls
}

do_build_web() {
  local build_flags="${1:-}"
  log "Building web image only (DB_MODE=$DB_MODE)${build_flags:+ $build_flags}..."
  if ! $COMPOSE_CMD $COMPOSE_FILES build $build_flags web; then
    err "Web build failed. Fix errors and re-run."
    exit 1
  fi
  log "Web build OK."
}

do_up() {
  log "Starting containers (DB_MODE=$DB_MODE)..."
  $COMPOSE_CMD $COMPOSE_FILES down 2>/dev/null || true
  for name in topteens_web_1 topteens_nginx_1 topteens-web-1 topteens-nginx-1; do
    docker rm -f "$name" 2>/dev/null || true
  done
  docker ps -a --filter "name=topteens" --format "{{.ID}}" 2>/dev/null | xargs -r docker rm -f 2>/dev/null || true
  if ! $COMPOSE_CMD $COMPOSE_FILES up -d; then
    err "Start failed. Stopping partial start..."
    $COMPOSE_CMD $COMPOSE_FILES down 2>/dev/null || true
    err "Fix the error above and re-run."
    exit 1
  fi
  log "Containers started."
}

do_up_web() {
  log "Updating web container only (mysql, redis, celery, nginx stay running)..."
  if ! $COMPOSE_CMD $COMPOSE_FILES up -d web; then
    err "Web container update failed."
    exit 1
  fi
  log "Web container updated."
}

do_migrate() {
  log "Running database migrations..."
  if $COMPOSE_CMD $COMPOSE_FILES exec -T web python manage.py migrate --noinput 2>/dev/null; then
    log "Migrations OK."
  else
    log "Migrations failed or skipped (DB may be initializing). Continuing..."
  fi
}

do_collectstatic() {
  log "Collecting static files..."
  if $COMPOSE_CMD $COMPOSE_FILES exec -T web python manage.py collectstatic --noinput --clear 2>/dev/null; then
    log "collectstatic OK."
  else
    log "collectstatic failed. Check web container logs. Continuing..."
  fi
}

health_check() {
  local url="$1" retries="$2" interval="$3" i=1
  while [ "$i" -le "$retries" ]; do
    if curl -sf --max-time 10 "$url" >/dev/null 2>&1; then
      log "Health check OK ($url)."
      return 0
    fi
    log "  Health check $i/$retries failed, retry in ${interval}s..."
    sleep "$interval"
    i=$((i + 1))
  done
  return 1
}

do_rollback() {
  log "Attempting rollback to :previous images (DB_MODE=$DB_MODE)..."
  $COMPOSE_CMD $ROLLBACK_FILES down 2>/dev/null || true
  for name in topteens_web_1 topteens_nginx_1 topteens-web-1 topteens-nginx-1; do
    docker rm -f "$name" 2>/dev/null || true
  done
  docker ps -a --filter "name=topteens" --format "{{.ID}}" 2>/dev/null | xargs -r docker rm -f 2>/dev/null || true
  if $COMPOSE_CMD $ROLLBACK_FILES up -d; then
    sleep 3
    if health_check "$DEPLOY_HEALTH_URL" 3 3; then
      log "Rollback OK: previous version running."
      return 0
    fi
    err "Rollback up but health check failed. Stopping rollback stack."
    $COMPOSE_CMD $ROLLBACK_FILES down 2>/dev/null || true
  else
    err "Rollback up failed (:previous images may be missing)."
    $COMPOSE_CMD $ROLLBACK_FILES down 2>/dev/null || true
  fi
  return 1
}

do_rollback_web() {
  log "Attempting web-only rollback to :previous image..."
  if $COMPOSE_CMD $ROLLBACK_FILES up -d web; then
    sleep 3
    if health_check "$DEPLOY_HEALTH_URL" 3 3; then
      log "Web rollback OK: previous version running."
      return 0
    fi
    err "Web rollback up but health check failed."
  else
    err "Web rollback failed (topteens-web:previous may be missing)."
  fi
  return 1
}

deploy_web() {
  local rebuild="${1:-}"
  preflight
  tag_previous_web
  do_build_web "$rebuild"
  do_up_web
  sleep 5
  do_migrate
  do_collectstatic
  log "Waiting ${HEALTH_STARTUP_DELAY}s, then health check (${HEALTH_RETRIES}x every ${HEALTH_INTERVAL}s)..."
  sleep "$HEALTH_STARTUP_DELAY"
  if health_check "$DEPLOY_HEALTH_URL" "$HEALTH_RETRIES" "$HEALTH_INTERVAL"; then
    log "Web deployment finished successfully."
    print_urls
    return 0
  fi
  err "Health check failed. Attempting web-only rollback..."
  $COMPOSE_CMD logs --tail=120 web 2>&1 | sed 's/^/[deploy]   /' >&2 || true
  if do_rollback_web; then
    err "New version failed; rolled back to previous web. Fix errors and redeploy."
    exit 1
  fi
  err "Web deployment failed. Rollback failed or topteens-web:previous missing."
  exit 1
}

deploy() {
  local rebuild="${1:-}"
  preflight
  tag_previous
  do_build "$rebuild"
  do_up
  sleep 5
  do_migrate
  do_collectstatic
  log "Waiting ${HEALTH_STARTUP_DELAY}s, then health check (${HEALTH_RETRIES}x every ${HEALTH_INTERVAL}s)..."
  sleep "$HEALTH_STARTUP_DELAY"
  if health_check "$DEPLOY_HEALTH_URL" "$HEALTH_RETRIES" "$HEALTH_INTERVAL"; then
    log "Deployment finished successfully."
    print_urls
    return 0
  fi
  err "Health check failed. Stopping new deployment and attempting rollback..."
  $COMPOSE_CMD logs --tail=120 web 2>&1 | sed 's/^/[deploy]   /' >&2 || true
  $COMPOSE_CMD $COMPOSE_FILES down 2>/dev/null || true
  if do_rollback; then
    err "New version failed; rolled back to previous. Fix errors and redeploy."
    exit 1
  fi
  err "Deployment failed. Rollback failed or :previous missing. All containers stopped."
  exit 1
}

rollback() {
  preflight
  log "Manual rollback: stopping current deployment..."
  $COMPOSE_CMD $COMPOSE_FILES down 2>/dev/null || true
  for name in topteens_web_1 topteens_nginx_1 topteens-web-1 topteens-nginx-1; do
    docker rm -f "$name" 2>/dev/null || true
  done
  docker ps -a --filter "name=topteens" --format "{{.ID}}" 2>/dev/null | xargs -r docker rm -f 2>/dev/null || true
  if ! do_rollback; then
    err "Rollback failed. Ensure topteens-web:previous exists from a prior deploy."
    exit 1
  fi
  log "Manual rollback done."
  print_urls
}

stop() {
  preflight
  log "Stopping all containers..."
  $COMPOSE_CMD $COMPOSE_FILES down 2>/dev/null || true
  log "Containers stopped."
}

case "${1:-deploy}" in
  deploy) deploy ;;
  rebuild) deploy "--no-cache" ;;
  web) deploy_web ;;
  web-rebuild) deploy_web "--no-cache" ;;
  rollback) rollback ;;
  stop) stop ;;
  *)
    echo "Usage: $0 {deploy|rebuild|web|web-rebuild|rollback|stop}"
    echo ""
    echo "  web          - [CI/GitHub Actions] Build & update web only; mysql, redis, celery, nginx stay running"
    echo "  web-rebuild  - Same as web but build with --no-cache"
    echo ""
    echo "  deploy       - [Manual] Full deploy: build all, recreate all containers (mysql, redis, celery, nginx, web)"
    echo "  rebuild      - Same as deploy but build with --no-cache"
    echo ""
    echo "  rollback     - Rollback to :previous images"
    echo "  stop         - docker compose down"
    exit 1
    ;;
esac
