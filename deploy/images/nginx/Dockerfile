# =============================================================================
# TopTeen nginx load balancer (BASE stack)
# Build context = repo root:  docker build -f deploy/images/nginx/Dockerfile .
# Uses the official image's envsubst templating (/etc/nginx/templates/*.template)
# to inject SERVER_NAMES / upstream at start, plus an ssl-optional hook.
# =============================================================================
FROM nginx:1.27-alpine

RUN rm -f /etc/nginx/conf.d/default.conf

COPY deploy/images/nginx/nginx.conf /etc/nginx/nginx.conf
COPY deploy/images/nginx/templates/ /etc/nginx/templates/
COPY deploy/images/nginx/docker-entrypoint.d/25-ssl-optional.sh /docker-entrypoint.d/25-ssl-optional.sh
RUN chmod +x /docker-entrypoint.d/25-ssl-optional.sh
