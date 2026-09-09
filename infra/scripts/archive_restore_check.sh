#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${1:-$ROOT_DIR/.env.production}"
DAY="${2:?usage: archive_restore_check.sh [.env.production] YYYY-MM-DD}"
COMPOSE_FILE="$ROOT_DIR/infra/docker-compose.production.yml"

ARCHIVE_DAY="$DAY" docker compose \
  --env-file "$ENV_FILE" \
  -f "$COMPOSE_FILE" \
  --profile maintenance \
  run --rm archive-restore-check
