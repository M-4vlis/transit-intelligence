# Multi-architecture PostGIS image built only from the official PostgreSQL image
# and Debian's signed package repositories. Supports linux/amd64 and linux/arm64.
FROM postgres:17.11-trixie

RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        postgresql-17-postgis-3 \
        postgresql-17-postgis-3-scripts; \
    rm -rf /var/lib/apt/lists/*
