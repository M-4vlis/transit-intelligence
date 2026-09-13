#!/usr/bin/env bash
set -euo pipefail
umask 077

ROOT_DIR="${TRANSIT_ROOT_DIR:-/home/ubuntu/apps/transit-intelligence}"
REPORT_DIR="${TRANSIT_CONFIDENCE_REPORT_DIR:-/home/ubuntu/artifacts/transit-intelligence/confidence-cohorts}"
run_id="${1:-$(date -u +%Y%m%dT%H%M%SZ)}"
report="$REPORT_DIR/readiness-$run_id.json"
temporary="$(mktemp "$REPORT_DIR/.readiness-$run_id.XXXXXX")"
cleanup() {
  rm -f -- "$temporary"
}
trap cleanup EXIT

python3 "$ROOT_DIR/backend/scripts/build_m2_readiness_report.py" \
  --reports-dir "$REPORT_DIR" >"$temporary"
python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); assert d["promotion_authorized"] is False' "$temporary"
mv "$temporary" "$report"
sha256sum "$report" >>"$REPORT_DIR/SHA256SUMS"
ln -sfn "$(basename "$report")" "$REPORT_DIR/readiness-latest.json"
printf 'TRANSIT_M2_READINESS_OK report=%s\n' "$report"
