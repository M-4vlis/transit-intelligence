from __future__ import annotations

import argparse
import json
import time
import urllib.request
from datetime import UTC, datetime

_LAST_SUCCESS_METRIC = "transit_ingestion_last_success_unixtime"


def parse_last_success(metrics: str, *, source: str) -> float | None:
    expected_label = f'source="{source}"'
    for line in metrics.splitlines():
        if line.startswith(f"{_LAST_SUCCESS_METRIC}{{") and expected_label in line:
            try:
                return float(line.rsplit(maxsplit=1)[1])
            except (IndexError, ValueError):
                return None
    return None


def build_report(
    *, now_unix: float, last_success_unix: float | None, maximum_age_seconds: int
) -> dict[str, object]:
    age = max(0.0, now_unix - last_success_unix) if last_success_unix else None
    fresh = age is not None and age <= maximum_age_seconds
    return {
        "schema_version": 1,
        "generated_at": datetime.fromtimestamp(now_unix, UTC).isoformat(),
        "status": "passed" if fresh else "failed",
        "maximum_age_seconds": maximum_age_seconds,
        "last_success_at": (
            datetime.fromtimestamp(last_success_unix, UTC).isoformat()
            if last_success_unix
            else None
        ),
        "last_success_age_seconds": round(age, 3) if age is not None else None,
        "checks": {"recent_ingestion_success": fresh},
    }


def _read(url: str, *, timeout_seconds: float) -> str:
    with urllib.request.urlopen(url, timeout=timeout_seconds) as response:
        return response.read().decode("utf-8")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check realtime collector freshness")
    parser.add_argument("--metrics-url", default="http://127.0.0.1:9101/metrics")
    parser.add_argument("--ready-url", default="http://127.0.0.1:18000/health/ready")
    parser.add_argument("--source", default="rio-smtr-gps")
    parser.add_argument("--maximum-age-seconds", type=int, default=300)
    parser.add_argument("--timeout-seconds", type=float, default=5)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if args.maximum_age_seconds < 60:
        raise SystemExit("maximum age must be at least 60 seconds")
    try:
        ready = json.loads(_read(args.ready_url, timeout_seconds=args.timeout_seconds))
        if ready.get("status") != "ready":
            raise RuntimeError("API readiness did not pass")
        metrics = _read(args.metrics_url, timeout_seconds=args.timeout_seconds)
        report = build_report(
            now_unix=time.time(),
            last_success_unix=parse_last_success(metrics, source=args.source),
            maximum_age_seconds=args.maximum_age_seconds,
        )
    except Exception as exc:  # noqa: BLE001 - operational boundary must fail closed
        report = {
            "schema_version": 1,
            "generated_at": datetime.now(UTC).isoformat(),
            "status": "failed",
            "checks": {"endpoints_reachable": False},
            "error_type": type(exc).__name__,
        }
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    raise SystemExit(0 if report["status"] == "passed" else 1)


if __name__ == "__main__":
    main()
