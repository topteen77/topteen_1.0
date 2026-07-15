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

# If an explicit command was given (celery worker/beat), run it as-is.
if [ "$#" -gt 0 ]; then
  exec "$@"
fi

echo "[entrypoint] Starting gunicorn (workers=${GUNICORN_WORKERS:-3} threads=${GUNICORN_THREADS:-4})..."
exec gunicorn topteens.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers "${GUNICORN_WORKERS:-3}" \
  --worker-class gthread \
  --threads "${GUNICORN_THREADS:-4}" \
  --max-requests 2000 \
  --max-requests-jitter 100 \
  --timeout 60 \
  --graceful-timeout 30 \
  --keep-alive 5 \
  --limit-request-line 65535 \
  --access-logfile "$LOG_DIR/gunicorn_access.log" \
  --error-logfile "$LOG_DIR/gunicorn_error.log" \
  --capture-output \
  --enable-stdio-inheritance
