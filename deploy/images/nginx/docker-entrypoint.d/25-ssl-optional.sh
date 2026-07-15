#!/bin/sh
# Runs after the official 20-envsubst-on-templates.sh has rendered the configs.
# Keeps the HTTPS server block only when SSL certs are actually present, so the
# load balancer starts cleanly on HTTP-only hosts (before certbot has issued a cert).
set -e

SSL_DIR="/etc/nginx/ssl"
HTTPS_CONF="/etc/nginx/conf.d/10-https.conf"

if [ -f "$SSL_DIR/cert.pem" ] && [ -f "$SSL_DIR/key.pem" ]; then
  echo "[nginx-lb] SSL certs found -> HTTPS enabled (:443)"
else
  echo "[nginx-lb] No SSL certs in $SSL_DIR -> HTTP only (:80). Removing HTTPS server block."
  rm -f "$HTTPS_CONF"
fi
