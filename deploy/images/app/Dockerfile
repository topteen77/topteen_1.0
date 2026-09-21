# =============================================================================
# TopTeen application image (gunicorn web + celery share this image)
# Build context = repo root:  docker build -f deploy/images/app/Dockerfile .
# Tagged per environment by deploy.sh -> developertopteen/demotopteen:<env>
# =============================================================================
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps: MySQL client build libs + WeasyPrint (PDF) runtime libs + curl (healthcheck/debug)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc default-libmysqlclient-dev pkg-config \
    libglib2.0-0 libcairo2 libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf-2.0-0 \
    libffi-dev shared-mime-info curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# Context is filtered by .dockerignore (no react-game dump, html scrapes, zips, tests).
COPY . .
RUN find /app \( -name '*.pyc' -o -name '*.pyo' -o -name '*.zip' -o -name '*.tar' \
      -o -name '*.tgz' -o -name '*.bak' -o -name '.DS_Store' \) -type f -delete \
 && find /app \( -type d -name '__pycache__' -o -type d -name 'node_modules' \) \
    | xargs -r rm -rf

COPY deploy/images/app/entrypoint.sh /entrypoint.sh
COPY deploy/images/app/start.sh /start.sh
RUN chmod +x /entrypoint.sh /start.sh

EXPOSE 8000
# Live ECS web tasks still set command ["/start.sh"] (old docker_files image).
# Keep that file at /start.sh. celery / celery_beat override command.
ENTRYPOINT ["/entrypoint.sh"]
CMD ["/start.sh"]
