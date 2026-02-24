#!/bin/sh
# Enable HTTPS for topteen.in only when SSL certs exist (copy topteen-ssl.conf).
set -e
SSL_CERT="${SSL_CERT_PATH:-/etc/nginx/ssl}/cert.pem"
SSL_KEY="${SSL_CERT_PATH:-/etc/nginx/ssl}/key.pem"
CONF_D="/etc/nginx/conf.d"
SSL_CONF="$CONF_D/topteen-ssl.conf"
SSL_CONF_DISABLED="$CONF_D/topteen-ssl.conf.disabled"

if [ -f "$SSL_CERT" ] && [ -f "$SSL_KEY" ]; then
  echo "[nginx] SSL certificates found - enabling HTTPS"
  cp "$SSL_CONF_DISABLED" "$SSL_CONF" 2>/dev/null || true
else
  echo "[nginx] No SSL certificates - HTTP only (demotopteen / dev)"
  rm -f "$SSL_CONF" 2>/dev/null || true
fi
