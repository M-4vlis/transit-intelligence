from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
import json
from typing import Any

from app.modules.mobility.models import VehiclePosition


async def create_valkey_client(url: str) -> Any:
    from redis.asyncio import Redis

    client = Redis.from_url(url, decode_responses=True, health_check_interval=30)
    await client.ping()
    return client


class ValkeyLivePositionCache:
    PUT_LATEST_SCRIPT = """
    local current = redis.call('get', KEYS[2])
    if current and tonumber(current) > tonumber(ARGV[2]) then
      return 0
    end
    redis.call('set', KEYS[1], ARGV[1], 'EX', ARGV[4])
    redis.call('set', KEYS[2], ARGV[2], 'EX', ARGV[4])
    redis.call('zadd', KEYS[3], ARGV[2], ARGV[3])
    redis.call('zremrangebyscore', KEYS[3], '-inf', ARGV[5])
    redis.call('expire', KEYS[3], ARGV[6])
    return 1
    """

    RELEASE_LEASE_SCRIPT = """
    if redis.call('get', KEYS[1]) == ARGV[1] then
      return redis.call('del', KEYS[1])
    else
      return 0
    end
    """

    def __init__(self, client: Any, *, ttl_seconds: int = 180) -> None:
        self.client = client
        self.ttl_seconds = ttl_seconds

    @staticmethod
    def _vehicle_key(agency_id: str, vehicle_id: str) -> str:
        return f"mobility:v1:vehicle:{agency_id}:{vehicle_id}"

    @staticmethod
    def _vehicle_timestamp_key(agency_id: str, vehicle_id: str) -> str:
        return f"mobility:v1:vehicle-ts:{agency_id}:{vehicle_id}"

    @staticmethod
    def _route_key(agency_id: str, route_id: str) -> str:
        return f"mobility:v1:route:{agency_id}:{route_id}"

    async def ping(self) -> bool:
        return bool(await self.client.ping())

    async def put_many(self, positions: Sequence[VehiclePosition]) -> int:
        if not positions:
            return 0

        pipe = self.client.pipeline(transaction=False)
        now_epoch = datetime.now(UTC).timestamp()
        cutoff = now_epoch - self.ttl_seconds
        route_ttl = self.ttl_seconds * 2

        for position in positions:
            vehicle_key = self._vehicle_key(position.agency_id, position.vehicle_id)
            timestamp_key = self._vehicle_timestamp_key(position.agency_id, position.vehicle_id)
            route_key = self._route_key(position.agency_id, position.route_id)
            payload = json.dumps(position.model_dump(mode="json"), separators=(",", ":"))
            score = position.observed_at.astimezone(UTC).timestamp()
            member = json.dumps(
                [position.agency_id, position.vehicle_id],
                separators=(",", ":"),
            )
            pipe.eval(
                self.PUT_LATEST_SCRIPT,
                3,
                vehicle_key,
                timestamp_key,
                route_key,
                payload,
                score,
                member,
                self.ttl_seconds,
                cutoff,
                route_ttl,
            )

        results = await pipe.execute()
        return sum(int(result or 0) for result in results)

    async def by_route(self, *, agency_id: str, route_id: str) -> Sequence[VehiclePosition]:
        route_key = self._route_key(agency_id, route_id)
        cutoff = datetime.now(UTC).timestamp() - self.ttl_seconds
        members = await self.client.zrangebyscore(route_key, cutoff, "+inf")
        if not members:
            return []

        keys = []
        for member in members:
            try:
                member_agency, vehicle_id = json.loads(member)
            except (ValueError, TypeError):
                continue
            keys.append(self._vehicle_key(str(member_agency), str(vehicle_id)))
        payloads = await self.client.mget(keys)
        positions = [
            VehiclePosition.model_validate_json(payload)
            for payload in payloads
            if payload is not None
        ]
        # A vehicle can switch routes while the old route ZSET membership is still inside
        # its short TTL. The vehicle payload is authoritative, so never leak it into the
        # previous route response.
        return sorted(
            (position for position in positions if position.route_id == route_id),
            key=lambda position: position.vehicle_id,
        )

    async def try_acquire(self, *, name: str, token: str, ttl_ms: int) -> bool:
        key = f"lease:v1:{name}"
        return bool(await self.client.set(key, token, nx=True, px=ttl_ms))

    async def release(self, *, name: str, token: str) -> None:
        key = f"lease:v1:{name}"
        await self.client.eval(self.RELEASE_LEASE_SCRIPT, 1, key, token)
