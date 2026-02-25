#!/bin/sh
# Generate nginx server blocks from templates using domain/IP from .env (PRODUCTION_SERVER_NAMES, STAGING_SERVER_NAMES)
set -e
CONF_D="${CONF_D:-/etc/nginx/conf.d}"
export PRODUCTION_SERVER_NAMES="${PRODUCTION_SERVER_NAMES:-topteen.in www.topteen.in}"
export STAGING_SERVER_NAMES="${STAGING_SERVER_NAMES:-demo.topteen.in 43.204.127.118 localhost}"

for t in topteen demotopteen; do
  if [ -f "$CONF_D/$t.conf.template" ]; then
    envsubst '${PRODUCTION_SERVER_NAMES} ${STAGING_SERVER_NAMES}' < "$CONF_D/$t.conf.template" > "$CONF_D/$t.conf"
  fi
done
if [ -f "$CONF_D/topteen-ssl.conf.disabled.template" ]; then
  envsubst '${PRODUCTION_SERVER_NAMES} ${STAGING_SERVER_NAMES}' < "$CONF_D/topteen-ssl.conf.disabled.template" > "$CONF_D/topteen-ssl.conf.disabled"
fi
