#!/bin/bash
set -e
# Collect static files into mounted volume for nginx to serve
echo "[start] Running collectstatic..."
python manage.py collectstatic --noinput --clear
echo "[start] collectstatic OK."
exec gunicorn topteens.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers "${GUNICORN_WORKERS:-6}" \
  --limit-request-line 65535 \
  --timeout 60
