#!/usr/bin/env bash
# TopTeens deployment: build, up, health check, rollback on failure.
# Production/staging: domain and IP from .env (PRODUCTION_DOMAIN, STAGING_IP, PRODUCTION_SERVER_NAMES, STAGING_SERVER_NAMES).
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
DOCKER_DIR="$ROOT/docker"
cd "$ROOT"

# Run compose from docker/ so all compose files live there; use root .env for variable substitution
run_compose() { (cd "$DOCKER_DIR" && $COMPOSE_CMD --env-file "$ROOT/.env" "$@"); }

# Docker image and tags (configurable from .env: DOCKER_IMAGE, DOCKER_IMAGE_NGINX, DOCKER_TAG_ENV, DOCKER_TAG_PROD)
# Domain (production) and IP (staging) from .env: PRODUCTION_DOMAIN, STAGING_IP, PRODUCTION_SERVER_NAMES, STAGING_SERVER_NAMES
read_env_var() { [ -f .env ] && grep -E "^$1=" .env 2>/dev/null | cut -d= -f2- | tr -d ' "' | head -1; }
DEPLOY_IMAGE="${DOCKER_IMAGE:-$(read_env_var DOCKER_IMAGE)}"
DEPLOY_IMAGE="${DEPLOY_IMAGE:-developertopteen/demotopteen}"
DEPLOY_IMAGE_NGINX="${DOCKER_IMAGE_NGINX:-$(read_env_var DOCKER_IMAGE_NGINX)}"
DEPLOY_IMAGE_NGINX="${DEPLOY_IMAGE_NGINX:-developertopteen/demotopteen-nginx}"
DOCKER_TAG_ENV="${DOCKER_TAG_ENV:-$(read_env_var DOCKER_TAG_ENV)}"
DOCKER_TAG_ENV="${DOCKER_TAG_ENV:-topteens_django_env}"
DOCKER_TAG_PROD="${DOCKER_TAG_PROD:-$(read_env_var DOCKER_TAG_PROD)}"
DOCKER_TAG_PROD="${DOCKER_TAG_PROD:-topteens_django_prod}"

PRODUCTION_DOMAIN="${PRODUCTION_DOMAIN:-$(read_env_var PRODUCTION_DOMAIN)}"
PRODUCTION_DOMAIN="${PRODUCTION_DOMAIN:-topteen.in}"
STAGING_IP="${STAGING_IP:-$(read_env_var STAGING_IP)}"
STAGING_IP="${STAGING_IP:-43.204.127.118}"
PRODUCTION_SERVER_NAMES="${PRODUCTION_SERVER_NAMES:-$(read_env_var PRODUCTION_SERVER_NAMES)}"
PRODUCTION_SERVER_NAMES="${PRODUCTION_SERVER_NAMES:-topteen.in www.topteen.in}"
STAGING_SERVER_NAMES="${STAGING_SERVER_NAMES:-$(read_env_var STAGING_SERVER_NAMES)}"
STAGING_SERVER_NAMES="${STAGING_SERVER_NAMES:-demo.topteen.in 43.204.127.118 localhost}"

# DB_MODE: local = MySQL container; external = join 0innerdb network; host = MySQL on host:3306; remote = DB_HOST from .env
DB_MODE="${DB_MODE:-remote}"
[ -f .env ] && DB_MODE=$(grep -E '^DB_MODE=' .env 2>/dev/null | cut -d= -f2- | tr -d ' "') || true
[ -z "$DB_MODE" ] && DB_MODE=remote

COMPOSE_FILES="-f docker-compose.yml"
ROLLBACK_FILES="-f docker-compose.rollback.yml"
COMPOSE_ENV="-f docker-compose.env.yml"
COMPOSE_CODE="-f docker-compose.code.yml"
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

# Check if a port is already in use (so multiple sites can use different APP_PORT via .env)
check_port_busy() {
  local port="$1"
  [ -z "$port" ] && return 1
  if command -v ss >/dev/null 2>&1; then
    ss -tlnp 2>/dev/null | grep -qE ":$port\s"
    return $?
  fi
  if command -v netstat >/dev/null 2>&1; then
    netstat -tln 2>/dev/null | grep -qE "[:.]$port\s"
    return $?
  fi
  return 1
}

warn_if_ports_busy() {
  local app_port="${APP_PORT:-80}"
  local https_port="${HTTPS_PORT:-443}"
  local busy=0
  if check_port_busy "$app_port"; then
    err "Port $app_port (APP_PORT) is already in use. Set APP_PORT to a different port in .env (e.g. 8005) for this site."
    busy=1
  fi
  if check_port_busy "$https_port"; then
    err "Port $https_port (HTTPS_PORT) is already in use. Set HTTPS_PORT to a different port in .env (e.g. 8443)."
    busy=1
  fi
  if [ "$busy" -eq 1 ]; then
    err "Deploy aborted. Free the port(s) or change APP_PORT/HTTPS_PORT in .env and run again."
    exit 1
  fi
  log "Ports $app_port (HTTP) and $https_port (HTTPS) are free."
}

print_urls() {
  log "App (HTTP):     $DEPLOY_HEALTH_URL"
  if [ -f "${SSL_CERT_PATH:-./ssl}/cert.pem" ]; then
    HTTPS_PORT="${HTTPS_PORT:-443}"
    log "App (HTTPS):    https://${PRODUCTION_DOMAIN} (production) or https://${STAGING_IP}:${HTTPS_PORT} (staging)"
    log "Note: Self-signed cert will show browser warning unless using Let's Encrypt."
  fi
}

preflight() {
  log "Preflight checks..."
  if ! command -v docker >/dev/null 2>&1; then
    err "Docker is not installed or not in PATH."
    exit 1
  fi
  if [ ! -f "$DOCKER_DIR/docker-compose.yml" ]; then
    err "docker-compose.yml not found in $DOCKER_DIR"
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
  # Normalize LOG_PATH to absolute so volume mounts work when compose runs from docker/
  [ -n "$LOG_PATH" ] && [ "${LOG_PATH#/}" = "$LOG_PATH" ] && LOG_PATH="$ROOT/$LOG_PATH"
  export LOG_PATH
  [ -f .env ] && DB_MODE=$(grep -E '^DB_MODE=' .env 2>/dev/null | cut -d= -f2- | tr -d ' "') || true
  [ -z "$DB_MODE" ] && DB_MODE=remote
  COMPOSE_FILES="-f docker-compose.yml"
  ROLLBACK_FILES="-f docker-compose.rollback.yml"
  [ "$DB_MODE" = "local" ] && COMPOSE_FILES="-f docker-compose.yml -f docker-compose.db-local.yml" && ROLLBACK_FILES="-f docker-compose.rollback.yml -f docker-compose.rollback.db-local.yml"
  [ "$DB_MODE" = "external" ] && COMPOSE_FILES="-f docker-compose.yml -f docker-compose.db-external.yml" && ROLLBACK_FILES="-f docker-compose.rollback.yml -f docker-compose.rollback.db-external.yml"
  [ "$DB_MODE" = "host" ] && COMPOSE_FILES="-f docker-compose.yml -f docker-compose.db-host.yml" && ROLLBACK_FILES="-f docker-compose.rollback.yml -f docker-compose.rollback.db-host.yml"
  log "DB_MODE=$DB_MODE (local=MySQL container, external=0innerdb network, host=MySQL on host:3306, remote=DB_HOST)"
  [ -z "${APP_PORT}" ] && APP_PORT=$(grep -E '^APP_PORT=' .env 2>/dev/null | cut -d= -f2- | tr -d ' "')
  [ -z "${HTTPS_PORT}" ] && HTTPS_PORT=$(grep -E '^HTTPS_PORT=' .env 2>/dev/null | cut -d= -f2- | tr -d ' "')
  APP_PORT="${APP_PORT:-80}"
  HTTPS_PORT="${HTTPS_PORT:-443}"
  log "Preflight OK."
}

# DEPLOY_IMAGE / DEPLOY_IMAGE_NGINX / DOCKER_TAG_* set above from .env

tag_previous() {
  log "Tagging current images as :previous (for rollback)..."
  for img in "$DEPLOY_IMAGE" "$DEPLOY_IMAGE_NGINX"; do
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
  if docker image inspect "$DEPLOY_IMAGE:latest" >/dev/null 2>&1; then
    docker tag "$DEPLOY_IMAGE:latest" "$DEPLOY_IMAGE:previous" 2>/dev/null || true
    log "  $DEPLOY_IMAGE:latest -> :previous"
  else
    log "  $DEPLOY_IMAGE:latest not present (first deploy); skip :previous"
  fi
}

do_build() {
  local build_flags="${1:-}"
  log "Building images (DB_MODE=$DB_MODE)${build_flags:+ $build_flags}..."
  if ! run_compose $COMPOSE_FILES build $build_flags; then
    err "Build failed. Fix errors and re-run. No containers started."
    exit 1
  fi
  if docker image inspect "$DEPLOY_IMAGE:latest" >/dev/null 2>&1; then
    docker tag "$DEPLOY_IMAGE:latest" "$DEPLOY_IMAGE:$DOCKER_TAG_PROD" 2>/dev/null || true
    log "Tagged $DEPLOY_IMAGE:$DOCKER_TAG_PROD"
  fi
  log "Build OK."
  print_urls
}

do_build_web() {
  local build_flags="${1:-}"
  log "Building web image only (DB_MODE=$DB_MODE)${build_flags:+ $build_flags}..."
  if ! run_compose $COMPOSE_FILES build $build_flags web; then
    err "Web build failed. Fix errors and re-run."
    exit 1
  fi
  log "Web build OK."
}

do_up() {
  warn_if_ports_busy
  log "Starting containers (DB_MODE=$DB_MODE)..."
  run_compose $COMPOSE_FILES down 2>/dev/null || true
  for name in topteens_web_1 topteens_nginx_1 topteens-web-1 topteens-nginx-1; do
    docker rm -f "$name" 2>/dev/null || true
  done
  docker ps -a --filter "name=topteens" --format "{{.ID}}" 2>/dev/null | xargs -r docker rm -f 2>/dev/null || true
  if ! run_compose $COMPOSE_FILES up -d; then
    err "Start failed. Stopping partial start..."
    run_compose $COMPOSE_FILES down 2>/dev/null || true
    err "Fix the error above and re-run."
    exit 1
  fi
  log "Containers started."
}

do_up_web() {
  # web/celery/celery_beat share the same app image. Recreating only web leaves
  # workers on the old filesystem (missing new tasks like demo_data.tasks.*).
  log "Updating web + celery + celery_beat (shared app image; mysql/redis/nginx stay running)..."
  if ! run_compose $COMPOSE_FILES up -d --force-recreate --no-deps web celery celery_beat; then
    err "Web/celery container update failed."
    exit 1
  fi
  log "Web + celery + celery_beat containers updated."
}

do_migrate() {
  log "Running database migrations..."
  if run_compose $COMPOSE_FILES exec -T web python manage.py migrate --noinput 2>/dev/null; then
    log "Migrations OK."
  else
    log "Migrations failed or skipped (DB may be initializing). Continuing..."
  fi
}

do_collectstatic() {
  log "Collecting static files..."
  if run_compose $COMPOSE_FILES exec -T web python manage.py collectstatic --noinput --clear 2>/dev/null; then
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
  run_compose $ROLLBACK_FILES down 2>/dev/null || true
  for name in topteens_web_1 topteens_nginx_1 topteens-web-1 topteens-nginx-1; do
    docker rm -f "$name" 2>/dev/null || true
  done
  docker ps -a --filter "name=topteens" --format "{{.ID}}" 2>/dev/null | xargs -r docker rm -f 2>/dev/null || true
  if run_compose $ROLLBACK_FILES up -d; then
    sleep 3
    if health_check "$DEPLOY_HEALTH_URL" 3 3; then
      log "Rollback OK: previous version running."
      return 0
    fi
    err "Rollback up but health check failed. Stopping rollback stack."
    run_compose $ROLLBACK_FILES down 2>/dev/null || true
  else
    err "Rollback up failed (:previous images may be missing)."
    run_compose $ROLLBACK_FILES down 2>/dev/null || true
  fi
  return 1
}

do_rollback_web() {
  log "Attempting web-only rollback to :previous image..."
  if run_compose $ROLLBACK_FILES up -d web; then
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
  run_compose logs --tail=120 web 2>&1 | sed 's/^/[deploy]   /' >&2 || true
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
    deploy_push
    return 0
  fi
  err "Health check failed. Stopping new deployment and attempting rollback..."
  run_compose logs --tail=120 web 2>&1 | sed 's/^/[deploy]   /' >&2 || true
  run_compose $COMPOSE_FILES down 2>/dev/null || true
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
  run_compose $COMPOSE_FILES down 2>/dev/null || true
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
  run_compose $COMPOSE_FILES down 2>/dev/null || true
  log "Containers stopped."
}

# --- ENV stack (mariadb, nginx, redis, elasticsearch, certbot) ---
up_env() {
  preflight
  warn_if_ports_busy
  log "Starting ENV stack (mariadb, nginx, redis, elasticsearch, certbot)..."
  mkdir -p "${LOG_PATH:-./logs}" "${MARIADB_DATA_PATH:-./data/mariadb}" "${ELASTICSEARCH_DATA_PATH:-./data/elasticsearch}" 2>/dev/null || true
  run_compose $COMPOSE_ENV up -d
  log "ENV stack started."
}

down_env() {
  [ -f .env ] && preflight || true
  log "Stopping ENV stack..."
  run_compose $COMPOSE_ENV down 2>/dev/null || true
  log "ENV stack stopped."
}

rebuild_env() {
  preflight
  warn_if_ports_busy
  log "Rebuilding and starting ENV stack..."
  run_compose $COMPOSE_ENV build --no-cache 2>/dev/null || true
  run_compose $COMPOSE_ENV up -d --force-recreate
  log "ENV stack rebuilt and started."
}

down_env_remove_images() {
  [ -f .env ] && preflight || true
  log "Stopping ENV stack and removing images..."
  run_compose $COMPOSE_ENV down --rmi local 2>/dev/null || true
  log "ENV stack stopped and images removed."
}

# --- CODE stack (developertopteen/demotopteen image) ---
code_build() {
  local flags="${1:-}"
  log "Building CODE stack image $DEPLOY_IMAGE:latest $flags..."
  if ! run_compose $COMPOSE_CODE build $flags web; then
    err "CODE build failed."
    exit 1
  fi
  if docker image inspect "$DEPLOY_IMAGE:latest" >/dev/null 2>&1; then
    docker tag "$DEPLOY_IMAGE:latest" "$DEPLOY_IMAGE:$DOCKER_TAG_ENV" 2>/dev/null || true
    log "Tagged $DEPLOY_IMAGE:$DOCKER_TAG_ENV"
  fi
  log "CODE build OK (image: $DEPLOY_IMAGE:latest)."
}

code_push() {
  local push_img="${DOCKER_PUSH_IMAGE:-}"
  [ -z "$push_img" ] && [ -n "${DOCKER_PUSH_TAG:-}" ] && push_img="$DEPLOY_IMAGE:${DOCKER_PUSH_TAG}"
  if [ -n "$push_img" ]; then
    log "Pushing to docker.io ($push_img)..."
    docker tag "$DEPLOY_IMAGE:latest" "$push_img" 2>/dev/null || true
    if docker push "$push_img"; then
      log "Push to docker.io OK."
    else
      err "Push failed. Check: docker login"
    fi
  fi
}

# Push production image (after deploy/rebuild). Only runs when DOCKER_PUSH_TAG or DOCKER_PUSH_IMAGE is set.
deploy_push() {
  local push_img="${DOCKER_PUSH_IMAGE:-}"
  [ -z "$push_img" ] && [ -n "${DOCKER_PUSH_TAG:-}" ] && push_img="$DEPLOY_IMAGE:${DOCKER_PUSH_TAG}"
  [ -z "$push_img" ] && return 0
  if docker image inspect "$DEPLOY_IMAGE:latest" >/dev/null 2>&1; then
    log "Pushing to docker.io ($push_img)..."
    docker tag "$DEPLOY_IMAGE:latest" "$push_img" 2>/dev/null || true
    if docker push "$push_img"; then
      log "Push to docker.io OK."
    else
      err "Push failed. Check: docker login"
    fi
  fi
}

up_code() {
  preflight
  warn_if_ports_busy
  code_build
  code_push
  log "Starting CODE stack (web, nginx, celery, celery_beat, redis)..."
  mkdir -p "${LOG_PATH:-./logs}" 2>/dev/null || true
  run_compose $COMPOSE_CODE up -d
  log "CODE stack started. Logs: ${LOG_PATH:-./logs}"
  print_urls
}

down_code() {
  [ -f .env ] && preflight || true
  log "Stopping CODE stack..."
  run_compose $COMPOSE_CODE down 2>/dev/null || true
  log "CODE stack stopped."
}

rebuild_code() {
  preflight
  warn_if_ports_busy
  code_build "--no-cache"
  code_push
  log "Starting CODE stack (recreate)..."
  run_compose $COMPOSE_CODE up -d --force-recreate
  log "CODE stack rebuilt and started."
  print_urls
}

down_code_remove_images() {
  [ -f .env ] && preflight || true
  log "Stopping CODE stack and removing $DEPLOY_IMAGE images..."
  run_compose $COMPOSE_CODE down --rmi local 2>/dev/null || true
  log "CODE stack stopped and images removed."
}

case "${1:-deploy}" in
  deploy) deploy ;;
  rebuild) deploy "--no-cache" ;;
  web) deploy_web ;;
  web-rebuild) deploy_web "--no-cache" ;;
  rollback) rollback ;;
  stop) stop ;;
  up-env) up_env ;;
  down-env) down_env ;;
  rebuild-env) rebuild_env ;;
  down-env-remove-images) down_env_remove_images ;;
  up-code) up_code ;;
  down-code) down_code ;;
  rebuild-code) rebuild_code ;;
  down-code-remove-images) down_code_remove_images ;;
  *)
    echo "Usage: $0 <command>"
    echo ""
    echo "  ENV stack (infra):"
    echo "    up-env                 - Start env (mariadb, nginx, redis, elasticsearch, certbot)"
    echo "    down-env               - Stop env stack"
    echo "    rebuild-env            - Rebuild and start env stack"
    echo "    down-env-remove-images - Stop env and remove images"
    echo ""
    echo "  CODE stack (image/tags from .env: DOCKER_IMAGE, DOCKER_TAG_ENV, DOCKER_TAG_PROD):"
    echo "    up-code                 - Build image (tagged :DOCKER_TAG_ENV), push if DOCKER_PUSH_* set, start stack"
    echo "    down-code               - Stop code stack"
    echo "    rebuild-code            - No-cache build, push if set, start code stack"
    echo "    down-code-remove-images - Stop code and remove local images"
    echo "    Push: set DOCKER_PUSH_TAG=topteens_django_prod or topteens_django_env (or DOCKER_PUSH_IMAGE=...)"
    echo ""
    echo "  Legacy (unified compose):"
    echo "    deploy       - Full deploy (docker-compose.yml)"
    echo "    rebuild      - Full deploy with --no-cache"
    echo "    web          - Build & update web + celery + celery_beat (shared image)"
    echo "    web-rebuild  - Same as web with --no-cache build"
    echo "    rollback     - Rollback to :previous"
    echo "    stop         - docker compose down"
    exit 1
    ;;
esac
