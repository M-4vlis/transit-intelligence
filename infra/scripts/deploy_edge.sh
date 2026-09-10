#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${1:-$ROOT_DIR/.env.production}"
COMPOSE_FILE="$ROOT_DIR/infra/docker-compose.production.yml"
COMPOSE=(docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" --profile edge)

"$ROOT_DIR/infra/scripts/edge_preflight.sh" "$ENV_FILE"

printf '\nBuilding the isolated edge proxy...\n'
"${COMPOSE[@]}" build --pull edge-proxy edge-smoke
"${COMPOSE[@]}" pull cloudflared

printf '\nStarting edge proxy and outbound tunnel...\n'
"${COMPOSE[@]}" up -d edge-proxy cloudflared

printf '\nValidating public-path policy through the internal tunnel network...\n'
"${COMPOSE[@]}" run --rm edge-smoke

"${COMPOSE[@]}" ps edge-proxy cloudflared
printf '\nEdge deployment passed. Verify the public hostname from outside the VPS.\n'
