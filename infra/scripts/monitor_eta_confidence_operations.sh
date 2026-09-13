#!/usr/bin/env bash
set -euo pipefail
umask 077

ROOT_DIR="${TRANSIT_ROOT_DIR:-/home/ubuntu/apps/transit-intelligence}"
REPORT_DIR="${TRANSIT_CONFIDENCE_REPORT_DIR:-/home/ubuntu/artifacts/transit-intelligence/confidence-cohorts}"
output="$REPORT_DIR/operations-latest.json"
temporary="$(mktemp "$REPORT_DIR/.operations.XXXXXX")"
cleanup() {
  rm -f -- "$temporary"
}
trap cleanup EXIT

unit_value() {
  systemctl show "$1" --property="$2" --value 2>/dev/null || printf 'unknown'
}

cohort_result="$(unit_value transit-intelligence-eta-confidence-cohort.service Result)"
cohort_status="$(unit_value transit-intelligence-eta-confidence-cohort.service ExecMainStatus)"
restore_result="$(unit_value transit-intelligence-confidence-evidence-restore.service Result)"
restore_status="$(unit_value transit-intelligence-confidence-evidence-restore.service ExecMainStatus)"

set +e
python3 "$ROOT_DIR/backend/scripts/check_eta_confidence_operations.py" \
  --reports-dir "$REPORT_DIR" \
  --cohort-service-result "$cohort_result" \
  --cohort-service-exit-status "${cohort_status:-0}" \
  --restore-service-result "$restore_result" \
  --restore-service-exit-status "${restore_status:-0}" >"$temporary"
result=$?
set -e
mv "$temporary" "$output"
cat "$output"
exit "$result"
