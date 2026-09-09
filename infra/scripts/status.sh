#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${1:-$ROOT_DIR/.env.production}"
COMPOSE_FILE="$ROOT_DIR/infra/docker-compose.production.yml"
COMPOSE=(docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE")

read_env() {
  local key="$1"
  sed -n "s/^${key}=//p" "$ENV_FILE" | tail -n 1
}

api_host_port="$(read_env TRANSIT_API_HOST_PORT)"
api_host_port="${api_host_port:-18000}"

"${COMPOSE[@]}" ps
printf '\nAPI readiness:\n'
curl --fail --silent --show-error "http://127.0.0.1:${api_host_port}/health/ready" || true
printf '\n\nRecent ingestion logs:\n'
"${COMPOSE[@]}" logs --tail=30 rio-ingestion
