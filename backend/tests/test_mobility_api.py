from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.api.deps import get_gtfs_catalog, get_live_cache, get_position_repository
from app.main import app
from app.modules.mobility.gtfs.models import (
    GtfsRoute,
    GtfsRoutePage,
    GtfsStopPage,
    JourneyMatchMethod,
    NearbyGtfsStop,
    UpcomingGtfsStop,
    VehicleJourneyMatch,
)
from app.modules.mobility.models import VehiclePosition


def sample_position() -> VehiclePosition:
    return VehiclePosition(
        agency_id="br-rj-rio-smtr-sppo",
        vehicle_id="D12345",
        route_id="457",
        shape_id="SH1",
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


class FakeGtfsCatalog:
    async def search_routes(self, **kwargs):
        assert kwargs == {"query": "483", "limit": 10, "offset": 0}
        return GtfsRoutePage(
            items=(
                GtfsRoute(
                    snapshot_id="a" * 64,
                    route_id="483",
                    route_short_name="483",
                    route_long_name="Penha - General Osório",
                    route_type=3,
                ),
            ),
            limit=10,
            offset=0,
            total=1,
        )

    async def nearby_stops(self, **kwargs):
        assert kwargs["radius_m"] == 500
        return GtfsStopPage(
            items=(
                NearbyGtfsStop(
                    snapshot_id="a" * 64,
                    stop_id="123",
                    stop_name="Central",
                    latitude=-22.904,
                    longitude=-43.191,
                    distance_m=42.5,
                ),
            ),
            limit=25,
            offset=0,
            total=1,
        )

    async def match_vehicle_to_upcoming_stops(self, **kwargs):
        assert kwargs["position"].vehicle_id == "D12345"
        assert kwargs["limit"] == 3
        assert kwargs["max_projection_distance_m"] == 250.0
        return VehicleJourneyMatch(
            available=True,
            snapshot_id="a" * 64,
            vehicle_id="D12345",
            route_id="457",
            source_trip_id=None,
            matched_trip_id="T1",
            shape_id="SH1",
            match_method=JourneyMatchMethod.ROUTE_SHAPE_PATTERN,
            observed_at=sample_position().observed_at,
            projected_shape_dist_traveled=50,
            projection_distance_m=4.2,
            upcoming_stops=(
                UpcomingGtfsStop(
                    stop_id="S1",
                    stop_name="Central",
                    latitude=-22.9,
                    longitude=-43.2,
                    stop_sequence=1,
                    shape_dist_traveled=100,
                    shape_distance_ahead=50,
                ),
            ),
        )


def test_route_vehicles_endpoint() -> None:
    app.dependency_overrides[get_live_cache] = lambda: FakeCache()
    try:
        with TestClient(app) as client:
            response = client.get("/v1/routes/457/vehicles")
        assert response.status_code == 200
        assert response.json()[0]["vehicle_id"] == "D12345"
        assert response.json()[0]["shape_id"] == "SH1"
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


def test_route_catalog_search_is_paginated() -> None:
    app.dependency_overrides[get_gtfs_catalog] = lambda: FakeGtfsCatalog()
    try:
        with TestClient(app) as client:
            response = client.get("/v1/routes", params={"query": "483", "limit": 10})
        assert response.status_code == 200
        assert response.json()["total"] == 1
        assert response.json()["items"][0]["route_id"] == "483"
    finally:
        app.dependency_overrides.clear()


def test_nearby_static_stops_include_distance() -> None:
    app.dependency_overrides[get_gtfs_catalog] = lambda: FakeGtfsCatalog()
    try:
        with TestClient(app) as client:
            response = client.get(
                "/v1/stops/nearby",
                params={"latitude": -22.904, "longitude": -43.191, "radius_m": 500},
            )
        assert response.status_code == 200
        assert response.json()["items"][0]["distance_m"] == 42.5
    finally:
        app.dependency_overrides.clear()


def test_vehicle_upcoming_stops_exposes_match_evidence() -> None:
    app.dependency_overrides[get_live_cache] = lambda: FakeCache()
    app.dependency_overrides[get_gtfs_catalog] = lambda: FakeGtfsCatalog()
    try:
        with TestClient(app) as client:
            response = client.get(
                "/v1/routes/457/vehicles/D12345/upcoming-stops",
                params={"limit": 3},
            )
        assert response.status_code == 200
        assert response.json()["available"] is True
        assert response.json()["match_method"] == "route_shape_pattern"
        assert response.json()["projection_distance_m"] == 4.2
        assert response.json()["upcoming_stops"][0]["stop_id"] == "S1"
    finally:
        app.dependency_overrides.clear()


def test_vehicle_upcoming_stops_requires_a_live_vehicle() -> None:
    app.dependency_overrides[get_live_cache] = lambda: FakeCache()
    app.dependency_overrides[get_gtfs_catalog] = lambda: FakeGtfsCatalog()
    try:
        with TestClient(app) as client:
            response = client.get("/v1/routes/457/vehicles/D99999/upcoming-stops")
        assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()
