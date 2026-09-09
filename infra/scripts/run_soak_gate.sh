#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${1:-$ROOT_DIR/.env.production}"
HOURS="${2:-24}"
COMPOSE_FILE="$ROOT_DIR/infra/docker-compose.production.yml"

docker compose \
  --env-file "$ENV_FILE" \
  -f "$COMPOSE_FILE" \
  --profile operations \
  run --rm soak-gate python scripts/soak_gate.py --hours "$HOURS"
