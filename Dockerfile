FROM --platform=linux/amd64 nginxinc/nginx-unprivileged:1.27-alpine

# Copy static site content.
COPY . /usr/share/nginx/html

# Copy the nginx server config template. The nginxinc entrypoint renders any
# *.template file in /etc/nginx/templates/ via `envsubst` at container startup,
# substituting only the variables listed in NGINX_ENVSUBST_FILTER below.
COPY nginx/templates/default.conf.template /etc/nginx/templates/default.conf.template

# Remove files that should not be served as website content.
#RUN rm -rf /usr/share/nginx/html/k8s \
#    /usr/share/nginx/html/.dockerignore \
#    /usr/share/nginx/html/Dockerfile \
#    /usr/share/nginx/html/README-k8s.md

# App identity metadata (surfaced by /pod-info, /whoami). Override at runtime.
ENV APP_NAME=nexabank \
    APP_VERSION=dev

# Restrict envsubst to only these variables so nginx's own $vars are preserved.
ENV NGINX_ENVSUBST_FILTER="POD_NAME|POD_NAMESPACE|POD_IP|NODE_NAME|HOSTNAME|APP_NAME|APP_VERSION"

# Provide safe defaults so the endpoints work even outside Kubernetes.
ENV POD_NAME="" \
    POD_NAMESPACE="" \
    POD_IP="" \
    NODE_NAME=""

EXPOSE 8080


HEALTHCHECK --interval=30s --timeout=3s --retries=3 CMD wget -qO- http://127.0.0.1:8080/health >/dev/null || exit 1
