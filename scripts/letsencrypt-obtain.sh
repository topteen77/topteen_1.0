#!/usr/bin/env bash
# Obtain Let's Encrypt SSL certificate and install for nginx (domain from .env).
# Prereqs: Domain must point to this host; port 80 open; nginx serving /.well-known/acme-challenge/
# Usage: ./scripts/letsencrypt-obtain.sh   (from project root)
# Optional: CERTBOT_EMAIL=you@example.com ./scripts/letsencrypt-obtain.sh

set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

# Load from .env
read_var() { [ -f .env ] && grep -E "^$1=" .env 2>/dev/null | cut -d= -f2- | tr -d ' "' | head -1; }
PRODUCTION_DOMAIN="${PRODUCTION_DOMAIN:-$(read_var PRODUCTION_DOMAIN)}"
PRODUCTION_DOMAIN="${PRODUCTION_DOMAIN:-topteen.in}"
PRODUCTION_SERVER_NAMES="${PRODUCTION_SERVER_NAMES:-$(read_var PRODUCTION_SERVER_NAMES)}"
PRODUCTION_SERVER_NAMES="${PRODUCTION_SERVER_NAMES:-topteen.in www.topteen.in}"
CERTBOT_EMAIL="${CERTBOT_EMAIL:-$(read_var CERTBOT_EMAIL)}"
CERTBOT_WEBROOT="${CERTBOT_WEBROOT:-$(read_var CERTBOT_WEBROOT)}"
CERTBOT_WEBROOT="${CERTBOT_WEBROOT:-$ROOT/certbot-webroot}"
CERTBOT_CONF_PATH="${CERTBOT_CONF_PATH:-$(read_var CERTBOT_CONF_PATH)}"
CERTBOT_CONF_PATH="${CERTBOT_CONF_PATH:-$ROOT/certbot-conf}"
SSL_CERT_PATH="${SSL_CERT_PATH:-$(read_var SSL_CERT_PATH)}"
SSL_CERT_PATH="${SSL_CERT_PATH:-$ROOT/ssl}"

mkdir -p "$CERTBOT_WEBROOT" "$CERTBOT_CONF_PATH" "$SSL_CERT_PATH"
chmod 755 "$CERTBOT_WEBROOT"

# Build -d list from PRODUCTION_SERVER_NAMES (space-separated; skip localhost/IP-only for LE)
DOMAINS=()
FIRST_DOMAIN=""
for d in $PRODUCTION_SERVER_NAMES; do
  [[ "$d" =~ ^[0-9.]+$ ]] && continue
  [[ "$d" == "localhost" ]] && continue
  DOMAINS+=( -d "$d" )
  FIRST_DOMAIN="${FIRST_DOMAIN:-$d}"
done
if [ ${#DOMAINS[@]} -eq 0 ]; then
  echo "ERROR: No valid domain in PRODUCTION_SERVER_NAMES (Let's Encrypt needs a public domain)." >&2
  echo "Set e.g. PRODUCTION_SERVER_NAMES=topteen.in www.topteen.in in .env" >&2
  exit 1
fi

if [ -z "$CERTBOT_EMAIL" ]; then
  echo "CERTBOT_EMAIL is not set. Let's Encrypt requires an email for expiry notices."
  read -p "Enter email for certificate: " CERTBOT_EMAIL
  [ -z "$CERTBOT_EMAIL" ] && { echo "Aborted."; exit 1; }
fi

echo "[letsencrypt] Obtaining certificate for: ${DOMAINS[*]}"
echo "[letsencrypt] Webroot: $CERTBOT_WEBROOT  (nginx must serve /.well-known/acme-challenge/ from here)"
echo "[letsencrypt] Certbot config: $CERTBOT_CONF_PATH"

docker run --rm \
  -v "$CERTBOT_CONF_PATH:/etc/letsencrypt" \
  -v "$CERTBOT_WEBROOT:/var/www/certbot" \
  certbot/certbot certonly --webroot -w /var/www/certbot \
  "${DOMAINS[@]}" \
  --email "$CERTBOT_EMAIL" \
  --agree-tos \
  --non-interactive

# Primary domain = first in list (certbot uses it for live/ path)
LIVE_DIR="$CERTBOT_CONF_PATH/live/$FIRST_DOMAIN"
if [ ! -f "$LIVE_DIR/fullchain.pem" ] || [ ! -f "$LIVE_DIR/privkey.pem" ]; then
  echo "ERROR: Expected $LIVE_DIR/fullchain.pem and privkey.pem" >&2
  exit 1
fi

cp "$LIVE_DIR/fullchain.pem" "$SSL_CERT_PATH/cert.pem"
cp "$LIVE_DIR/privkey.pem" "$SSL_CERT_PATH/key.pem"
chmod 644 "$SSL_CERT_PATH/cert.pem"
chmod 600 "$SSL_CERT_PATH/key.pem"

echo "[letsencrypt] Certificate installed to $SSL_CERT_PATH (cert.pem, key.pem)"
echo "[letsencrypt] Reload nginx to enable HTTPS: ./docker_files/deploy.sh restart"
echo "             Or restart stack: ./docker_files/deploy.sh down && ./docker_files/deploy.sh up"
echo "[letsencrypt] Renew before expiry: run this script again, or add certbot renew to cron."
