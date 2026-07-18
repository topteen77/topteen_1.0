#!/bin/bash
# Gunicorn start script for TopTeen web containers.
set -e

APP_HOME="${APP_HOME:-/app/topteen1.0}"
LOG_DIR="${LOG_PATH:-${APP_HOME}/logs}"
mkdir -p "$LOG_DIR"
cd "$APP_HOME"

echo "[start] Starting gunicorn (workers=${GUNICORN_WORKERS:-8} threads=${GUNICORN_THREADS:-4})..."
exec gunicorn topteens.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers "${GUNICORN_WORKERS:-8}" \
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
