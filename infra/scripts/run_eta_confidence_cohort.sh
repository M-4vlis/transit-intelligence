#!/usr/bin/env bash
set -euo pipefail
umask 077

ROOT_DIR="${TRANSIT_ROOT_DIR:-/home/ubuntu/apps/transit-intelligence}"
REPORT_DIR="${TRANSIT_CONFIDENCE_REPORT_DIR:-/home/ubuntu/artifacts/transit-intelligence/confidence-cohorts}"
COMPOSE_FILE="$ROOT_DIR/infra/docker-compose.production.yml"
ENV_FILE="$ROOT_DIR/.env.production"

install -d -m 700 "$REPORT_DIR"
exec 9>"$REPORT_DIR/.cohort.lock"
if ! flock -n 9; then
  printf 'TRANSIT_ETA_CONFIDENCE_COHORT_SKIPPED reason=already_running\n'
  exit 0
fi

run_id="$(date -u +%Y%m%dT%H%M%SZ)"
report="$REPORT_DIR/cohort-$run_id.json"
summary="$REPORT_DIR/summary-$run_id.json"
calibration="$REPORT_DIR/calibration-$run_id.json"
report_tmp="$(mktemp "$REPORT_DIR/.cohort-$run_id.XXXXXX")"
summary_tmp="$(mktemp "$REPORT_DIR/.summary-$run_id.XXXXXX")"
calibration_tmp="$(mktemp "$REPORT_DIR/.calibration-$run_id.XXXXXX")"
cleanup() {
  rm -f -- "$report_tmp" "$summary_tmp" "$calibration_tmp"
}
trap cleanup EXIT

cd "$ROOT_DIR"
docker compose \
  --env-file "$ENV_FILE" \
  -f "$COMPOSE_FILE" \
  --profile maintenance \
  run --rm -T eta-replay \
  --anchor-age-minutes 45 \
  --anchor-window-seconds 180 \
  --outcome-horizon-minutes 20 \
  --stop-radius-m 75 \
  --max-samples 200 \
  --min-outcomes 20 >"$report_tmp"

python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); assert d["candidate_confidence"]["calibration_status"] == "uncalibrated"' "$report_tmp"
mv "$report_tmp" "$report"
sha256sum "$report" >>"$REPORT_DIR/SHA256SUMS"

python3 backend/scripts/summarize_eta_confidence_cohorts.py \
  --reports-dir "$REPORT_DIR" >"$summary_tmp"
mv "$summary_tmp" "$summary"
sha256sum "$summary" >>"$REPORT_DIR/SHA256SUMS"
ln -sfn "$(basename "$summary")" "$REPORT_DIR/summary-latest.json"

python3 backend/scripts/calibrate_eta_confidence.py \
  --reports-dir "$REPORT_DIR" >"$calibration_tmp"
mv "$calibration_tmp" "$calibration"
sha256sum "$calibration" >>"$REPORT_DIR/SHA256SUMS"
ln -sfn "$(basename "$calibration")" "$REPORT_DIR/calibration-latest.json"

docker compose \
  --env-file "$ENV_FILE" \
  -f "$COMPOSE_FILE" \
  --profile maintenance \
  run --rm -T confidence-evidence-archive

printf 'TRANSIT_ETA_CONFIDENCE_COHORT_OK report=%s summary=%s calibration=%s\n' \
  "$report" "$summary" "$calibration"
