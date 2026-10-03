#!/usr/bin/env bash
set -euo pipefail
umask 077

ROOT_DIR="${TRANSIT_ROOT_DIR:-/home/ubuntu/apps/transit-intelligence}"
REPORT_DIR="${TRANSIT_OPERATIONS_REPORT_DIR:-/home/ubuntu/artifacts/transit-intelligence/operations}"
BUDGET_REPORT="${TRANSIT_BUDGET_REPORT:-/home/ubuntu/artifacts/transit-intelligence/confidence-cohorts/budget-latest.json}"
ENV_FILE="$ROOT_DIR/.env.production"
COMPOSE_FILE="$ROOT_DIR/infra/docker-compose.production.yml"
PAUSE_MARKER="$REPORT_DIR/capacity-guard-paused-collector"
REPORT="$REPORT_DIR/capacity-guard-latest.json"
LOCK_FILE="/run/lock/transit-intelligence-capacity-guard.lock"
RETENTION_LOCK="/run/lock/transit-intelligence-verified-retention.lock"
RETENTION_MARKER="$REPORT_DIR/capacity-guard-last-retention"
COMPOSE=(docker compose -p transit-intelligence --env-file "$ENV_FILE" -f "$COMPOSE_FILE")

install -d -m 700 "$REPORT_DIR"
exec 9>"$LOCK_FILE"
flock -n 9 || exit 0

plan_file="$(mktemp "$REPORT_DIR/.capacity-plan.XXXXXX")"
result_file="$(mktemp "$REPORT_DIR/.capacity-result.XXXXXX")"
cleanup() { rm -f -- "$plan_file" "$result_file"; }
trap cleanup EXIT

build_plan() {
  python3 "$ROOT_DIR/backend/scripts/plan_capacity_guard.py" \
    --budget-report "$BUDGET_REPORT" \
    --pause-marker "$PAUSE_MARKER" \
    --warning-percent "${TRANSIT_DISK_WARNING_PERCENT:-80}" \
    --critical-percent "${TRANSIT_DISK_CRITICAL_PERCENT:-90}" \
    --resume-percent "${TRANSIT_DISK_RESUME_PERCENT:-75}" \
    --object-warning-bytes "${TRANSIT_OBJECT_WARNING_BYTES:-15000000000}" \
    --object-hard-guard-bytes "${TRANSIT_OBJECT_HARD_GUARD_BYTES:-18000000000}" \
    >"$plan_file"
}

plan_value() {
  python3 - "$plan_file" "$1" <<'PY'
import json, sys
value = json.load(open(sys.argv[1], encoding="utf-8"))
for part in sys.argv[2].split("."):
    value = value[part]
print(str(value).lower() if isinstance(value, bool) else value)
PY
}

actions=()
retention_exit_status=null
build_plan

if [[ "$(plan_value actions.pause_collector)" == "true" ]]; then
  "${COMPOSE[@]}" stop --timeout 45 rio-ingestion
  printf '%s\n' "$(plan_value reason)" >"$PAUSE_MARKER"
  actions+=("collector_paused")
fi

retention_cooldown_seconds="${TRANSIT_RETENTION_COOLDOWN_SECONDS:-21600}"
retention_cooldown=false
if [[ -f "$RETENTION_MARKER" ]]; then
  marker_age="$(( $(date +%s) - $(stat -c %Y "$RETENTION_MARKER") ))"
  [[ "$marker_age" -lt "$retention_cooldown_seconds" ]] && retention_cooldown=true
fi

if [[ "$(plan_value actions.attempt_verified_retention)" == "true" && "$retention_cooldown" == "false" ]]; then
  set +e
  flock --nonblock --conflict-exit-code 75 "$RETENTION_LOCK" \
    /bin/bash "$ROOT_DIR/infra/scripts/run_verified_retention_cycle.sh" "$ENV_FILE"
  retention_exit_status=$?
  set -e
  if [[ "$retention_exit_status" -eq 0 ]]; then
    actions+=("verified_retention_completed")
    touch "$RETENTION_MARKER"
  elif [[ "$retention_exit_status" -eq 75 ]]; then
    actions+=("verified_retention_already_running")
  else
    actions+=("verified_retention_failed")
  fi
  build_plan
elif [[ "$(plan_value actions.attempt_verified_retention)" == "true" ]]; then
  actions+=("verified_retention_cooldown")
fi

if [[ "$(plan_value actions.resume_collector)" == "true" ]]; then
  # A successful BGSAVE clears Valkey's stop-writes-on-bgsave-error latch after
  # disk pressure has passed. Authentication stays inside the container.
  persistence="$("${COMPOSE[@]}" exec -T redis sh -ec \
    'valkey-cli -a "$CACHE_PASSWORD" --no-auth-warning INFO persistence')"
  if ! grep -q $'rdb_bgsave_in_progress:1\r' <<<"$persistence"; then
    "${COMPOSE[@]}" exec -T redis sh -ec \
      'valkey-cli -a "$CACHE_PASSWORD" --no-auth-warning BGSAVE >/dev/null'
  fi
  persistence_ok=false
  for _ in $(seq 1 30); do
    persistence="$("${COMPOSE[@]}" exec -T redis sh -ec \
      'valkey-cli -a "$CACHE_PASSWORD" --no-auth-warning INFO persistence')"
    if grep -q $'rdb_bgsave_in_progress:0\r' <<<"$persistence" && \
       grep -q $'rdb_last_bgsave_status:ok\r' <<<"$persistence"; then
      persistence_ok=true
      break
    fi
    sleep 2
  done
  [[ "$persistence_ok" == "true" ]]
  "${COMPOSE[@]}" up -d rio-ingestion
  rm -f -- "$PAUSE_MARKER"
  actions+=("valkey_persistence_verified" "collector_resumed")
  build_plan
fi

python3 - "$plan_file" "$result_file" "$retention_exit_status" "${actions[*]:-none}" <<'PY'
import json, sys
plan = json.load(open(sys.argv[1], encoding="utf-8"))
plan["execution"] = {
    "actions": sys.argv[4].split(),
    "retention_exit_status": None if sys.argv[3] == "null" else int(sys.argv[3]),
}
with open(sys.argv[2], "w", encoding="utf-8") as stream:
    json.dump(plan, stream, indent=2, sort_keys=True)
    stream.write("\n")
PY
mv "$result_file" "$REPORT"
cat "$REPORT"

# Warnings remain visible without failing a normal observation. A hard guard or
# a retention error is operationally fatal.
if [[ -f "$PAUSE_MARKER" || ( "$retention_exit_status" != "null" && "$retention_exit_status" -ne 0 && "$retention_exit_status" -ne 75 ) ]]; then
  exit 1
fi
