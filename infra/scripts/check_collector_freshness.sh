#!/usr/bin/env bash
set -euo pipefail
umask 077

ROOT_DIR="${TRANSIT_ROOT_DIR:-/home/ubuntu/apps/transit-intelligence}"
REPORT_DIR="${TRANSIT_OPERATIONS_REPORT_DIR:-/home/ubuntu/artifacts/transit-intelligence/operations}"
PAUSE_MARKER="$REPORT_DIR/capacity-guard-paused-collector"
ENV_FILE="$ROOT_DIR/.env.production"
COMPOSE_FILE="$ROOT_DIR/infra/docker-compose.production.yml"
COMPOSE=(docker compose -p transit-intelligence --env-file "$ENV_FILE" -f "$COMPOSE_FILE")
report="$REPORT_DIR/collector-watchdog-latest.json"
install -d -m 700 "$REPORT_DIR"
temporary="$(mktemp "$REPORT_DIR/.collector-watchdog.XXXXXX")"
cleanup() {
  rm -f -- "$temporary"
}
trap cleanup EXIT

set +e
python3 "$ROOT_DIR/backend/scripts/check_collector_freshness.py" \
  --maximum-age-seconds "${TRANSIT_COLLECTOR_MAXIMUM_AGE_SECONDS:-300}" >"$temporary"
result=$?
set -e

# Recover only an exited collector. A running-but-stale collector stays failed
# for diagnosis, and a capacity-guard pause is never overridden.
if [[ "$result" -ne 0 && ! -f "$PAUSE_MARKER" ]]; then
  running="$(docker inspect -f '{{.State.Running}}' transit-intelligence-rio-ingestion-1 2>/dev/null || true)"
  root_used_percent="$(df --output=pcent / | tail -n 1 | tr -dc '0-9')"
  if [[ "$running" != "true" && "${root_used_percent:-100}" -lt "${TRANSIT_DISK_CRITICAL_PERCENT:-90}" ]]; then
    "${COMPOSE[@]}" up -d rio-ingestion
    printf 'collector_recovery=started\n' >&2
  fi
fi

mv "$temporary" "$report"
cat "$report"
exit "$result"
