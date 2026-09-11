#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${1:-$ROOT_DIR/.env.production}"
COMPOSE_FILE="$ROOT_DIR/infra/docker-compose.production.yml"
COMPOSE=(
  docker compose
  --env-file "$ENV_FILE"
  -f "$COMPOSE_FILE"
  --profile edge
  --profile preview
)

[[ -f "$ENV_FILE" ]] || { printf 'ERROR: missing env file: %s\n' "$ENV_FILE" >&2; exit 1; }

"${COMPOSE[@]}" build edge-proxy edge-smoke
"${COMPOSE[@]}" pull cloudflared-quick
"${COMPOSE[@]}" up -d edge-proxy cloudflared-quick
"${COMPOSE[@]}" run --rm edge-smoke

preview_url=""
for _ in $(seq 1 30); do
  preview_url="$(
    "${COMPOSE[@]}" logs --no-color cloudflared-quick 2>&1 \
      | grep -Eo 'https://[a-z0-9-]+\.trycloudflare\.com' \
      | tail -n 1 \
      || true
  )"
  [[ -n "$preview_url" ]] && break
  sleep 2
done

[[ "$preview_url" =~ ^https://[a-z0-9-]+\.trycloudflare\.com$ ]] \
  || { printf 'ERROR: Quick Tunnel URL was not issued\n' >&2; exit 1; }

printf 'PREVIEW_API_URL=%s\n' "$preview_url"
