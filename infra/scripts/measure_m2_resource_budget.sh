#!/usr/bin/env bash
set -euo pipefail
umask 077

ROOT_DIR="${TRANSIT_ROOT_DIR:-/home/ubuntu/apps/transit-intelligence}"
REPORT_DIR="${TRANSIT_CONFIDENCE_REPORT_DIR:-/home/ubuntu/artifacts/transit-intelligence/confidence-cohorts}"
ENV_FILE="$ROOT_DIR/.env.production"
COMPOSE_FILE="$ROOT_DIR/infra/docker-compose.production.yml"
run_id="$(date -u +%Y%m%dT%H%M%SZ)"
report="$REPORT_DIR/budget-$run_id.json"
temporary="$(mktemp "$REPORT_DIR/.budget-$run_id.XXXXXX")"
stats="$REPORT_DIR/.docker-stats.jsonl"
cleanup() {
  rm -f -- "$temporary" "$stats"
}
trap cleanup EXIT

docker stats --no-stream --format '{{json .}}' >"$stats"
memory_total="$(awk '/MemTotal:/ {print $2 * 1024}' /proc/meminfo | cut -d. -f1)"
memory_available="$(awk '/MemAvailable:/ {print $2 * 1024}' /proc/meminfo | cut -d. -f1)"
root_total="$(df -B1 --output=size / | tail -n 1 | tr -d ' ')"
root_available="$(df -B1 --output=avail / | tail -n 1 | tr -d ' ')"
root_used="$((root_total - root_available))"
project_bytes="$(du -sb "$ROOT_DIR" /home/ubuntu/artifacts/transit-intelligence | awk '{sum += $1} END {print sum}')"

cd "$ROOT_DIR"
set +e
M2_LOGICAL_CPUS="$(nproc)" \
M2_MEMORY_TOTAL_BYTES="$memory_total" \
M2_MEMORY_AVAILABLE_BYTES="$memory_available" \
M2_ROOT_TOTAL_BYTES="$root_total" \
M2_ROOT_USED_BYTES="$root_used" \
M2_PROJECT_BYTES="$project_bytes" \
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" --profile maintenance \
  run --rm -T m2-resource-budget >"$temporary"
result=$?
set -e
mv "$temporary" "$report"
sha256sum "$report" >>"$REPORT_DIR/SHA256SUMS"
ln -sfn "$(basename "$report")" "$REPORT_DIR/budget-latest.json"
"$ROOT_DIR/infra/scripts/archive_eta_confidence_evidence.sh"
cat "$report"
exit "$result"
