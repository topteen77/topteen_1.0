#!/bin/bash
# TopTeen app entrypoint.
# - Web replicas run gunicorn (this default). They do NOT run migrate/collectstatic:
#   deploy.sh runs those ONCE (against a single web container) to avoid N replicas
#   racing on the shared static volume / database.
# - celery / celery_beat pass their own command (celery ...), so this default is
#   only used by the web service.
set -e

LOG_DIR="${LOG_PATH:-/app/logs}"
mkdir -p "$LOG_DIR"

# Optional: allow single-container/dev setups to collect static on boot.
if [ "${RUN_COLLECTSTATIC:-0}" = "1" ]; then
  echo "[entrypoint] collectstatic (RUN_COLLECTSTATIC=1)..."
  python manage.py collectstatic --noinput --clear || echo "[entrypoint] collectstatic failed (continuing)"
fi

# Celery/beat pass their own command. Web ECS tasks still pass /start.sh
# from the old image; if that file is missing, fall through to /start.sh.
if [ "$#" -gt 0 ]; then
  if [ -x "$1" ] || command -v "$1" >/dev/null 2>&1; then
    exec "$@"
  fi
  echo "[entrypoint] '$1' not found; starting /start.sh instead"
fi

exec /start.sh
