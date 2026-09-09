#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="${1:-$ROOT_DIR/.env.production}"
STATE_DIR="${2:-$ROOT_DIR/ops/soak}"
HOURS="${3:-24}"
POLL_SECONDS="${SOAK_WATCH_POLL_SECONDS:-30}"
COMPOSE_FILE="$ROOT_DIR/infra/docker-compose.production.yml"

[[ "$HOURS" =~ ^[1-9][0-9]*$ ]] || { echo "hours must be a positive integer" >&2; exit 1; }
[[ "$POLL_SECONDS" =~ ^[1-9][0-9]*$ ]] || { echo "poll seconds must be positive" >&2; exit 1; }
[[ -f "$ENV_FILE" ]] || { echo "missing env file: $ENV_FILE" >&2; exit 1; }

mkdir -p "$STATE_DIR"
chmod 700 "$STATE_DIR"
exec 9>"$STATE_DIR/watch.lock"
flock -n 9 || { echo "soak watcher is already running"; exit 0; }

REPORT_FILE="$STATE_DIR/soak-${HOURS}h.json"
STATUS_FILE="$STATE_DIR/status"
ARMED_FILE="$STATE_DIR/armed_at"
STARTED_FILE="$STATE_DIR/started_at"

if [[ -s "$REPORT_FILE" ]]; then
  echo "soak watcher already completed: $REPORT_FILE"
  exit 0
fi

if [[ -s "$ARMED_FILE" ]]; then
  armed_at="$(<"$ARMED_FILE")"
else
  armed_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  printf '%s\n' "$armed_at" >"$ARMED_FILE.tmp"
  mv "$ARMED_FILE.tmp" "$ARMED_FILE"
fi

if [[ -s "$STARTED_FILE" ]]; then
  started_at="$(<"$STARTED_FILE")"
else
  printf 'armed source=rio-smtr-gps armed_at=%s\n' "$armed_at" >"$STATUS_FILE"
  while true; do
    started_at="$(
      docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T postgres \
        psql -U transit_app -d transit -Atc "
          SELECT to_char(finished_at AT TIME ZONE 'UTC', 'YYYY-MM-DD\"T\"HH24:MI:SS.US\"Z\"')
          FROM transit.ingestion_runs
          WHERE source = 'rio-smtr-gps'
            AND status = 'success'
            AND persisted_records > 0
            AND cached_records > 0
            AND contract_fingerprint IS NOT NULL
            AND finished_at >= '$armed_at'::timestamptz
          ORDER BY finished_at
          LIMIT 1;
        " 2>/dev/null || true
    )"
    [[ -n "$started_at" ]] && break
    sleep "$POLL_SECONDS"
  done
  printf '%s\n' "$started_at" >"$STARTED_FILE.tmp"
  mv "$STARTED_FILE.tmp" "$STARTED_FILE"
fi

printf 'running source=rio-smtr-gps started_at=%s hours=%s\n' "$started_at" "$HOURS" >"$STATUS_FILE"
start_epoch="$(date -u -d "$started_at" +%s)"
finish_epoch="$((start_epoch + HOURS * 3600))"
while (( $(date -u +%s) < finish_epoch )); do
  remaining="$((finish_epoch - $(date -u +%s)))"
  (( remaining > 60 )) && remaining=60
  sleep "$remaining"
done

set +e
"$ROOT_DIR/infra/scripts/run_soak_gate.sh" "$ENV_FILE" "$HOURS" \
  >"$REPORT_FILE.tmp" 2>"$STATE_DIR/soak-${HOURS}h.stderr.tmp"
gate_status=$?
set -e
mv "$REPORT_FILE.tmp" "$REPORT_FILE"
mv "$STATE_DIR/soak-${HOURS}h.stderr.tmp" "$STATE_DIR/soak-${HOURS}h.stderr"

if (( gate_status == 0 )); then
  printf 'passed source=rio-smtr-gps started_at=%s evaluated_at=%s\n' \
    "$started_at" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >"$STATUS_FILE"
else
  printf 'failed source=rio-smtr-gps started_at=%s evaluated_at=%s gate_exit=%s\n' \
    "$started_at" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$gate_status" >"$STATUS_FILE"
fi

# A failed quality gate is a completed measurement, not a watcher crash.
exit 0
