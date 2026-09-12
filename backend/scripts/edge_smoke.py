from __future__ import annotations

import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen

BASE_URL = "http://edge-proxy:8080"


def request(
    method: str, path: str, *, accept: str = "application/json"
) -> tuple[int, dict[str, str], bytes]:
    req = Request(
        f"{BASE_URL}{path}",
        method=method,
        headers={"CF-Connecting-IP": "203.0.113.10", "Accept": accept},
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
    tile_status, tile_headers, tile_body = request(
        "GET", "/v1/map/tiles/14/6225/9261.png", accept="image/png"
    )
    cached_tile_status, cached_tile_headers, cached_tile_body = request(
        "GET", "/v1/map/tiles/14/6225/9261.png", accept="image/png"
    )

    normalized_headers = {key.lower(): value for key, value in public_headers.items()}
    normalized_tile_headers = {key.lower(): value for key, value in tile_headers.items()}
    normalized_cached_tile_headers = {
        key.lower(): value for key, value in cached_tile_headers.items()
    }
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
        "map_tile_is_png": tile_status == 200
        and normalized_tile_headers.get("content-type", "").startswith("image/png")
        and tile_body.startswith(b"\x89PNG\r\n\x1a\n"),
        "map_tile_is_cached": cached_tile_status == 200
        and cached_tile_body == tile_body
        and normalized_cached_tile_headers.get("x-transit-tile-cache") == "HIT",
    }
    result = {"passed": all(checks.values()), "checks": checks}
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
