#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${1:-$ROOT_DIR/.env.production}"
COMPOSE_FILE="$ROOT_DIR/infra/docker-compose.production.yml"

fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
info() { printf 'OK: %s\n' "$*"; }

command -v docker >/dev/null 2>&1 || fail "docker is not installed"
docker compose version >/dev/null 2>&1 || fail "docker compose plugin is not available"
[[ -f "$ENV_FILE" ]] || fail "missing production env file: $ENV_FILE"

mode="$(stat -c '%a' "$ENV_FILE" 2>/dev/null || true)"
case "$mode" in
  600|400) info "production env file permissions are restrictive ($mode)" ;;
  *) fail "set $ENV_FILE permissions to 600 (current: ${mode:-unknown})" ;;
esac

read_env() {
  local key="$1"
  sed -n "s/^${key}=//p" "$ENV_FILE" | tail -n 1
}

postgres_password="$(read_env POSTGRES_PASSWORD)"
cache_password="$(read_env CACHE_PASSWORD)"
[[ ${#postgres_password} -ge 24 ]] || fail "POSTGRES_PASSWORD must be at least 24 characters"
[[ ${#cache_password} -ge 24 ]] || fail "CACHE_PASSWORD must be at least 24 characters"
[[ "$postgres_password" != *"change-me"* ]] || fail "POSTGRES_PASSWORD still contains placeholder text"
[[ "$cache_password" != *"change-me"* ]] || fail "CACHE_PASSWORD still contains placeholder text"
[[ "$postgres_password" =~ ^[A-Za-z0-9._~-]+$ ]] \
  || fail "POSTGRES_PASSWORD contains characters that require DSN percent-encoding; use openssl rand -hex 32"
[[ "$cache_password" =~ ^[A-Za-z0-9._~-]+$ ]] \
  || fail "CACHE_PASSWORD contains characters that require DSN percent-encoding; use openssl rand -hex 32"
info "database/cache credentials pass basic preflight"

arch="$(uname -m)"
case "$arch" in
  aarch64|arm64|x86_64|amd64) info "supported host architecture: $arch" ;;
  *) fail "unsupported host architecture: $arch" ;;
esac

mem_kb="$(awk '/MemTotal/ {print $2}' /proc/meminfo)"
(( mem_kb >= 4 * 1024 * 1024 )) || fail "at least 4 GiB RAM is required"
info "memory preflight passed"

free_kb="$(df -Pk "$ROOT_DIR" | awk 'NR==2 {print $4}')"
(( free_kb >= 8 * 1024 * 1024 )) || fail "at least 8 GiB free disk is required before first deployment"
info "disk preflight passed"

# Compose interpolation validates required variables and catches YAML/schema errors.
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" config --quiet
info "production compose configuration is valid"

# Validate the ARM64-safe PostgreSQL/PostGIS build definition without starting services.
grep -q '^FROM postgres:17.11-trixie$' "$ROOT_DIR/infra/postgres/Dockerfile" \
  || fail "unexpected PostgreSQL base image"
grep -q 'postgresql-17-postgis-3' "$ROOT_DIR/infra/postgres/Dockerfile" \
  || fail "PostGIS package missing from database image"
info "database image is built from the official multi-arch PostgreSQL base"

printf '\nPreflight passed. No service was started.\n'
