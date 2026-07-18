# =============================================================================
# TopTeen nginx reverse proxy / load balancer
# Runtime conf is bind-mounted from ${DATA_ROOT}/nginx/conf -> /etc/nginx/conf.d
# Templates in this image are only used by deploy.sh to seed that host folder.
# =============================================================================
FROM nginx:1.27-alpine

RUN rm -f /etc/nginx/conf.d/default.conf \
    && rm -rf /etc/nginx/templates

COPY docker_files/nginx/nginx.conf /etc/nginx/nginx.conf
COPY docker_files/nginx/docker-entrypoint.d/25-ssl-optional.sh /docker-entrypoint.d/25-ssl-optional.sh
RUN chmod +x /docker-entrypoint.d/25-ssl-optional.sh
