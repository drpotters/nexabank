FROM --platform=linux/amd64 nginxinc/nginx-unprivileged:1.27-alpine

# Copy static site content.
COPY . /usr/share/nginx/html

# Remove files that should not be served as website content.
#RUN rm -rf /usr/share/nginx/html/k8s \
#    /usr/share/nginx/html/.dockerignore \
#    /usr/share/nginx/html/Dockerfile \
#    /usr/share/nginx/html/README-k8s.md

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --retries=3 CMD wget -qO- http://127.0.0.1:8080/index.html >/dev/null || exit 1
