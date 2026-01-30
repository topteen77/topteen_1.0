# Nginx with domain configs: topteen (production), demotopteen (dev)
# Build context is project root (docker compose build)
FROM nginx:1.25-alpine
RUN rm -f /etc/nginx/conf.d/default.conf
COPY docker/nginx/nginx.conf /etc/nginx/nginx.conf
COPY docker/nginx/conf.d/ /etc/nginx/conf.d/
COPY docker/nginx/nginx-entrypoint.sh /docker-entrypoint.d/40-topteen-ssl.sh
RUN chmod +x /docker-entrypoint.d/40-topteen-ssl.sh
