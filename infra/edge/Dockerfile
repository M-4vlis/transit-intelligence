FROM nginx:1.30.4-alpine-slim

COPY nginx.conf /etc/nginx/nginx.conf

USER 101:101

EXPOSE 8080 8081

STOPSIGNAL SIGQUIT
