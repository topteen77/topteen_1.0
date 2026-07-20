#!/usr/bin/env bash
# =============================================================================
# TopTeen docker_files - single independent container deploy
#
# Builds and runs the full project in Docker. App path: /app/topteen1.0
#
# Usage:
#   ./docker_files/deploy.sh up              # build + start + migrate + health-check
#   ./docker_files/deploy.sh deploy          # production: tag :previous, rebuild, health-check, push on success, rollback on fail
#   ./docker_files/deploy.sh rollback        # restore :previous images and recreate containers
#   ./docker_files/deploy.sh build           # build images only
#   ./docker_files/deploy.sh down            # stop containers (volumes kept)
#   ./docker_files/deploy.sh restart         # recreate app services
#   ./docker_files/deploy.sh status          # show containers
#   ./docker_files/deploy.sh logs [svc]      # follow logs
#   ./docker_files/deploy.sh migrate         # run migrations once
#   ./docker_files/deploy.sh collectstatic   # collect static once
#   ./docker_files/deploy.sh shell           # bash in a web container
#   ./docker_files/deploy.sh push            # push images (if registry set)
#
# First time:
#   cp docker_files/env.example docker_files/.env
#   # ensure repo-root .env has Django secrets / DB credentials
#   ./docker_files/deploy.sh up
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
COMPOSE_FILE="$SCRIPT_DIR/docker-compose.yml"
ENV_FILE="$SCRIPT_DIR/.env"
ROOT_ENV="$REPO_ROOT/.env"

log() { echo "[docker_files] $*"; }
err() { echo "[docker_files] ERROR: $*" >&2; }

# Run a command with sudo when needed (data dirs under /data, docker.sock, etc.)
SUDO=""
if [ "$(id -u)" -ne 0 ]; then
  if command -v sudo >/dev/null 2>&1; then SUDO="sudo"; fi
fi

# Prefer plain docker; fall back to sudo docker when socket access is denied
DOCKER="docker"
if ! docker info >/dev/null 2>&1; then
  if [ -n "$SUDO" ] && $SUDO docker info >/dev/null 2>&1; then
    DOCKER="$SUDO docker"
    log "Docker socket needs elevated access — using: sudo docker"
    log "  (optional permanent fix: sudo usermod -aG docker \$USER && newgrp docker)"
  else
    err "Cannot talk to Docker daemon. Install Docker or fix /var/run/docker.sock permissions."
    exit 1
  fi
fi

# ---- docker compose detection ----------------------------------------------
COMPOSE=""
if $DOCKER compose version >/dev/null 2>&1; then
  COMPOSE="$DOCKER compose"
elif command -v docker-compose >/dev/null 2>&1 && docker-compose version >/dev/null 2>&1; then
  COMPOSE="docker-compose"
elif [ -n "$SUDO" ] && $SUDO docker-compose version >/dev/null 2>&1; then
  COMPOSE="$SUDO docker-compose"
fi
[ -z "$COMPOSE" ] && { err "docker compose (or docker-compose) is required."; exit 1; }

usage() {
  cat <<'EOF'
Usage: ./docker_files/deploy.sh <command> [args]

  up              Rebuild images, recreate containers, migrate, health-check, print URLs
  deploy          Production deploy: tag :previous, rebuild (BUILD_PULL=1), health-check,
                  push images on success, auto-rollback on failure
  rollback        Restore app+nginx images from :<tag>-previous and recreate containers
  build           Build app + nginx images only
  down            Stop and remove containers (images + data kept)
  destroy         Remove containers AND project images (data under DATA_ROOT kept)
  restart         Force-recreate web/celery/celery_beat/nginx
  status          List project containers + SSL status
  logs [service]  Follow logs (optional service name)
  migrate         Run Django migrate once
  collectstatic   Run collectstatic once
  shell           Open a shell in a web container
  push            Push app + nginx images to DOCKER_PUSH_REGISTRY
  reload-nginx    Reload nginx after editing ${DATA_ROOT}/nginx/conf
  reseed-nginx    Rewrite nginx conf from templates (SERVER_NAMES) + reload
  debug           Curl/nginx/web diagnostics (no host Python needed)

  ssl status      Show cert paths / expiry
  ssl self-signed [domain]   Generate self-signed cert into ${DATA_ROOT}/nginx/ssl
  ssl obtain      Let's Encrypt obtain (needs DNS + APP_PORT=80 + CERTBOT_EMAIL)
  ssl renew       Renew LE certs, sync to nginx/ssl, reload nginx
  ssl sync        Copy certbot live certs -> nginx/ssl and reload

SSL env (docker_files/.env):
  SSL_MODE=off|self-signed|letsencrypt   (auto on 'up')
  SSL_CERT_PATH is always ${DATA_ROOT}/nginx/ssl
  CERTBOT_EMAIL=you@example.com
  COMPOSE_PROFILES=ssl                   (background renew every 12h)
  SERVER_NAMES=test.topteen.in
  APP_PORT=80  HTTPS_PORT=443            (domain, no port in URL)
  TEST_HTTP_PORT=8005 TEST_HTTPS_PORT=8443  (IP testing only)

Cron renew example:
  0 4 * * * /home/ubuntu/topteen_1.0/docker_files/deploy.sh ssl renew >> /data/topteens/logs/ssl-renew.log 2>&1
EOF
}

ensure_env() {
  if [ ! -f "$ENV_FILE" ]; then
    if [ -f "$SCRIPT_DIR/env.example" ]; then
      log "Creating $ENV_FILE from env.example"
      cp "$SCRIPT_DIR/env.example" "$ENV_FILE"
    else
      err "Missing $ENV_FILE and env.example"
      exit 1
    fi
  fi
  if [ ! -f "$ROOT_ENV" ]; then
    err "Repo-root .env not found at $ROOT_ENV (Django secrets / DB)."
    err "Create it before deploying."
    exit 1
  fi
}

read_env() {
  grep -E "^$1=" "$ENV_FILE" 2>/dev/null | head -1 | cut -d= -f2- | sed 's/[[:space:]]*$//' || true
}

dc() {
  # shellcheck disable=SC2086
  $COMPOSE --env-file "$ENV_FILE" -p "${PROJECT_NAME}-topteen10" -f "$COMPOSE_FILE" "$@"
}

# Create path; use sudo if /data (or DATA_ROOT) is not writable by current user
mkdir_p() {
  local path="$1"
  if mkdir -p "$path" 2>/dev/null; then
    return 0
  fi
  if [ -n "$SUDO" ]; then
    log "Need elevated access for $path — using sudo"
    $SUDO mkdir -p "$path"
    # Let deploy user (and docker) write collectstatic / logs / conf
    $SUDO chown -R "$(id -u):$(id -g)" "$path" 2>/dev/null || true
    $SUDO chmod -R u+rwX,g+rwX "$path" 2>/dev/null || true
    return 0
  fi
  err "Cannot create $path (permission denied). Run:"
  err "  sudo mkdir -p $path && sudo chown -R \$USER:\$USER $DATA_ROOT"
  exit 1
}

write_file() {
  local dst="$1" content="$2"
  if [ -w "$(dirname "$dst")" ] 2>/dev/null || [ -w "$dst" ] 2>/dev/null; then
    printf '%s\n' "$content" > "$dst"
    return 0
  fi
  if [ -n "$SUDO" ]; then
    printf '%s\n' "$content" | $SUDO tee "$dst" >/dev/null
    $SUDO chown "$(id -u):$(id -g)" "$dst" 2>/dev/null || true
    return 0
  fi
  err "Cannot write $dst (permission denied)."
  exit 1
}

ensure_data_dirs() {
  DATA_ROOT="$(read_env DATA_ROOT)"; DATA_ROOT="${DATA_ROOT:-/data/topteens}"
  SERVER_NAMES="$(read_env SERVER_NAMES)"; SERVER_NAMES="${SERVER_NAMES:-localhost}"
  CLIENT_MAX_BODY_SIZE="$(read_env CLIENT_MAX_BODY_SIZE)"; CLIENT_MAX_BODY_SIZE="${CLIENT_MAX_BODY_SIZE:-25M}"

  log "Ensuring data dirs under $DATA_ROOT ..."
  # Parent may exist (e.g. /data/topteens) but not be writable — fix once
  if [ ! -d "$DATA_ROOT" ]; then
    mkdir_p "$DATA_ROOT"
  elif [ ! -w "$DATA_ROOT" ]; then
    if [ -n "$SUDO" ]; then
      log "Fixing ownership of $DATA_ROOT for user $(id -un) ..."
      $SUDO chown -R "$(id -u):$(id -g)" "$DATA_ROOT" || true
      $SUDO chmod -R u+rwX,g+rwX "$DATA_ROOT" || true
    else
      err "$DATA_ROOT is not writable. Run: sudo chown -R \$USER:\$USER $DATA_ROOT"
      exit 1
    fi
  fi

  for d in \
    nginx/static nginx/media nginx/conf nginx/ssl nginx/logs \
    mariadb elasticsearch redis logs \
    certbot/conf certbot/webroot
  do
    mkdir_p "$DATA_ROOT/$d"
  done

  # Seed / refresh nginx conf from templates (edit live under nginx/conf afterward)
  # Pass force=1 to overwrite (used on up / reseed-nginx so IP default_server applies)
  reseed_nginx_from_templates() {
    local force="${1:-0}"
    local http_conf="$DATA_ROOT/nginx/conf/00-http.conf"
    local https_conf="$DATA_ROOT/nginx/conf/10-https.conf"
    local tpl_http="$SCRIPT_DIR/nginx/templates/00-http.conf.template"
    local tpl_https="$SCRIPT_DIR/nginx/templates/10-https.conf.template"

    seed_conf() {
      local src="$1" dst="$2" rendered
      [ -f "$src" ] || return 0
      if [ "$force" != "1" ] && [ -f "$dst" ]; then
        return 0
      fi
      rendered="$(sed -e "s|__SERVER_NAMES__|${SERVER_NAMES}|g" \
                      -e "s|__CLIENT_MAX_BODY_SIZE__|${CLIENT_MAX_BODY_SIZE}|g" \
                      "$src")"
      write_file "$dst" "$rendered"
      log "Seeded $dst (server_name=${SERVER_NAMES} _)"
    }
    seed_conf "$tpl_http" "$http_conf"
    SSL_CERT_PATH="${DATA_ROOT}/nginx/ssl"
    if [ -f "$SSL_CERT_PATH/cert.pem" ] && [ -f "$SSL_CERT_PATH/key.pem" ]; then
      seed_conf "$tpl_https" "$https_conf"
    fi
  }
  reseed_nginx_from_templates 0
}

prepare() {
  ensure_env
  PROJECT_NAME="$(read_env PROJECT_NAME)"; PROJECT_NAME="${PROJECT_NAME:-topteen}"
  APP_IMAGE="$(read_env APP_IMAGE)"; APP_IMAGE="${APP_IMAGE:-developertopteen/demotopteen}"
  APP_IMAGE_TAG="$(read_env APP_IMAGE_TAG)"; APP_IMAGE_TAG="${APP_IMAGE_TAG:-topteen1.0}"
  NGINX_IMAGE="$(read_env NGINX_IMAGE)"; NGINX_IMAGE="${NGINX_IMAGE:-developertopteen/demotopteen-nginx}"
  NGINX_IMAGE_TAG="$(read_env NGINX_IMAGE_TAG)"; NGINX_IMAGE_TAG="${NGINX_IMAGE_TAG:-topteen1.0}"
  APP_PORT="$(read_env APP_PORT)"; APP_PORT="${APP_PORT:-80}"
  HTTPS_PORT="$(read_env HTTPS_PORT)"; HTTPS_PORT="${HTTPS_PORT:-443}"
  TEST_HTTP_PORT="$(read_env TEST_HTTP_PORT)"; TEST_HTTP_PORT="${TEST_HTTP_PORT:-8005}"
  TEST_HTTPS_PORT="$(read_env TEST_HTTPS_PORT)"; TEST_HTTPS_PORT="${TEST_HTTPS_PORT:-8443}"
  PUBLIC_IP="$(read_env PUBLIC_IP)"
  DOCKER_PUSH_REGISTRY="$(read_env DOCKER_PUSH_REGISTRY)"
  COMPOSE_PROFILES="$(read_env COMPOSE_PROFILES)"
  SSL_MODE="$(read_env SSL_MODE)"; SSL_MODE="${SSL_MODE:-off}"   # off | self-signed | letsencrypt
  CERTBOT_EMAIL="$(read_env CERTBOT_EMAIL)"
  # Prefer docker_files/.env, else repo-root .env
  if [ -z "$CERTBOT_EMAIL" ] && [ -f "$ROOT_ENV" ]; then
    CERTBOT_EMAIL="$(grep -E '^CERTBOT_EMAIL=' "$ROOT_ENV" 2>/dev/null | head -1 | cut -d= -f2- | sed 's/[[:space:]]*$//' || true)"
  fi
  SSL_CERT_PATH="${DATA_ROOT:-/data/topteens}/nginx/ssl"
  CERTBOT_CONF="${DATA_ROOT:-/data/topteens}/certbot/conf"
  CERTBOT_WEBROOT="${DATA_ROOT:-/data/topteens}/certbot/webroot"
  export COMPOSE_PROFILES
  ensure_data_dirs
  # Re-bind SSL paths after DATA_ROOT is set
  SSL_CERT_PATH="${DATA_ROOT}/nginx/ssl"
  CERTBOT_CONF="${DATA_ROOT}/certbot/conf"
  CERTBOT_WEBROOT="${DATA_ROOT}/certbot/webroot"
}

banner() {
  log "project=${PROJECT_NAME}-topteen10"
  log "  app image   : ${APP_IMAGE}:${APP_IMAGE_TAG}"
  log "  nginx image : ${NGINX_IMAGE}:${NGINX_IMAGE_TAG}"
  log "  app path    : /app/topteen1.0"
  log "  data root   : ${DATA_ROOT:-/data/topteens}"
  log "  ssl path    : ${SSL_CERT_PATH:-${DATA_ROOT}/nginx/ssl}"
  log "  ssl mode    : ${SSL_MODE:-off}"
  log "  server_name : ${SERVER_NAMES:-localhost}"
  log "  domain ports: ${APP_PORT} / ${HTTPS_PORT:-443}  (no port in URL)"
  log "  test ports  : ${TEST_HTTP_PORT} / ${TEST_HTTPS_PORT}  (IP testing only)"
  log "  profiles    : ${COMPOSE_PROFILES:-none}"
}

ssl_has_certs() {
  [ -f "${SSL_CERT_PATH}/cert.pem" ] && [ -f "${SSL_CERT_PATH}/key.pem" ]
}

ssl_enable_https_conf() {
  local https_conf="$DATA_ROOT/nginx/conf/10-https.conf"
  local tpl_https="$SCRIPT_DIR/nginx/templates/10-https.conf.template"
  if [ ! -f "$https_conf" ] && [ -f "$tpl_https" ]; then
    local rendered
    rendered="$(sed -e "s|__SERVER_NAMES__|${SERVER_NAMES}|g" \
                    -e "s|__CLIENT_MAX_BODY_SIZE__|${CLIENT_MAX_BODY_SIZE:-25M}|g" \
                    "$tpl_https")"
    write_file "$https_conf" "$rendered"
    log "Enabled HTTPS nginx conf: $https_conf"
  fi
  # Restore if previously disabled by entrypoint
  if [ -f "$DATA_ROOT/nginx/conf/10-https.conf.disabled" ] && [ ! -f "$https_conf" ]; then
    mv "$DATA_ROOT/nginx/conf/10-https.conf.disabled" "$https_conf" 2>/dev/null || true
  fi
}

ssl_primary_domain() {
  local d
  for d in $SERVER_NAMES; do
    [ "$d" = "localhost" ] && continue
    [ "$d" = "127.0.0.1" ] && continue
    case "$d" in
      *[!0-9.]*) echo "$d"; return 0 ;;  # has a non-digit/non-dot => hostname
    esac
  done
  echo ""
}

ssl_domain_args() {
  local d
  for d in $SERVER_NAMES; do
    [[ "$d" =~ ^[0-9.]+$ ]] && continue
    [ "$d" = "localhost" ] && continue
    printf ' -d %s' "$d"
  done
}

do_ssl_self_signed() {
  local domain="${1:-}"
  [ -z "$domain" ] && domain="$(ssl_primary_domain)"
  [ -z "$domain" ] && domain="localhost"
  mkdir_p "$SSL_CERT_PATH"
  log "Generating self-signed cert for $domain -> $SSL_CERT_PATH"
  if ! command -v openssl >/dev/null 2>&1; then
    err "openssl not found on host. Install openssl or use: ./docker_files/deploy.sh ssl obtain"
    exit 1
  fi
  local san
  if [[ "$domain" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    san="IP:$domain,DNS:$domain"
  else
    san="DNS:$domain,DNS:*.${domain},DNS:www.${domain}"
  fi
  openssl genrsa -out "$SSL_CERT_PATH/key.pem" 2048
  openssl req -new -x509 -key "$SSL_CERT_PATH/key.pem" -out "$SSL_CERT_PATH/cert.pem" -days 365 \
    -subj "/C=IN/ST=State/L=City/O=TopTeen/CN=$domain" \
    -addext "subjectAltName=$san"
  chmod 600 "$SSL_CERT_PATH/key.pem"
  chmod 644 "$SSL_CERT_PATH/cert.pem"
  ssl_enable_https_conf
  log "Self-signed SSL ready: $SSL_CERT_PATH/cert.pem"
}

do_ssl_sync() {
  local primary live_dir
  primary="$(ssl_primary_domain)"
  [ -z "$primary" ] && { err "No public domain in SERVER_NAMES"; exit 1; }
  live_dir="$CERTBOT_CONF/live/$primary"
  if [ ! -f "$live_dir/fullchain.pem" ]; then
    # fallback: first live dir
    live_dir="$(ls -d "$CERTBOT_CONF"/live/*/ 2>/dev/null | head -1 | sed 's|/$||' || true)"
  fi
  [ -z "$live_dir" ] || [ ! -f "$live_dir/fullchain.pem" ] && {
    err "No Let's Encrypt live certs under $CERTBOT_CONF/live/"
    exit 1
  }
  mkdir_p "$SSL_CERT_PATH"
  cp -f "$live_dir/fullchain.pem" "$SSL_CERT_PATH/cert.pem"
  cp -f "$live_dir/privkey.pem" "$SSL_CERT_PATH/key.pem"
  chmod 644 "$SSL_CERT_PATH/cert.pem"
  chmod 600 "$SSL_CERT_PATH/key.pem"
  ssl_enable_https_conf
  log "Synced $live_dir -> $SSL_CERT_PATH"
}

do_ssl_obtain() {
  local email="${CERTBOT_EMAIL:-}"
  local domains_args primary
  domains_args="$(ssl_domain_args)"
  primary="$(ssl_primary_domain)"
  [ -z "$primary" ] && { err "SERVER_NAMES has no public domain for Let's Encrypt."; exit 1; }
  [ -z "$email" ] && { err "Set CERTBOT_EMAIL in docker_files/.env (or repo .env)"; exit 1; }
  if [ "${APP_PORT}" != "80" ]; then
    log "WARN: APP_PORT=$APP_PORT (Let's Encrypt HTTP-01 usually needs port 80 published)."
    log "      Set APP_PORT=80 HTTPS_PORT=443 in docker_files/.env for production LE."
  fi
  mkdir_p "$CERTBOT_CONF" "$CERTBOT_WEBROOT" "$SSL_CERT_PATH"
  chmod 755 "$CERTBOT_WEBROOT" 2>/dev/null || true
  log "Obtaining Let's Encrypt cert for:$domains_args"
  log "  webroot=$CERTBOT_WEBROOT  conf=$CERTBOT_CONF  email=$email"
  # Ensure nginx is up so ACME challenge is reachable
  dc up -d nginx 2>/dev/null || true
  # shellcheck disable=SC2086
  $DOCKER run --rm \
    -v "$CERTBOT_CONF:/etc/letsencrypt" \
    -v "$CERTBOT_WEBROOT:/var/www/certbot" \
    -v "$SSL_CERT_PATH:/nginx-ssl" \
    -v "$SCRIPT_DIR/ssl-deploy-hook.sh:/hooks/ssl-deploy-hook.sh:ro" \
    -e NGINX_SSL_DIR=/nginx-ssl \
    certbot/certbot certonly --webroot -w /var/www/certbot \
      $domains_args \
      --email "$email" \
      --agree-tos \
      --non-interactive \
      --deploy-hook /hooks/ssl-deploy-hook.sh
  do_ssl_sync
  # Enable ssl profile renew loop if not already
  if [[ ",${COMPOSE_PROFILES}," != *",ssl,"* ]]; then
    log "Tip: set COMPOSE_PROFILES=ssl in docker_files/.env for auto-renew container."
  fi
  log "Reloading nginx..."
  dc up -d --force-recreate nginx 2>/dev/null || true
  dc exec nginx nginx -s reload 2>/dev/null || true
  log "Let's Encrypt SSL installed."
}

do_ssl_renew() {
  mkdir_p "$CERTBOT_CONF" "$CERTBOT_WEBROOT" "$SSL_CERT_PATH"
  log "Renewing Let's Encrypt certificates..."
  $DOCKER run --rm \
    -v "$CERTBOT_CONF:/etc/letsencrypt" \
    -v "$CERTBOT_WEBROOT:/var/www/certbot" \
    -v "$SSL_CERT_PATH:/nginx-ssl" \
    -v "$SCRIPT_DIR/ssl-deploy-hook.sh:/hooks/ssl-deploy-hook.sh:ro" \
    -e NGINX_SSL_DIR=/nginx-ssl \
    certbot/certbot renew --webroot -w /var/www/certbot \
      --deploy-hook /hooks/ssl-deploy-hook.sh \
      --non-interactive || log "renew returned non-zero (may be not-due-yet)"
  if ssl_has_certs; then
    ssl_enable_https_conf
    dc exec nginx nginx -s reload 2>/dev/null || dc up -d --force-recreate nginx || true
    log "SSL renew done; nginx reloaded."
  else
    err "No certs in $SSL_CERT_PATH after renew."
    exit 1
  fi
}

do_ssl_status() {
  log "SSL_CERT_PATH=$SSL_CERT_PATH"
  if ssl_has_certs; then
    log "certs: present"
    if command -v openssl >/dev/null 2>&1; then
      openssl x509 -in "$SSL_CERT_PATH/cert.pem" -noout -subject -dates 2>/dev/null | sed 's/^/[docker_files]   /'
    fi
  else
    log "certs: MISSING (HTTP only)"
  fi
  log "certbot conf: $CERTBOT_CONF"
  ls -la "$CERTBOT_CONF/live" 2>/dev/null | sed 's/^/[docker_files]   /' || log "  (no certbot live certs yet)"
}

ensure_ssl_on_up() {
  case "${SSL_MODE}" in
    self-signed|selfsigned)
      if ! ssl_has_certs; then
        log "SSL_MODE=self-signed and no certs — generating..."
        do_ssl_self_signed
      else
        log "SSL certs already present at $SSL_CERT_PATH"
        ssl_enable_https_conf
      fi
      ;;
    letsencrypt|le|certbot)
      if ! ssl_has_certs; then
        log "SSL_MODE=letsencrypt and no certs — obtaining (needs DNS + port 80)..."
        do_ssl_obtain
      else
        log "SSL certs already present at $SSL_CERT_PATH"
        ssl_enable_https_conf
      fi
      ;;
    off|false|no|"")
      log "SSL_MODE=off (HTTP only unless certs already exist)"
      if ssl_has_certs; then
        ssl_enable_https_conf
      fi
      ;;
    *)
      log "Unknown SSL_MODE=$SSL_MODE (use off|self-signed|letsencrypt)"
      ;;
  esac
}

do_up() {
  banner
  # Clean restart: remove old project containers, rebuild images, recreate
  log "Stopping existing project containers (if any)..."
  dc down --remove-orphans 2>/dev/null || true
  # Refresh nginx conf so IP default_server / SERVER_NAMES updates apply
  reseed_nginx_from_templates 1
  do_build
  ensure_ssl_on_up
  # HTTPS template may need seed after certs appear
  reseed_nginx_from_templates 1
  log "Starting stack (force recreate)..."
  dc up -d --force-recreate --remove-orphans
  sleep 8
  release_tasks
  local health_url="http://127.0.0.1:${APP_PORT}/"
  if health_check "$health_url"; then
    log "Deploy finished successfully."
    banner
    dc ps
    print_deploy_urls
    return 0
  fi
  err "Health check failed. Recent web logs:"
  dc logs --tail=80 web 2>&1 | sed 's/^/[docker_files]   /' >&2 || true
  err "Run: ./docker_files/deploy.sh debug"
  exit 1
}

# Public site / admin URLs + log paths printed after a successful deploy
print_deploy_urls() {
  local primary http_base https_base data
  local test_http test_https local_http local_https
  primary="$(ssl_primary_domain)"
  [ -z "$primary" ] && primary="$(echo "$SERVER_NAMES" | awk '{print $1}')"
  [ -z "$primary" ] && primary="localhost"
  data="${DATA_ROOT:-/data/topteens}"

  # Domain URLs never include a port when APP_PORT=80 / HTTPS_PORT=443
  if [ "${APP_PORT}" = "80" ]; then
    http_base="http://${primary}"
  else
    http_base="http://${primary}:${APP_PORT}"
  fi
  if [ "${HTTPS_PORT:-443}" = "443" ]; then
    https_base="https://${primary}"
  else
    https_base="https://${primary}:${HTTPS_PORT}"
  fi

  # IP testing uses TEST_* ports only (not domain ports)
  if [ -n "${PUBLIC_IP:-}" ]; then
    test_http="http://${PUBLIC_IP}:${TEST_HTTP_PORT:-8005}"
    test_https="https://${PUBLIC_IP}:${TEST_HTTPS_PORT:-8443}"
  fi
  local_http="http://127.0.0.1:${TEST_HTTP_PORT:-8005}"
  local_https="https://127.0.0.1:${TEST_HTTPS_PORT:-8443}"

  echo ""
  log "============================================================"
  log "  Website URLs (domain — no port)"
  log "============================================================"
  if ssl_has_certs; then
    log "  Main site     : ${https_base}/"
    log "  Django admin  : ${https_base}/admin/"
    log "  TopTeen admin : ${https_base}/topteenadmin/"
    log "  HTTP (redir)  : ${http_base}/"
  else
    log "  Main site     : ${http_base}/"
    log "  Django admin  : ${http_base}/admin/"
    log "  TopTeen admin : ${http_base}/topteenadmin/"
  fi
  log "============================================================"
  log "  IP testing only (ports)"
  log "============================================================"
  if [ -n "${PUBLIC_IP:-}" ]; then
    log "  IP HTTP       : ${test_http}/"
    if ssl_has_certs; then
      log "  IP HTTPS      : ${test_https}/   (self-signed → browser warning OK)"
    fi
  else
    log "  (set PUBLIC_IP in docker_files/.env to print IP test URLs)"
  fi
  log "  Local HTTP    : ${local_http}/"
  if ssl_has_certs; then
    log "  Local HTTPS   : ${local_https}/"
  fi
  log "============================================================"
  log "  Debug / logs (no host Python needed)"
  log "============================================================"
  log "  Run diagnostics : ./docker_files/deploy.sh debug"
  log "  Docker logs     : ./docker_files/deploy.sh logs"
  log "  Docker nginx    : ./docker_files/deploy.sh logs nginx"
  log "  Docker web      : ./docker_files/deploy.sh logs web"
  log "  nginx access    : ${data}/nginx/logs/access.log"
  log "  nginx error     : ${data}/nginx/logs/error.log"
  log "  Django / app    : ${data}/logs/"
  log "  Tail access     : sudo tail -f ${data}/nginx/logs/access.log"
  log "  Tail error      : sudo tail -f ${data}/nginx/logs/error.log"
  log "============================================================"
  echo ""
}

do_reseed_nginx() {
  log "Rewriting nginx conf from templates (SERVER_NAMES=${SERVER_NAMES})..."
  reseed_nginx_from_templates 1
  if ssl_has_certs; then
    ssl_enable_https_conf
  fi
  log "Reloading nginx..."
  dc exec nginx nginx -s reload 2>/dev/null && log "nginx reloaded." || log "nginx not running yet (ok on first boot)"
}

do_debug() {
  local primary code loc data th tp
  data="${DATA_ROOT:-/data/topteens}"
  primary="$(echo "$SERVER_NAMES" | awk '{print $1}')"
  [ -z "$primary" ] && primary="localhost"
  th="${TEST_HTTP_PORT:-8005}"
  tp="${TEST_HTTPS_PORT:-8443}"

  echo ""
  log "============================================================"
  log "  Debug (host has no Python — all via curl/docker)"
  log "============================================================"
  log "  containers:"
  dc ps -a 2>&1 | sed 's/^/[docker_files]   /' || true

  log "  curl domain HTTP  http://127.0.0.1:${APP_PORT}/ (Host: ${primary})"
  code="$(curl -sS -o /tmp/tt-debug-body.html -m 15 -w '%{http_code}' \
    -H "Host: ${primary}" \
    -D /tmp/tt-debug-headers.txt "http://127.0.0.1:${APP_PORT}/" 2>/dev/null)" || code="000"
  loc="$(grep -i '^Location:' /tmp/tt-debug-headers.txt 2>/dev/null | head -1 | tr -d '\r' || true)"
  log "    status=${code}  ${loc}"
  head -c 200 /tmp/tt-debug-body.html 2>/dev/null | tr '\n' ' ' | sed 's/^/[docker_files]    body: /'; echo

  log "  curl test HTTP    http://127.0.0.1:${th}/"
  code="$(curl -sS -o /dev/null -m 15 -w '%{http_code}' \
    "http://127.0.0.1:${th}/" 2>/dev/null)" || code="000"
  log "    status=${code}"

  if [ -n "${PUBLIC_IP:-}" ]; then
    log "  curl IP test HTTP http://127.0.0.1:${th}/ (Host: ${PUBLIC_IP})"
    code="$(curl -sS -o /dev/null -m 15 -w '%{http_code}' \
      -H "Host: ${PUBLIC_IP}" "http://127.0.0.1:${th}/" 2>/dev/null)" || code="000"
    log "    status=${code}"
  fi

  if ssl_has_certs; then
    log "  curl domain HTTPS https://127.0.0.1:${HTTPS_PORT:-443}/ (Host: ${primary})"
    code="$(curl -skS -o /dev/null -m 15 -w '%{http_code}' \
      -H "Host: ${primary}" "https://127.0.0.1:${HTTPS_PORT:-443}/" 2>/dev/null)" || code="000"
    log "    status=${code}"
    log "  curl test HTTPS   https://127.0.0.1:${tp}/"
    code="$(curl -skS -o /dev/null -m 15 -w '%{http_code}' \
      "https://127.0.0.1:${tp}/" 2>/dev/null)" || code="000"
    log "    status=${code}"
    if [ -n "${PUBLIC_IP:-}" ]; then
      code="$(curl -skS -o /dev/null -m 15 -w '%{http_code}' \
        -H "Host: ${PUBLIC_IP}" "https://127.0.0.1:${tp}/" 2>/dev/null)" || code="000"
      log "    status=${code} (Host: ${PUBLIC_IP})"
    fi
  fi

  log "  Django USE_HTTPS / ALLOWED_HOSTS (from web container):"
  dc exec -T web printenv USE_HTTPS SECURE_SSL_REDIRECT ALLOWED_HOSTS 2>/dev/null \
    | sed 's/^/[docker_files]    /' || log "    (web not running)"

  log "  nginx conf server_name:"
  dc exec -T nginx sh -c 'grep -h server_name /etc/nginx/conf.d/*.conf 2>/dev/null' 2>/dev/null \
    | sed 's/^/[docker_files]    /' || true

  log "  recent nginx error.log:"
  if [ -f "${data}/nginx/logs/error.log" ]; then
    tail -n 30 "${data}/nginx/logs/error.log" 2>/dev/null | sed 's/^/[docker_files]    /' || \
      $SUDO tail -n 30 "${data}/nginx/logs/error.log" 2>/dev/null | sed 's/^/[docker_files]    /' || true
  else
    log "    missing ${data}/nginx/logs/error.log"
  fi

  log "  recent nginx access.log:"
  if [ -f "${data}/nginx/logs/access.log" ]; then
    tail -n 15 "${data}/nginx/logs/access.log" 2>/dev/null | sed 's/^/[docker_files]    /' || \
      $SUDO tail -n 15 "${data}/nginx/logs/access.log" 2>/dev/null | sed 's/^/[docker_files]    /' || true
  else
    log "    missing ${data}/nginx/logs/access.log"
  fi

  log "  recent web logs:"
  dc logs --tail=40 web 2>&1 | sed 's/^/[docker_files]    /' || true

  log "============================================================"
  log "  Log file paths"
  log "============================================================"
  log "  nginx access : ${data}/nginx/logs/access.log"
  log "  nginx error  : ${data}/nginx/logs/error.log"
  log "  app / Django : ${data}/logs/"
  log "  Follow: sudo tail -f ${data}/nginx/logs/access.log ${data}/nginx/logs/error.log"
  print_deploy_urls
}

do_down() {
  log "Stopping and removing containers (images + DATA_ROOT kept)..."
  dc down --remove-orphans
  log "Down complete. Data kept at ${DATA_ROOT}."
  log "  Restart: ./docker_files/deploy.sh up"
}

do_destroy() {
  log "Destroying containers AND project images..."
  log "  (DATA_ROOT=${DATA_ROOT} is NOT deleted)"
  # Remove containers first
  dc down --remove-orphans --rmi local 2>/dev/null || dc down --remove-orphans || true
  # Explicitly remove tagged project images (compose --rmi local may miss some tags)
  for pair in "${APP_IMAGE}:${APP_IMAGE_TAG}" "${NGINX_IMAGE}:${NGINX_IMAGE_TAG}"; do
    if $DOCKER image inspect "$pair" >/dev/null 2>&1; then
      log "Removing image $pair"
      $DOCKER rmi -f "$pair" 2>/dev/null || true
    fi
  done
  # Dangling images from previous builds of this project
  $DOCKER image prune -f >/dev/null 2>&1 || true
  log "Destroy complete. Containers + project images removed."
  log "  Data kept at ${DATA_ROOT}"
  log "  Redeploy from scratch: ./docker_files/deploy.sh up"
}

do_build() {
  banner
  local build_args=()
  [ "${BUILD_PULL:-0}" = "1" ] && build_args+=(--pull)
  [ "${BUILD_NO_CACHE:-0}" = "1" ] && build_args+=(--no-cache)
  log "Building app + nginx images (rebuild)..."
  if [ "${#build_args[@]}" -gt 0 ]; then
    dc build "${build_args[@]}" web nginx
  else
    dc build web nginx
  fi
  log "Build complete."
}

tag_images_previous() {
  for pair in "${APP_IMAGE}:${APP_IMAGE_TAG}" "${NGINX_IMAGE}:${NGINX_IMAGE_TAG}"; do
    if $DOCKER image inspect "$pair" >/dev/null 2>&1; then
      $DOCKER tag "$pair" "${pair}-previous"
      log "Rollback point tagged: ${pair}-previous"
    else
      log "No existing image to tag: $pair (first deploy?)"
    fi
  done
}

docker_login_if_configured() {
  if [ -n "${DOCKERHUB_TOKEN:-}" ] && [ -n "${DOCKERHUB_USERNAME:-}" ]; then
    log "Logging in to Docker Hub as ${DOCKERHUB_USERNAME}..."
    echo "$DOCKERHUB_TOKEN" | $DOCKER login -u "$DOCKERHUB_USERNAME" --password-stdin
  fi
}

do_rollback_internal() {
  local rolled=0
  for pair in "${APP_IMAGE}:${APP_IMAGE_TAG}" "${NGINX_IMAGE}:${NGINX_IMAGE_TAG}"; do
    local prev="${pair}-previous"
    if $DOCKER image inspect "$prev" >/dev/null 2>&1; then
      $DOCKER tag "$prev" "$pair"
      log "Restored $pair from $prev"
      rolled=1
    else
      err "Missing rollback image: $prev"
    fi
  done
  [ "$rolled" = "1" ] || return 1
  ensure_ssl_on_up
  log "Recreating containers with previous images..."
  dc up -d --force-recreate --remove-orphans
  sleep 8
  if health_check "http://127.0.0.1:${APP_PORT}/" 12 5; then
    log "Rollback health check OK."
    return 0
  fi
  err "Rollback completed but health check still failing."
  return 1
}

do_rollback() {
  banner
  if do_rollback_internal; then
    log "Rollback finished."
    dc ps
    print_deploy_urls
  else
    err "Rollback failed."
    exit 1
  fi
}

do_deploy() {
  banner
  tag_images_previous
  log "Stopping existing project containers (if any)..."
  dc down --remove-orphans 2>/dev/null || true
  reseed_nginx_from_templates 1
  BUILD_PULL="${BUILD_PULL:-1}" do_build
  ensure_ssl_on_up
  reseed_nginx_from_templates 1
  log "Starting stack (force recreate)..."
  dc up -d --force-recreate --remove-orphans
  sleep 8
  release_tasks
  if health_check "http://127.0.0.1:${APP_PORT}/"; then
    log "Deploy finished successfully."
    docker_login_if_configured
    if [ -n "${DOCKER_PUSH_REGISTRY:-}" ] || [ "${PUSH_ON_SUCCESS:-1}" = "1" ]; then
      do_push || log "Image push failed (deploy itself succeeded)."
    fi
    banner
    dc ps
    print_deploy_urls
    return 0
  fi
  err "Health check failed. Recent web logs:"
  dc logs --tail=80 web 2>&1 | sed 's/^/[docker_files]   /' >&2 || true
  err "Attempting rollback to previous images..."
  if do_rollback_internal; then
    err "Rolled back to previous working version."
  else
    err "Rollback failed or no :previous image. Stack may be unhealthy."
  fi
  exit 1
}

health_check() {
  local url="$1" retries="${2:-18}" interval="${3:-5}" i=1 code
  log "Health check $url (${retries}x every ${interval}s)..."
  while [ "$i" -le "$retries" ]; do
    # Do NOT use `|| echo 000` after curl -w: failed curl already prints 000 → "000000"
    code="$(curl -sS -o /dev/null -m 10 -w '%{http_code}' "$url" 2>/dev/null)" || code="000"
    case "$code" in
      2??|3??|4??)
        log "Health OK (HTTP $code)."
        return 0
        ;;
    esac
    log "  attempt $i/$retries -> HTTP ${code:-000}, retry in ${interval}s"
    sleep "$interval"; i=$((i + 1))
  done
  return 1
}

release_tasks() {
  log "Running migrations (single web container)..."
  dc exec -T web python manage.py migrate --noinput || log "migrate failed/skipped (continuing)"
  log "Collecting static (single web container)..."
  dc exec -T web python manage.py collectstatic --noinput --clear || log "collectstatic failed (continuing)"
}

do_push() {
  docker_login_if_configured
  for pair in "${APP_IMAGE}:${APP_IMAGE_TAG}" "${NGINX_IMAGE}:${NGINX_IMAGE_TAG}"; do
    if ! $DOCKER image inspect "$pair" >/dev/null 2>&1; then
      log "skip $pair (not built)"
      continue
    fi
    local dst="$pair"
    if [ -n "${DOCKER_PUSH_REGISTRY:-}" ]; then
      dst="${DOCKER_PUSH_REGISTRY%/}/$pair"
      $DOCKER tag "$pair" "$dst"
    fi
    log "Pushing $dst ..."
    $DOCKER push "$dst" || err "push failed for $dst (docker login?)"
  done
}

do_ssl_cmd() {
  local action="${1:-status}"
  shift || true
  case "$action" in
    status)       do_ssl_status ;;
    self-signed|selfsigned) do_ssl_self_signed "$@" ;;
    obtain|certbot|letsencrypt) do_ssl_obtain ;;
    renew)        do_ssl_renew ;;
    sync)         do_ssl_sync; dc exec nginx nginx -s reload 2>/dev/null || true ;;
    *)
      err "Unknown ssl action: $action"
      echo "Usage: ./docker_files/deploy.sh ssl {status|self-signed|obtain|renew|sync}" >&2
      exit 1
      ;;
  esac
}

CMD="${1:-}"
[ -z "$CMD" ] && { usage; exit 1; }
[ "$CMD" = "-h" ] || [ "$CMD" = "--help" ] || [ "$CMD" = "help" ] && { usage; exit 0; }
shift || true

prepare

case "$CMD" in
  up)            do_up ;;
  deploy)        do_deploy ;;
  rollback)      do_rollback ;;
  build)         do_build ;;
  down)          do_down ;;
  destroy|purge|clean) do_destroy ;;
  restart)
    banner
    ensure_ssl_on_up
    dc up -d --force-recreate --remove-orphans web celery celery_beat nginx
    sleep 5
    release_tasks
    if health_check "http://127.0.0.1:${APP_PORT}/"; then
      print_deploy_urls
    fi
    ;;
  reload-nginx)  log "Reloading nginx..."; dc exec nginx nginx -s reload && log "nginx reloaded." ;;
  reseed-nginx)  do_reseed_nginx ;;
  debug)         do_debug ;;
  status|ps)     banner; do_ssl_status; dc ps -a; print_deploy_urls ;;
  logs)          dc logs -f --tail=200 "$@" ;;
  migrate)       dc exec -T web python manage.py migrate --noinput ;;
  collectstatic) dc exec -T web python manage.py collectstatic --noinput --clear ;;
  shell)         dc exec web bash || dc exec web sh ;;
  push)          do_push ;;
  ssl)           do_ssl_cmd "$@" ;;
  *)             err "Unknown command: $CMD"; usage; exit 1 ;;
esac
