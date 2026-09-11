from __future__ import annotations

from typing import Any

from app.modules.mobility.gtfs.models import (
    GtfsRoute,
    GtfsRoutePage,
    GtfsStopPage,
    NearbyGtfsStop,
)


class PostgresGtfsCatalog:
    def __init__(self, pool: Any) -> None:
        self.pool = pool

    async def search_routes(
        self,
        *,
        query: str | None,
        limit: int,
        offset: int,
    ) -> GtfsRoutePage:
        normalized = query.strip() if query else None
        pattern = f"%{normalized}%" if normalized else None
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                WITH active AS (
                    SELECT snapshot_id
                    FROM transit.gtfs_snapshots
                    WHERE status = 'active'
                )
                SELECT
                    route.snapshot_id, route.route_id, route.agency_id,
                    route.route_short_name, route.route_long_name, route.route_desc,
                    route.route_type, route.route_color, route.route_text_color,
                    count(*) OVER() AS total
                FROM transit.gtfs_routes route
                JOIN active USING (snapshot_id)
                WHERE $1::text IS NULL
                   OR route.route_id ILIKE $1
                   OR route.route_short_name ILIKE $1
                   OR route.route_long_name ILIKE $1
                ORDER BY
                    nullif(route.route_short_name, '') ASC NULLS LAST,
                    nullif(route.route_long_name, '') ASC NULLS LAST,
                    route.route_id ASC
                LIMIT $2 OFFSET $3
                """,
                pattern,
                limit,
                offset,
            )
        total = int(rows[0]["total"]) if rows else 0
        items = tuple(
            GtfsRoute.model_validate(
                {key: value for key, value in dict(row).items() if key != "total"}
            )
            for row in rows
        )
        return GtfsRoutePage(items=items, limit=limit, offset=offset, total=total)

    async def nearby_stops(
        self,
        *,
        latitude: float,
        longitude: float,
        radius_m: int,
        limit: int,
        offset: int,
    ) -> GtfsStopPage:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                WITH active AS (
                    SELECT snapshot_id
                    FROM transit.gtfs_snapshots
                    WHERE status = 'active'
                ), nearby AS (
                    SELECT
                        stop.snapshot_id, stop.stop_id, stop.stop_code, stop.stop_name,
                        stop.stop_desc, stop.stop_lat AS latitude, stop.stop_lon AS longitude,
                        stop.location_type, stop.parent_station, stop.wheelchair_boarding,
                        ST_Distance(
                            stop.location,
                            ST_SetSRID(ST_MakePoint($2,$1),4326)::geography
                        ) AS distance_m
                    FROM transit.gtfs_stops stop
                    JOIN active USING (snapshot_id)
                    WHERE ST_DWithin(
                        stop.location,
                        ST_SetSRID(ST_MakePoint($2,$1),4326)::geography,
                        $3
                    )
                )
                SELECT *, count(*) OVER() AS total
                FROM nearby
                ORDER BY distance_m ASC, stop_id ASC
                LIMIT $4 OFFSET $5
                """,
                latitude,
                longitude,
                radius_m,
                limit,
                offset,
            )
        total = int(rows[0]["total"]) if rows else 0
        items = tuple(
            NearbyGtfsStop.model_validate(
                {key: value for key, value in dict(row).items() if key != "total"}
            )
            for row in rows
        )
        return GtfsStopPage(items=items, limit=limit, offset=offset, total=total)
