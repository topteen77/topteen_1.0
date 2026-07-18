#!/bin/sh
# Certbot deploy-hook: sync renewed certs into nginx ssl dir.
# Inside certbot container: LIVE certs at /etc/letsencrypt/live/<domain>/
#                           nginx ssl mount at /nginx-ssl
set -e

SSL_DIR="${NGINX_SSL_DIR:-/nginx-ssl}"
mkdir -p "$SSL_DIR"

# Prefer domain from RENEWED_LINEAGE (set by certbot on renew) or first live dir
if [ -n "${RENEWED_LINEAGE:-}" ] && [ -f "$RENEWED_LINEAGE/fullchain.pem" ]; then
  SRC="$RENEWED_LINEAGE"
else
  SRC="$(ls -d /etc/letsencrypt/live/*/ 2>/dev/null | head -1 | sed 's|/$||')"
fi

if [ -z "$SRC" ] || [ ! -f "$SRC/fullchain.pem" ] || [ ! -f "$SRC/privkey.pem" ]; then
  echo "[ssl-hook] No certbot live certs found to sync."
  exit 0
fi

cp -f "$SRC/fullchain.pem" "$SSL_DIR/cert.pem"
cp -f "$SRC/privkey.pem" "$SSL_DIR/key.pem"
chmod 644 "$SSL_DIR/cert.pem"
chmod 600 "$SSL_DIR/key.pem"
echo "[ssl-hook] Synced $SRC -> $SSL_DIR/cert.pem + key.pem"
# Touch stamp so host/cron can detect renew and reload nginx
date -u +%Y-%m-%dT%H:%M:%SZ > "$SSL_DIR/.last-renewed"
