from __future__ import annotations

import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen

BASE_URL = "http://edge-proxy:8080"


def request(method: str, path: str) -> tuple[int, dict[str, str], bytes]:
    req = Request(
        f"{BASE_URL}{path}",
        method=method,
        headers={"CF-Connecting-IP": "203.0.113.10", "Accept": "application/json"},
    )
    try:
        with urlopen(req, timeout=5) as response:
            return response.status, dict(response.headers.items()), response.read()
    except HTTPError as exc:
        return exc.code, dict(exc.headers.items()), exc.read()


def main() -> int:
    public_status, public_headers, _ = request(
        "GET", "/v1/routes/__edge_smoke__/vehicles"
    )
    metrics_status, _, _ = request("GET", "/metrics")
    readiness_status, _, _ = request("GET", "/health/ready")
    mutation_status, _, _ = request("POST", "/v1/routes/__edge_smoke__/vehicles")
    options_status, _, _ = request("OPTIONS", "/v1/routes/__edge_smoke__/vehicles")

    normalized_headers = {key.lower(): value for key, value in public_headers.items()}
    checks = {
        "public_v1_reaches_api": public_status == 200,
        "metrics_are_private": metrics_status == 404,
        "readiness_is_private": readiness_status == 404,
        "mutations_are_blocked": mutation_status in {403, 405},
        "preflight_is_bounded": options_status == 204,
        "nosniff_header": normalized_headers.get("x-content-type-options") == "nosniff",
        "hsts_header": normalized_headers.get("strict-transport-security", "").startswith(
            "max-age="
        ),
    }
    result = {"passed": all(checks.values()), "checks": checks}
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
