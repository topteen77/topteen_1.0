#!/bin/bash
# ECS web task command is still ["/start.sh"] (cloned from the old
# docker_files image). This image keeps Django at /app, not /app/topteen1.0.
# Ignore APP_HOME from the old task definition so gunicorn finds manage.py.
set -e

cd /app
LOG_DIR="${LOG_PATH:-/app/logs}"
mkdir -p "$LOG_DIR"

echo "[start] Starting gunicorn (workers=${GUNICORN_WORKERS:-3} threads=${GUNICORN_THREADS:-4})..."
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
