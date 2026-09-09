from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.api.deps import get_live_cache, get_position_repository
from app.main import app
from app.modules.mobility.models import VehiclePosition


def sample_position() -> VehiclePosition:
    return VehiclePosition(
        agency_id="br-rj-rio-smtr-sppo",
        vehicle_id="D12345",
        route_id="457",
        latitude=-22.9,
        longitude=-43.2,
        observed_at=datetime(2026, 9, 1, 13, tzinfo=UTC),
        received_at=datetime(2026, 9, 1, 13, 0, 1, tzinfo=UTC),
        source="test",
    )


class FakeCache:
    async def by_route(self, *, agency_id: str, route_id: str):
        assert route_id == "457"
        return [sample_position()]


class FakeRepo:
    async def nearby(self, **kwargs):
        assert kwargs["radius_m"] == 800
        return [sample_position()]


def test_route_vehicles_endpoint() -> None:
    app.dependency_overrides[get_live_cache] = lambda: FakeCache()
    try:
        with TestClient(app) as client:
            response = client.get("/v1/routes/457/vehicles")
        assert response.status_code == 200
        assert response.json()[0]["vehicle_id"] == "D12345"
    finally:
        app.dependency_overrides.clear()


def test_nearby_endpoint() -> None:
    app.dependency_overrides[get_position_repository] = lambda: FakeRepo()
    try:
        with TestClient(app) as client:
            response = client.get(
                "/v1/vehicles/nearby",
                params={"latitude": -22.9, "longitude": -43.2},
            )
        assert response.status_code == 200
        assert response.json()[0]["route_id"] == "457"
    finally:
        app.dependency_overrides.clear()


def test_route_id_rejects_unbounded_or_unsafe_values() -> None:
    app.dependency_overrides[get_live_cache] = lambda: FakeCache()
    try:
        with TestClient(app) as client:
            response = client.get("/v1/routes/../../etc/vehicles")
        assert response.status_code in {404, 422}
    finally:
        app.dependency_overrides.clear()
