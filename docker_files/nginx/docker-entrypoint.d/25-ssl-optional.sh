#!/bin/sh
# Keep HTTPS server block only when SSL certs are present.
# conf.d may be bind-mounted; if read-only, rename fails — disable via empty stub instead.
set -e

SSL_DIR="/etc/nginx/ssl"
HTTPS_CONF="/etc/nginx/conf.d/10-https.conf"
HTTPS_DISABLED="/etc/nginx/conf.d/10-https.conf.disabled"

if [ -f "$SSL_DIR/cert.pem" ] && [ -f "$SSL_DIR/key.pem" ]; then
  echo "[nginx] SSL certs found -> HTTPS enabled (:443)"
  if [ -f "$HTTPS_DISABLED" ] && [ ! -f "$HTTPS_CONF" ]; then
    mv "$HTTPS_DISABLED" "$HTTPS_CONF" 2>/dev/null || cp "$HTTPS_DISABLED" "$HTTPS_CONF" 2>/dev/null || true
  fi
else
  echo "[nginx] No SSL certs in $SSL_DIR -> HTTP only (:80)"
  if [ -f "$HTTPS_CONF" ]; then
    mv "$HTTPS_CONF" "$HTTPS_DISABLED" 2>/dev/null \
      || rm -f "$HTTPS_CONF" 2>/dev/null \
      || echo "[nginx] WARN: could not disable $HTTPS_CONF (mount read-only?); ensure host has no 10-https.conf until certs exist"
  fi
fi
