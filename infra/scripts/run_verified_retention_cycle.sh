#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${1:-$ROOT_DIR/.env.production}"
ARCHIVE_DAY="${2:-$(date -u -d yesterday +%F)}"
COMPOSE_FILE="$ROOT_DIR/infra/docker-compose.production.yml"
COMPOSE=(docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" --profile maintenance)

if [[ ! "$ARCHIVE_DAY" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
  printf 'invalid archive day: %s\n' "$ARCHIVE_DAY" >&2
  exit 2
fi

if ! grep -qx 'HOT_RETENTION_DAYS=7' "$ENV_FILE"; then
  printf 'retention cycle requires HOT_RETENTION_DAYS=7\n' >&2
  exit 3
fi
if ! grep -qx 'DESTRUCTIVE_RETENTION_ENABLED=true' "$ENV_FILE"; then
  printf 'retention cycle requires explicit destructive retention authorization\n' >&2
  exit 4
fi

preflight_output="$(mktemp)"
trap 'rm -f "$preflight_output"' EXIT

printf 'archive_day=%s stage=archive\n' "$ARCHIVE_DAY"
"${COMPOSE[@]}" run -T --rm archive-day \
  python -m app.workers.archive_day --day "$ARCHIVE_DAY"

printf 'archive_day=%s stage=independent_restore\n' "$ARCHIVE_DAY"
ARCHIVE_DAY="$ARCHIVE_DAY" "${COMPOSE[@]}" run -T --rm archive-restore-check

printf 'archive_day=%s stage=retention_preflight\n' "$ARCHIVE_DAY"
"${COMPOSE[@]}" run -T --rm retention-preflight | tee "$preflight_output"

python3 - "$preflight_output" <<'PY'
import json
import sys

report = json.loads(open(sys.argv[1], encoding="utf-8").read())
if report.get("dropped_days"):
    raise SystemExit("preflight unexpectedly reported dropped days")
if report.get("protected_days"):
    raise SystemExit(
        "retention blocked because candidate days lack complete remote verification: "
        + ",".join(report["protected_days"])
    )
print(
    "retention_preflight_passed would_drop="
    + ",".join(report.get("would_drop_days", []))
)
PY

printf 'archive_day=%s stage=retention_apply\n' "$ARCHIVE_DAY"
"${COMPOSE[@]}" run -T --rm retention
printf 'archive_day=%s verified_retention_cycle=complete\n' "$ARCHIVE_DAY"
