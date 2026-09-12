from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.modules.mobility.eta import MAX_POSITION_AGE_SECONDS, estimate_stop_arrivals
from app.modules.mobility.gtfs.models import (
    EtaEvidence,
    EtaMethod,
    EtaUnavailableReason,
    GtfsRoute,
    GtfsRoutePage,
    GtfsStopPage,
    JourneyMatchMethod,
    JourneyUnavailableReason,
    NearbyGtfsStop,
    UpcomingGtfsStop,
    VehicleJourneyMatch,
)
from app.modules.mobility.models import VehiclePosition

_MIN_ETA_SPEED_MPS = 0.8
_MAX_ETA_SPEED_MPS = 22.22
_VEHICLE_SPEED_WINDOW_SECONDS = 300
_VEHICLE_MIN_SAMPLES = 3
_ROUTE_SHAPE_SPEED_WINDOW_SECONDS = 600
_ROUTE_SHAPE_MIN_SAMPLES = 20
_HISTORICAL_PROFILE_WINDOW_SECONDS = 7 * 24 * 60 * 60
_HISTORICAL_PROFILE_MIN_SAMPLES = 50
_HISTORICAL_PROFILE_MIN_WINDOWS = 2
_HISTORICAL_PROFILE_GRID_DEGREES = 0.0025


class PostgresGtfsCatalog:
    def __init__(self, pool: Any, *, historical_profiles_enabled: bool = True) -> None:
        self.pool = pool
        self.historical_profiles_enabled = historical_profiles_enabled

    @staticmethod
    async def _historical_speed_evidence(
        conn: Any, position: VehiclePosition
    ) -> EtaEvidence | None:
        row = await conn.fetchrow(
            """
            WITH matching_profiles AS (
                SELECT
                    sample_count,
                    speed_p25_mps,
                    speed_median_mps,
                    speed_p75_mps
                FROM transit.eta_segment_speed_profiles
                WHERE route_id = $1
                  AND latitude_cell BETWEEN
                      floor(($2::double precision + 90.0) / $5)::integer - 1
                      AND floor(($2::double precision + 90.0) / $5)::integer + 1
                  AND longitude_cell BETWEEN
                      floor(($3::double precision + 180.0) / $5)::integer - 1
                      AND floor(($3::double precision + 180.0) / $5)::integer + 1
                  AND window_end <= $4::timestamptz
                  AND window_end >= $4::timestamptz
                      - ($6::double precision * interval '1 second')
                  AND least(
                      abs(
                          local_time_band - floor(
                              extract(epoch FROM (
                                  $4::timestamptz
                                  AT TIME ZONE 'America/Sao_Paulo'
                              )::time) / 900
                          )::integer
                      ),
                      96 - abs(
                          local_time_band - floor(
                              extract(epoch FROM (
                                  $4::timestamptz
                                  AT TIME ZONE 'America/Sao_Paulo'
                              )::time) / 900
                          )::integer
                      )
                  ) <= 1
            )
            SELECT
                count(*)::integer AS profile_count,
                coalesce(sum(sample_count),0)::bigint AS sample_count,
                sum(speed_p25_mps * sample_count) / nullif(sum(sample_count),0)
                    AS speed_p25_mps,
                sum(speed_median_mps * sample_count) / nullif(sum(sample_count),0)
                    AS speed_median_mps,
                sum(speed_p75_mps * sample_count) / nullif(sum(sample_count),0)
                    AS speed_p75_mps
            FROM matching_profiles
            """,
            position.route_id,
            position.latitude,
            position.longitude,
            position.observed_at,
            _HISTORICAL_PROFILE_GRID_DEGREES,
            float(_HISTORICAL_PROFILE_WINDOW_SECONDS),
        )
        profile_count = int(row["profile_count"] or 0)
        sample_count = int(row["sample_count"] or 0)
        if (
            profile_count < _HISTORICAL_PROFILE_MIN_WINDOWS
            or sample_count < _HISTORICAL_PROFILE_MIN_SAMPLES
        ):
            return None
        return EtaEvidence(
            method=EtaMethod.HISTORICAL_SEGMENT_TIME_BAND,
            sample_count=sample_count,
            window_seconds=_HISTORICAL_PROFILE_WINDOW_SECONDS,
            speed_p25_mps=float(row["speed_p25_mps"]),
            speed_median_mps=float(row["speed_median_mps"]),
            speed_p75_mps=float(row["speed_p75_mps"]),
        )

    async def _speed_evidence(
        self, conn: Any, position: VehiclePosition
    ) -> EtaEvidence | None:
        candidates = (
            (
                EtaMethod.VEHICLE_RECENT_SPEED,
                _VEHICLE_SPEED_WINDOW_SECONDS,
                _VEHICLE_MIN_SAMPLES,
                True,
            ),
            (
                EtaMethod.ROUTE_SHAPE_RECENT_SPEED,
                _ROUTE_SHAPE_SPEED_WINDOW_SECONDS,
                _ROUTE_SHAPE_MIN_SAMPLES,
                False,
            ),
        )
        for method, window_seconds, minimum_samples, vehicle_only in candidates:
            row = await conn.fetchrow(
                """
                SELECT
                    count(*)::bigint AS sample_count,
                    percentile_cont(ARRAY[0.25,0.5,0.75])
                        WITHIN GROUP (ORDER BY speed_mps) AS speed_percentiles
                FROM transit.vehicle_positions
                WHERE route_id = $1
                  AND shape_id = $2
                  AND observed_at >= $3::timestamptz
                      - make_interval(secs => $4::double precision)
                  AND observed_at <= $3::timestamptz
                  AND speed_mps BETWEEN $5 AND $6
                  AND quality_status <> 'invalid'
                  AND (
                    NOT $7
                    OR (agency_id = $8 AND vehicle_id = $9)
                  )
                """,
                position.route_id,
                position.shape_id,
                position.observed_at,
                float(window_seconds),
                _MIN_ETA_SPEED_MPS,
                _MAX_ETA_SPEED_MPS,
                vehicle_only,
                position.agency_id,
                position.vehicle_id,
            )
            sample_count = int(row["sample_count"] or 0)
            percentiles = row["speed_percentiles"]
            if sample_count >= minimum_samples and percentiles is not None:
                return EtaEvidence(
                    method=method,
                    sample_count=sample_count,
                    window_seconds=window_seconds,
                    speed_p25_mps=float(percentiles[0]),
                    speed_median_mps=float(percentiles[1]),
                    speed_p75_mps=float(percentiles[2]),
                )
            if (
                method is EtaMethod.VEHICLE_RECENT_SPEED
                and self.historical_profiles_enabled
            ):
                historical = await PostgresGtfsCatalog._historical_speed_evidence(
                    conn, position
                )
                if historical is not None:
                    return historical
        return None

    async def search_routes(
        self,
        *,
        query: str | None,
        limit: int,
        offset: int,
    ) -> GtfsRoutePage:
        normalized = query.strip() if query else None
        if normalized:
            escaped = normalized.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            pattern = f"%{escaped}%"
        else:
            pattern = None
        async with self.pool.acquire() as conn:
            total = await conn.fetchval(
                """
                SELECT count(*)
                FROM transit.gtfs_routes route
                JOIN transit.gtfs_snapshots snapshot USING (snapshot_id)
                WHERE snapshot.status = 'active'
                  AND (
                    $1::text IS NULL
                    OR route.route_id ILIKE $1 ESCAPE '\\'
                    OR route.route_short_name ILIKE $1 ESCAPE '\\'
                    OR route.route_long_name ILIKE $1 ESCAPE '\\'
                  )
                """,
                pattern,
            )
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
                    route.route_type, route.route_color, route.route_text_color
                FROM transit.gtfs_routes route
                JOIN active USING (snapshot_id)
                WHERE $1::text IS NULL
                   OR route.route_id ILIKE $1 ESCAPE '\\'
                   OR route.route_short_name ILIKE $1 ESCAPE '\\'
                   OR route.route_long_name ILIKE $1 ESCAPE '\\'
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
        items = tuple(
            GtfsRoute.model_validate(dict(row))
            for row in rows
        )
        return GtfsRoutePage(items=items, limit=limit, offset=offset, total=int(total or 0))

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
            total = await conn.fetchval(
                """
                SELECT count(*)
                FROM transit.gtfs_stops stop
                JOIN transit.gtfs_snapshots snapshot USING (snapshot_id)
                WHERE snapshot.status = 'active'
                  AND ST_DWithin(
                    stop.location,
                    ST_SetSRID(ST_MakePoint($2,$1),4326)::geography,
                    $3
                  )
                """,
                latitude,
                longitude,
                radius_m,
            )
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
                SELECT *
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
        items = tuple(
            NearbyGtfsStop.model_validate(dict(row))
            for row in rows
        )
        return GtfsStopPage(items=items, limit=limit, offset=offset, total=int(total or 0))

    async def match_vehicle_to_upcoming_stops(
        self,
        *,
        position: VehiclePosition,
        limit: int,
        max_projection_distance_m: float,
        evaluated_at: datetime | None = None,
    ) -> VehicleJourneyMatch:
        evaluated_at = evaluated_at or datetime.now(UTC)
        observed_at = position.observed_at
        if observed_at.tzinfo is None:
            observed_at = observed_at.replace(tzinfo=UTC)
        position_age_seconds = max(
            0.0,
            (evaluated_at - observed_at.astimezone(UTC)).total_seconds(),
        )
        base = {
            "vehicle_id": position.vehicle_id,
            "route_id": position.route_id,
            "source_trip_id": position.trip_id,
            "shape_id": position.shape_id,
            "observed_at": position.observed_at,
            "evaluated_at": evaluated_at,
            "position_age_seconds": position_age_seconds,
        }
        if position.shape_id is None:
            return VehicleJourneyMatch(
                available=False,
                unavailable_reason=JourneyUnavailableReason.MISSING_SHAPE_ID,
                **base,
            )

        async with self.pool.acquire() as conn:
            candidate = await conn.fetchrow(
                """
                WITH active AS (
                    SELECT snapshot_id
                    FROM transit.gtfs_snapshots
                    WHERE status = 'active'
                )
                SELECT trip.snapshot_id, trip.trip_id, trip.shape_id
                FROM transit.gtfs_trips trip
                JOIN active USING (snapshot_id)
                LEFT JOIN transit.gtfs_stop_times stop_time
                  ON stop_time.snapshot_id = trip.snapshot_id
                 AND stop_time.trip_id = trip.trip_id
                WHERE trip.route_id = $1 AND trip.shape_id = $2
                GROUP BY trip.snapshot_id, trip.trip_id, trip.shape_id
                ORDER BY (trip.trip_id = $3) DESC NULLS LAST,
                         count(stop_time.stop_sequence) DESC,
                         trip.trip_id
                LIMIT 1
                """,
                position.route_id,
                position.shape_id,
                position.trip_id,
            )
            if candidate is None:
                return VehicleJourneyMatch(
                    available=False,
                    unavailable_reason=JourneyUnavailableReason.ROUTE_SHAPE_NOT_FOUND,
                    **base,
                )

            projection = await conn.fetchrow(
                """
                WITH input AS (
                    SELECT ST_SetSRID(ST_MakePoint($4,$3),4326) AS location
                ), shape_points AS (
                    SELECT
                        shape_pt_sequence,
                        shape_pt_lat,
                        shape_pt_lon,
                        shape_dist_traveled,
                        lead(shape_pt_lat) OVER (ORDER BY shape_pt_sequence) AS next_lat,
                        lead(shape_pt_lon) OVER (ORDER BY shape_pt_sequence) AS next_lon,
                        lead(shape_dist_traveled) OVER (
                            ORDER BY shape_pt_sequence
                        ) AS next_distance
                    FROM transit.gtfs_shapes
                    WHERE snapshot_id = $1
                      AND shape_id = $2
                      AND shape_dist_traveled IS NOT NULL
                ), segments AS (
                    SELECT
                        shape_dist_traveled,
                        next_distance,
                        ST_MakeLine(
                            ST_SetSRID(ST_MakePoint(shape_pt_lon,shape_pt_lat),4326),
                            ST_SetSRID(ST_MakePoint(next_lon,next_lat),4326)
                        ) AS segment
                    FROM shape_points
                    WHERE next_distance IS NOT NULL
                      AND (shape_pt_lon,shape_pt_lat) <> (next_lon,next_lat)
                )
                SELECT
                    shape_dist_traveled
                      + ST_LineLocatePoint(segment,input.location)
                        * (next_distance-shape_dist_traveled)
                        AS projected_shape_dist_traveled,
                    ST_Distance(segment::geography,input.location::geography)
                        AS projection_distance_m
                FROM segments
                CROSS JOIN input
                ORDER BY projection_distance_m
                LIMIT 1
                """,
                candidate["snapshot_id"],
                candidate["shape_id"],
                position.latitude,
                position.longitude,
            )
            if projection is None:
                return VehicleJourneyMatch(
                    available=False,
                    unavailable_reason=JourneyUnavailableReason.SHAPE_PROJECTION_FAILED,
                    snapshot_id=candidate["snapshot_id"],
                    matched_trip_id=candidate["trip_id"],
                    **base,
                )

            projection_distance_m = float(projection["projection_distance_m"])
            projected_distance = float(projection["projected_shape_dist_traveled"])
            method = (
                JourneyMatchMethod.EXACT_TRIP
                if candidate["trip_id"] == position.trip_id
                else JourneyMatchMethod.ROUTE_SHAPE_PATTERN
            )
            if projection_distance_m > max_projection_distance_m:
                return VehicleJourneyMatch(
                    available=False,
                    unavailable_reason=JourneyUnavailableReason.VEHICLE_OFF_SHAPE,
                    snapshot_id=candidate["snapshot_id"],
                    matched_trip_id=candidate["trip_id"],
                    match_method=method,
                    projected_shape_dist_traveled=projected_distance,
                    projection_distance_m=projection_distance_m,
                    **base,
                )

            rows = await conn.fetch(
                """
                SELECT
                    stop.stop_id, stop.stop_name,
                    stop.stop_lat AS latitude, stop.stop_lon AS longitude,
                    stop_time.stop_sequence, stop_time.shape_dist_traveled,
                    greatest(stop_time.shape_dist_traveled - $3, 0)
                        AS shape_distance_ahead
                FROM transit.gtfs_stop_times stop_time
                JOIN transit.gtfs_stops stop
                  ON stop.snapshot_id = stop_time.snapshot_id
                 AND stop.stop_id = stop_time.stop_id
                WHERE stop_time.snapshot_id = $1
                  AND stop_time.trip_id = $2
                  AND stop_time.shape_dist_traveled >= $3
                ORDER BY stop_time.shape_dist_traveled, stop_time.stop_sequence
                LIMIT $4
                """,
                candidate["snapshot_id"],
                candidate["trip_id"],
                projected_distance,
                limit,
            )

            eta_evidence = None
            eta_unavailable_reason = None
            if rows:
                if position_age_seconds > MAX_POSITION_AGE_SECONDS:
                    eta_unavailable_reason = EtaUnavailableReason.STALE_POSITION
                else:
                    eta_evidence = await self._speed_evidence(conn, position)
                    if eta_evidence is None:
                        eta_unavailable_reason = (
                            EtaUnavailableReason.INSUFFICIENT_SPEED_EVIDENCE
                        )

        upcoming_stops = tuple(UpcomingGtfsStop.model_validate(dict(row)) for row in rows)
        if upcoming_stops and eta_evidence is not None:
            upcoming_stops = estimate_stop_arrivals(
                upcoming_stops,
                evidence=eta_evidence,
                observed_at=observed_at,
                evaluated_at=evaluated_at,
            )
        return VehicleJourneyMatch(
            available=bool(upcoming_stops),
            unavailable_reason=(
                None if upcoming_stops else JourneyUnavailableReason.NO_UPCOMING_STOPS
            ),
            snapshot_id=candidate["snapshot_id"],
            matched_trip_id=candidate["trip_id"],
            match_method=method,
            projected_shape_dist_traveled=projected_distance,
            projection_distance_m=projection_distance_m,
            eta_evidence=eta_evidence,
            eta_unavailable_reason=eta_unavailable_reason,
            upcoming_stops=upcoming_stops,
            **base,
        )
