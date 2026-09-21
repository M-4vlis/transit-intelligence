#!/usr/bin/env bash
set -euo pipefail
umask 077

ROOT_DIR="${TRANSIT_ROOT_DIR:-/home/ubuntu/apps/transit-intelligence}"
REPORT_DIR="${TRANSIT_OPERATIONS_REPORT_DIR:-/home/ubuntu/artifacts/transit-intelligence/operations}"
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
mv "$temporary" "$report"
cat "$report"
exit "$result"
