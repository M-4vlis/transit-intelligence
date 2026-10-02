#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${1:-$ROOT_DIR/.env.production}"
REQUESTED_DAY="${2:-}"
RESTORE_DAY="${REQUESTED_DAY:-$(date -u -d yesterday +%F)}"
COMPOSE_FILE="$ROOT_DIR/infra/docker-compose.production.yml"
COMPOSE=(docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" --profile maintenance)

if [[ ! "$RESTORE_DAY" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
  printf 'invalid archive day: %s\n' "$RESTORE_DAY" >&2
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

if [[ -n "$REQUESTED_DAY" ]]; then
  archive_days=("$REQUESTED_DAY")
else
  # Revisit every closed hot partition, not only the nominal retention window.
  # This heals a previously verified archive when late rows arrived after it was
  # written, including partitions left behind by an older failed cycle.
  mapfile -t archive_days < <(
    {
      for offset in $(seq 8 -1 1); do
        date -u -d "$offset days ago" +%F
      done
      "${COMPOSE[@]}" exec -T postgres sh -ec '
        PGPASSWORD="$POSTGRES_PASSWORD" psql \
          -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "
            SELECT to_char(to_date(right(child.relname, 8), \$\$YYYYMMDD\$\$), \$\$YYYY-MM-DD\$\$)
            FROM pg_inherits
            JOIN pg_class parent ON pg_inherits.inhparent = parent.oid
            JOIN pg_class child ON pg_inherits.inhrelid = child.oid
            JOIN pg_namespace ns ON ns.oid = child.relnamespace
            WHERE ns.nspname = \$\$transit\$\$
              AND parent.relname = \$\$vehicle_positions\$\$
              AND child.relname ~ \$regex\$^vehicle_positions_[0-9]{8}\$\$regex\$
              AND to_date(right(child.relname, 8), \$\$YYYYMMDD\$\$) < CURRENT_DATE
            ORDER BY 1;
          "
      '
    } | sort -u
  )
fi

for archive_day in "${archive_days[@]}"; do
  printf 'archive_day=%s stage=archive\n' "$archive_day"
  "${COMPOSE[@]}" run -T --rm archive-day \
    python -m app.workers.archive_day --day "$archive_day"
done

printf 'archive_day=%s stage=independent_restore\n' "$RESTORE_DAY"
ARCHIVE_DAY="$RESTORE_DAY" "${COMPOSE[@]}" run -T --rm archive-restore-check

printf 'archive_day=%s stage=retention_preflight\n' "$RESTORE_DAY"
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

printf 'archive_day=%s stage=retention_apply\n' "$RESTORE_DAY"
"${COMPOSE[@]}" run -T --rm retention
printf 'archive_day=%s verified_retention_cycle=complete\n' "$RESTORE_DAY"
