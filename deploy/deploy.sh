#!/usr/bin/env bash
# =============================================================================
# TopTeen env-aware deployment orchestrator (two stacks: BASE + APP)
#
#   ./deploy/deploy.sh <env> <command> [args]
#   <env> = staging | production  (must have deploy/environments/<env>.env)
#
# BASE stack (infra, rarely changes):  nginx LB, redis, elasticsearch, mariadb, certbot
# APP  stack (code, changes often):    web (scaled), celery, celery_beat
#
# Examples:
#   ./deploy/deploy.sh production init            # create shared network + volumes (once)
#   ./deploy/deploy.sh production base up          # start infra + load balancer
#   ./deploy/deploy.sh production app deploy       # build + tag + roll app, migrate, health-check
#   ./deploy/deploy.sh production up               # init + base up + app deploy (full bring-up)
#   ./deploy/deploy.sh production app scale 5      # scale web replicas to 5
#   ./deploy/deploy.sh production app rollback     # revert app to :<tag>-previous
#   ./deploy/deploy.sh production status           # list this project's containers
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
STACKS_DIR="$SCRIPT_DIR/stacks"
ENV_DIR="$SCRIPT_DIR/environments"

log() { echo "[deploy] $*"; }
err() { echo "[deploy] ERROR: $*" >&2; }

# ---- docker compose detection ----------------------------------------------
COMPOSE=""
for c in "docker compose" "docker-compose"; do
  if $c version >/dev/null 2>&1; then COMPOSE="$c"; break; fi
done
[ -z "$COMPOSE" ] && { err "docker compose (or docker-compose) is required."; exit 1; }

usage() {
  cat <<'EOF'
Usage: ./deploy/deploy.sh <env> <command> [args]

  <env>                staging | production  (reads deploy/environments/<env>.env)

Top-level commands:
  init                 Create shared external network + volumes (run once per env)
  up                   init + base up + app deploy (full bring-up)
  down                 Stop APP then BASE stack (volumes kept)
  status               List all containers for this project+env
  push                 Push app + nginx images (their <env> tags)

BASE stack (infra - nginx LB, redis, elasticsearch, mariadb, certbot):
  base up | down | rebuild | reload | ps | logs

APP stack (code - web replicas, celery, celery_beat):
  app deploy           Tag :previous, build, (push), recreate, migrate+collectstatic, health-check (auto-rollback)
  app build            Build the app image only
  app up | down        Start / stop app stack (no build)
  app rollback         Revert to :<tag>-previous image
  app scale <N>        Scale web replicas to N
  app migrate          Run migrations once (single web container)
  app collectstatic    Collect static once (single web container)
  app shell            Open a shell in a web container
  app ps | logs
EOF
}

ENV="${1:-}"
[ -z "$ENV" ] && { usage; exit 1; }
[ "$ENV" = "-h" ] || [ "$ENV" = "--help" ] && { usage; exit 0; }
shift

ENV_FILE="$ENV_DIR/${ENV}.env"
if [ ! -f "$ENV_FILE" ]; then
  err "Env file not found: $ENV_FILE"
  echo "  Create it:  cp $ENV_DIR/${ENV}.env.example $ENV_FILE  && edit values" >&2
  exit 1
fi

# Safe single-token read from env file. `|| true` so a missing key returns empty
# instead of a non-zero status (which, under `set -e`, would abort the script).
read_env() { grep -E "^$1=" "$ENV_FILE" 2>/dev/null | head -1 | cut -d= -f2- | sed 's/[[:space:]]*$//' || true; }

PROJECT_NAME="$(read_env PROJECT_NAME)"; PROJECT_NAME="${PROJECT_NAME:-topteen}"
ENVIRONMENT="$(read_env ENVIRONMENT)"; ENVIRONMENT="${ENVIRONMENT:-$ENV}"
APP_IMAGE="$(read_env APP_IMAGE)"; APP_IMAGE="${APP_IMAGE:-developertopteen/demotopteen}"
APP_IMAGE_TAG="$(read_env APP_IMAGE_TAG)"; APP_IMAGE_TAG="${APP_IMAGE_TAG:-$ENVIRONMENT}"
NGINX_IMAGE="$(read_env NGINX_IMAGE)"; NGINX_IMAGE="${NGINX_IMAGE:-developertopteen/demotopteen-nginx}"
NGINX_IMAGE_TAG="$(read_env NGINX_IMAGE_TAG)"; NGINX_IMAGE_TAG="${NGINX_IMAGE_TAG:-$ENVIRONMENT}"
BASE_PROFILES="$(read_env BASE_PROFILES)"
APP_PORT="$(read_env APP_PORT)"; APP_PORT="${APP_PORT:-80}"
HTTPS_PORT="$(read_env HTTPS_PORT)"; HTTPS_PORT="${HTTPS_PORT:-443}"
WEB_REPLICAS="$(read_env WEB_REPLICAS)"; WEB_REPLICAS="${WEB_REPLICAS:-3}"
DOCKER_PUSH_REGISTRY="$(read_env DOCKER_PUSH_REGISTRY)"

BASE_PROJECT="${PROJECT_NAME}-${ENVIRONMENT}-base"
APP_PROJECT="${PROJECT_NAME}-${ENVIRONMENT}-app"
NET_NAME="${PROJECT_NAME}-${ENVIRONMENT}-net"
HEALTH_URL="http://localhost:${APP_PORT}/"

# compose wrappers (profiles only apply to the base stack)
base_compose() { COMPOSE_PROFILES="${BASE_PROFILES}" $COMPOSE --env-file "$ENV_FILE" -p "$BASE_PROJECT" -f "$STACKS_DIR/base.yml" "$@"; }
app_compose()  { COMPOSE_PROFILES="" $COMPOSE --env-file "$ENV_FILE" -p "$APP_PROJECT" -f "$STACKS_DIR/app.yml" "$@"; }

banner() {
  log "env=$ENVIRONMENT project=$PROJECT_NAME"
  log "  base project : $BASE_PROJECT   (profiles: ${BASE_PROFILES:-none})"
  log "  app project  : $APP_PROJECT    (image: ${APP_IMAGE}:${APP_IMAGE_TAG}, web replicas: ${WEB_REPLICAS})"
  log "  network      : $NET_NAME   ports: ${APP_PORT}(http) ${HTTPS_PORT}(https)"
}

check_port_busy() {
  local port="$1"; [ -z "$port" ] && return 1
  if command -v ss >/dev/null 2>&1; then ss -tlnp 2>/dev/null | grep -qE ":$port\b"; return $?; fi
  if command -v netstat >/dev/null 2>&1; then netstat -tln 2>/dev/null | grep -qE "[:.]$port\b"; return $?; fi
  return 1
}

warn_ports() {
  local busy=0
  check_port_busy "$APP_PORT"  && { err "APP_PORT $APP_PORT is in use. Change APP_PORT in $ENV_FILE."; busy=1; }
  check_port_busy "$HTTPS_PORT" && { err "HTTPS_PORT $HTTPS_PORT is in use. Change HTTPS_PORT in $ENV_FILE."; busy=1; }
  if [ "$busy" = 1 ]; then err "Aborting (port conflict)."; exit 1; fi
  return 0
}

# ---- shared network + volumes (created once) --------------------------------
ensure_infra() {
  docker network inspect "$NET_NAME" >/dev/null 2>&1 || { log "Creating network $NET_NAME"; docker network create "$NET_NAME" >/dev/null; }
  local v
  for v in static media redis es db; do
    local vol="${PROJECT_NAME}-${ENVIRONMENT}-$v"
    docker volume inspect "$vol" >/dev/null 2>&1 || { log "Creating volume $vol"; docker volume create "$vol" >/dev/null; }
  done
  return 0
}

health_check() {
  local url="$1" retries="${2:-12}" interval="${3:-5}" i=1 code
  log "Health check $url (${retries}x every ${interval}s)..."
  while [ "$i" -le "$retries" ]; do
    code="$(curl -s -o /dev/null -m 10 -w '%{http_code}' "$url" 2>/dev/null || echo 000)"
    if [ "$code" != "000" ] && [ "$code" -lt 500 ]; then
      log "Health OK (HTTP $code)."
      return 0
    fi
    log "  attempt $i/$retries -> HTTP $code, retry in ${interval}s"
    sleep "$interval"; i=$((i + 1))
  done
  return 1
}

# ---- APP: release tasks (run ONCE, not per replica) -------------------------
app_release() {
  log "Running migrations (single web container)..."
  app_compose exec -T web python manage.py migrate --noinput || log "migrate failed/skipped (continuing)"
  log "Collecting static (single web container)..."
  app_compose exec -T web python manage.py collectstatic --noinput --clear || log "collectstatic failed (continuing)"
}

maybe_push() {
  local reg="${DOCKER_PUSH_REGISTRY}"
  [ -z "$reg" ] && return 0
  local src="${APP_IMAGE}:${APP_IMAGE_TAG}" dst="${reg%/}/${APP_IMAGE}:${APP_IMAGE_TAG}"
  log "Pushing $dst ..."
  docker tag "$src" "$dst" && docker push "$dst" || err "push failed (docker login?)"
}

push_images() {
  local reg="${DOCKER_PUSH_REGISTRY}"
  for pair in "${APP_IMAGE}:${APP_IMAGE_TAG}" "${NGINX_IMAGE}:${NGINX_IMAGE_TAG}"; do
    if ! docker image inspect "$pair" >/dev/null 2>&1; then log "skip $pair (not built)"; continue; fi
    local dst="$pair"; [ -n "$reg" ] && dst="${reg%/}/$pair"
    [ "$dst" != "$pair" ] && docker tag "$pair" "$dst"
    log "Pushing $dst ..."; docker push "$dst" || err "push failed for $dst (docker login?)"
  done
}

app_deploy() {
  banner
  ensure_infra
  local img="${APP_IMAGE}:${APP_IMAGE_TAG}"
  if docker image inspect "$img" >/dev/null 2>&1; then
    docker tag "$img" "${APP_IMAGE}:${APP_IMAGE_TAG}-previous" && log "Tagged ${APP_IMAGE}:${APP_IMAGE_TAG}-previous (rollback point)"
  else
    log "$img not present (first deploy) - no :previous tag"
  fi
  log "Building app image $img ..."
  app_compose build web || { err "Build failed. No containers changed."; exit 1; }
  maybe_push
  log "(Re)starting APP stack..."
  app_compose up -d --force-recreate --remove-orphans web celery celery_beat
  sleep 5
  app_release
  if health_check "$HEALTH_URL"; then
    log "APP deploy finished successfully."
    banner
    return 0
  fi
  err "Health check failed. Recent web logs:"
  app_compose logs --tail=100 web 2>&1 | sed 's/^/[deploy]   /' >&2 || true
  err "Attempting rollback..."
  if app_rollback_internal; then
    err "Rolled back to previous. Fix and redeploy."
    exit 1
  fi
  err "Rollback failed or no :previous image. APP stack may be down."
  exit 1
}

app_rollback_internal() {
  local prev="${APP_IMAGE}:${APP_IMAGE_TAG}-previous"
  docker image inspect "$prev" >/dev/null 2>&1 || { err "No $prev to roll back to."; return 1; }
  docker tag "$prev" "${APP_IMAGE}:${APP_IMAGE_TAG}"
  app_compose up -d --force-recreate web celery celery_beat
  sleep 3
  health_check "$HEALTH_URL" 4 4
}

case "${1:-}" in
  "" ) usage; exit 1 ;;

  init)   banner; ensure_infra; log "Infra ready. Next: base up, then app deploy." ;;

  up)
    banner; ensure_infra; warn_ports
    log "Starting BASE stack..."; base_compose up -d
    app_deploy
    ;;

  down)
    log "Stopping APP stack..."; app_compose down 2>/dev/null || true
    log "Stopping BASE stack..."; base_compose down 2>/dev/null || true
    log "Down. (network + volumes kept; use docker volume rm to purge data)"
    ;;

  status)
    banner
    docker ps -a \
      --filter "label=com.topteen.project=${PROJECT_NAME}" \
      --filter "label=com.topteen.environment=${ENVIRONMENT}" \
      --format 'table {{.Names}}\t{{.Label "com.topteen.stack"}}\t{{.Label "com.topteen.service"}}\t{{.Status}}\t{{.Ports}}'
    ;;

  push) banner; push_images ;;

  base)
    action="${2:-}"
    case "$action" in
      up)      banner; ensure_infra; warn_ports; base_compose up -d; log "BASE stack up." ;;
      down)    base_compose down 2>/dev/null || true; log "BASE stack down." ;;
      rebuild) ensure_infra; warn_ports; base_compose build --no-cache; base_compose up -d --force-recreate; log "BASE stack rebuilt." ;;
      reload)  log "Reloading nginx (pick up renewed certs/config)..."; base_compose exec nginx nginx -s reload && log "nginx reloaded." ;;
      ps)      base_compose ps ;;
      logs)    shift 2 || true; base_compose logs -f --tail=200 "$@" ;;
      *) err "Unknown: base $action"; usage; exit 1 ;;
    esac
    ;;

  app)
    action="${2:-}"
    case "$action" in
      deploy)       app_deploy ;;
      build)        banner; app_compose build web; log "App image built." ;;
      up)           banner; ensure_infra; app_compose up -d; log "APP stack up." ;;
      down)         app_compose down 2>/dev/null || true; log "APP stack down." ;;
      rollback)     banner; app_rollback_internal && log "Rollback done." || { err "Rollback failed."; exit 1; } ;;
      scale)        n="${3:-}"; [ -z "$n" ] && { err "Usage: app scale <N>"; exit 1; }; app_compose up -d --no-recreate --scale web="$n" web; log "Scaled web to $n." ;;
      migrate)      app_compose exec -T web python manage.py migrate --noinput ;;
      collectstatic) app_compose exec -T web python manage.py collectstatic --noinput --clear ;;
      shell)        app_compose exec web bash || app_compose exec web sh ;;
      ps)           app_compose ps ;;
      logs)         shift 2 || true; app_compose logs -f --tail=200 "$@" ;;
      *) err "Unknown: app $action"; usage; exit 1 ;;
    esac
    ;;

  -h|--help|help) usage ;;
  *) err "Unknown command: $1"; usage; exit 1 ;;
esac
