#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${1:-$ROOT_DIR/.env.production}"
COMPOSE_FILE="$ROOT_DIR/infra/docker-compose.production.yml"
COMPOSE=(docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE")

"$ROOT_DIR/infra/scripts/preflight.sh" "$ENV_FILE"

printf '\nBuilding immutable application/database images...\n'
"${COMPOSE[@]}" build --pull postgres migrate api rio-ingestion

printf '\nStarting data services...\n'
"${COMPOSE[@]}" up -d postgres redis

printf '\nApplying database migrations...\n'
"${COMPOSE[@]}" run --rm migrate

printf '\nStarting API and realtime ingestion...\n'
"${COMPOSE[@]}" up -d api rio-ingestion

printf '\nWaiting for service health...\n'
for _ in $(seq 1 30); do
  api_health="$("${COMPOSE[@]}" ps --format json api 2>/dev/null || true)"
  worker_health="$("${COMPOSE[@]}" ps --format json rio-ingestion 2>/dev/null || true)"
  if grep -q '"Health":"healthy"' <<<"$api_health" && grep -q '"Health":"healthy"' <<<"$worker_health"; then
    break
  fi
  sleep 2
done

"${COMPOSE[@]}" ps
printf '\nDeployment complete. Run stack smoke after the ingestion worker has received its first batch:\n'
printf '  docker compose --env-file %q -f %q --profile operations run --rm stack-smoke\n' "$ENV_FILE" "$COMPOSE_FILE"
