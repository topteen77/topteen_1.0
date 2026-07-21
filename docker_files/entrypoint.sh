#!/bin/bash
# TopTeen app entrypoint.
# - Web uses start.sh (gunicorn) by default.
# - celery / celery_beat pass their own command.
# - migrate/collectstatic are run ONCE by deploy.sh (not per replica).
set -e

APP_HOME="${APP_HOME:-/app/topteen1.0}"
LOG_DIR="${LOG_PATH:-${APP_HOME}/logs}"
mkdir -p "$LOG_DIR" "${APP_HOME}/staticfiles" "${APP_HOME}/media"
cd "$APP_HOME"

if [ "${RUN_COLLECTSTATIC:-0}" = "1" ]; then
  echo "[entrypoint] collectstatic (RUN_COLLECTSTATIC=1)..."
  if [ "${COLLECTSTATIC_CLEAR:-0}" = "1" ]; then
    python manage.py collectstatic --noinput --clear || echo "[entrypoint] collectstatic failed (continuing)"
  else
    python manage.py collectstatic --noinput || echo "[entrypoint] collectstatic failed (continuing)"
  fi
fi

if [ "${RUN_MIGRATE:-0}" = "1" ]; then
  echo "[entrypoint] migrate (RUN_MIGRATE=1)..."
  python manage.py migrate --noinput || echo "[entrypoint] migrate failed (continuing)"
fi

exec "$@"
