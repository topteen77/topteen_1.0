# =============================================================================
# TopTeen application image (gunicorn web + celery share this image)
# Build from repo root:
#   docker build -f docker_files/Dockerfile -t topteen-app:latest .
# App code lives at /app/topteen1.0 inside the container.
# =============================================================================
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    APP_HOME=/app/topteen1.0

WORKDIR ${APP_HOME}

# System deps: MySQL client build libs + WeasyPrint (PDF) runtime libs + curl
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc default-libmysqlclient-dev pkg-config \
    libglib2.0-0 libcairo2 libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf-2.0-0 \
    libffi-dev shared-mime-info curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

COPY . .
RUN find ${APP_HOME} -name '*.pyc' -delete \
    && mkdir -p ${APP_HOME}/logs ${APP_HOME}/staticfiles ${APP_HOME}/media

COPY docker_files/entrypoint.sh /entrypoint.sh
COPY docker_files/start.sh /start.sh
RUN chmod +x /entrypoint.sh /start.sh

EXPOSE 8000
# Default = web (gunicorn via start.sh). celery / celery_beat override command.
ENTRYPOINT ["/entrypoint.sh"]
CMD ["/start.sh"]
