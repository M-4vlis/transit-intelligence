#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${TRANSIT_ROOT_DIR:-/home/ubuntu/apps/transit-intelligence}"
ENV_FILE="$ROOT_DIR/.env.production"
COMPOSE_FILE="$ROOT_DIR/infra/docker-compose.production.yml"

cd "$ROOT_DIR"
docker compose \
  --env-file "$ENV_FILE" \
  -f "$COMPOSE_FILE" \
  --profile maintenance \
  run --rm -T confidence-evidence-restore-check
