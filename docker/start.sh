#!/bin/bash
set -e
# Central logs dir (bind-mounted in Docker to host LOG_PATH for debugging)
LOG_DIR="${LOG_PATH:-/app/logs}"
mkdir -p "$LOG_DIR"
# Collect static files into mounted volume for nginx to serve
echo "[start] Running collectstatic..."
python manage.py collectstatic --noinput --clear
echo "[start] collectstatic OK."

# Optimal Gunicorn: gthread for I/O, keepalive for nginx; access/error logs to central folder
exec gunicorn topteens.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers "${GUNICORN_WORKERS:-4}" \
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
