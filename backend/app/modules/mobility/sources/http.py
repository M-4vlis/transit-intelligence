from __future__ import annotations

import asyncio
import hashlib
import json
import random
import tempfile
import time
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx

from app.modules.mobility.adapters.base import TransitSourceUnavailable


def validate_external_source_url(url: str, *, allowed_hosts: set[str]) -> None:
    parsed = urlsplit(url)
    hostname = (parsed.hostname or "").lower()
    if parsed.scheme != "https":
        raise ValueError("external mobility sources must use HTTPS")
    if parsed.username or parsed.password:
        raise ValueError("external mobility source URLs must not contain credentials")
    if not hostname or hostname not in {host.lower() for host in allowed_hosts}:
        raise ValueError("external mobility source host is not allowlisted")
    if parsed.fragment:
        raise ValueError("external mobility source URLs must not contain fragments")


class CircuitOpen(TransitSourceUnavailable):
    pass


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    max_attempts: int = 4
    base_delay_seconds: float = 0.5
    max_delay_seconds: float = 8.0
    jitter_ratio: float = 0.25


class CircuitBreaker:
    def __init__(
        self,
        *,
        failure_threshold: int = 5,
        recovery_timeout_seconds: float = 30.0,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout_seconds = recovery_timeout_seconds
        self._failures = 0
        self._opened_until = 0.0

    def before_call(self) -> None:
        if self._opened_until > time.monotonic():
            raise CircuitOpen("external source circuit is open")
        if self._opened_until:
            self._opened_until = 0.0
            self._failures = 0

    def record_success(self) -> None:
        self._failures = 0
        self._opened_until = 0.0

    def record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self.failure_threshold:
            self._opened_until = time.monotonic() + self.recovery_timeout_seconds


class ResilientJsonClient:
    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        policy: RetryPolicy | None = None,
        breaker: CircuitBreaker | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        random_value: Callable[[], float] = random.random,
        max_response_bytes: int = 20_000_000,
    ) -> None:
        self.client = client
        self.policy = policy or RetryPolicy()
        self.breaker = breaker or CircuitBreaker()
        self.sleep = sleep
        self.random_value = random_value
        self.max_response_bytes = max_response_bytes

    async def get_json(
        self,
        url: str,
        *,
        params: Mapping[str, str] | None = None,
    ) -> Any:
        self.breaker.before_call()
        last_error: Exception | None = None

        for attempt in range(1, self.policy.max_attempts + 1):
            try:
                async with self.client.stream(
                    "GET",
                    url,
                    params=params,
                    headers={
                        "Accept": "application/json",
                        "User-Agent": "TransitIntelligence/0.7.1",
                    },
                ) as response:
                    if response.status_code == 429 or response.status_code >= 500:
                        raise TransitSourceUnavailable(
                            f"source returned transient HTTP {response.status_code}"
                        )
                    if response.status_code >= 400:
                        raise TransitSourceUnavailable(
                            f"source returned non-retryable HTTP {response.status_code}"
                        )

                    declared_size = response.headers.get("content-length")
                    if declared_size:
                        try:
                            declared_bytes = int(declared_size)
                        except ValueError as exc:
                            raise TransitSourceUnavailable(
                                "source returned invalid content-length"
                            ) from exc
                        if declared_bytes > self.max_response_bytes:
                            raise TransitSourceUnavailable("source response exceeded size limit")

                    chunks: list[bytes] = []
                    total = 0
                    async for chunk in response.aiter_bytes():
                        total += len(chunk)
                        if total > self.max_response_bytes:
                            raise TransitSourceUnavailable("source response exceeded size limit")
                        chunks.append(chunk)

                try:
                    payload = json.loads(b"".join(chunks))
                except (ValueError, UnicodeDecodeError) as exc:
                    raise TransitSourceUnavailable("source returned invalid JSON") from exc
                self.breaker.record_success()
                return payload
            except (httpx.TimeoutException, httpx.NetworkError, TransitSourceUnavailable) as exc:
                last_error = exc
                retryable = isinstance(exc, (httpx.TimeoutException, httpx.NetworkError)) or (
                    "transient HTTP" in str(exc)
                )
                if not retryable or attempt >= self.policy.max_attempts:
                    self.breaker.record_failure()
                    raise TransitSourceUnavailable(str(exc)) from exc

                delay = min(
                    self.policy.max_delay_seconds,
                    self.policy.base_delay_seconds * (2 ** (attempt - 1)),
                )
                jitter = delay * self.policy.jitter_ratio * self.random_value()
                await self.sleep(delay + jitter)

        self.breaker.record_failure()
        raise TransitSourceUnavailable(str(last_error or "unknown source failure"))


@dataclass(frozen=True, slots=True)
class DownloadArtifact:
    path: Path
    byte_size: int
    sha256: str
    content_type: str


class ResilientBinaryDownloader:
    """Download a bounded binary artifact without buffering it in memory."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        policy: RetryPolicy | None = None,
        breaker: CircuitBreaker | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        random_value: Callable[[], float] = random.random,
        max_response_bytes: int = 64 * 1024 * 1024,
        accepted_content_types: set[str] | None = None,
    ) -> None:
        self.client = client
        self.policy = policy or RetryPolicy()
        self.breaker = breaker or CircuitBreaker()
        self.sleep = sleep
        self.random_value = random_value
        self.max_response_bytes = max_response_bytes
        self.accepted_content_types = accepted_content_types or {
            "application/zip",
            "application/octet-stream",
            "binary/octet-stream",
        }

    async def download(
        self,
        url: str,
        destination: Path,
        *,
        allowed_hosts: set[str],
    ) -> DownloadArtifact:
        validate_external_source_url(url, allowed_hosts=allowed_hosts)
        self.breaker.before_call()
        destination.parent.mkdir(parents=True, exist_ok=True)
        last_error: Exception | None = None

        for attempt in range(1, self.policy.max_attempts + 1):
            temporary_path: Path | None = None
            try:
                with tempfile.NamedTemporaryFile(
                    dir=destination.parent,
                    prefix=f".{destination.name}.",
                    suffix=".part",
                    delete=False,
                ) as temporary:
                    temporary_path = Path(temporary.name)

                async with self.client.stream(
                    "GET",
                    url,
                    headers={
                        "Accept": "application/zip, application/octet-stream",
                        "User-Agent": "TransitIntelligence/0.7",
                    },
                ) as response:
                    if response.status_code == 429 or response.status_code >= 500:
                        raise TransitSourceUnavailable(
                            f"source returned transient HTTP {response.status_code}"
                        )
                    if response.status_code >= 300:
                        raise TransitSourceUnavailable(
                            f"source returned non-retryable HTTP {response.status_code}"
                        )

                    content_type = response.headers.get("content-type", "")
                    media_type = content_type.split(";", 1)[0].strip().lower()
                    if media_type not in self.accepted_content_types:
                        raise TransitSourceUnavailable(
                            f"source returned unexpected content-type: {media_type or 'missing'}"
                        )

                    declared_size = response.headers.get("content-length")
                    if declared_size:
                        try:
                            declared_bytes = int(declared_size)
                        except ValueError as exc:
                            raise TransitSourceUnavailable(
                                "source returned invalid content-length"
                            ) from exc
                        if declared_bytes < 0 or declared_bytes > self.max_response_bytes:
                            raise TransitSourceUnavailable("source response exceeded size limit")

                    digest = hashlib.sha256()
                    total = 0
                    with temporary_path.open("wb") as output:  # noqa: ASYNC230
                        async for chunk in response.aiter_bytes():
                            total += len(chunk)
                            if total > self.max_response_bytes:
                                raise TransitSourceUnavailable(
                                    "source response exceeded size limit"
                                )
                            digest.update(chunk)
                            output.write(chunk)

                temporary_path.replace(destination)
                self.breaker.record_success()
                return DownloadArtifact(
                    path=destination,
                    byte_size=total,
                    sha256=digest.hexdigest(),
                    content_type=media_type,
                )
            except (httpx.TimeoutException, httpx.NetworkError, TransitSourceUnavailable) as exc:
                if temporary_path is not None:
                    temporary_path.unlink(missing_ok=True)
                last_error = exc
                retryable = isinstance(exc, (httpx.TimeoutException, httpx.NetworkError)) or (
                    "transient HTTP" in str(exc)
                )
                if not retryable or attempt >= self.policy.max_attempts:
                    self.breaker.record_failure()
                    raise TransitSourceUnavailable(str(exc)) from exc

                delay = min(
                    self.policy.max_delay_seconds,
                    self.policy.base_delay_seconds * (2 ** (attempt - 1)),
                )
                jitter = delay * self.policy.jitter_ratio * self.random_value()
                await self.sleep(delay + jitter)

        self.breaker.record_failure()
        raise TransitSourceUnavailable(str(last_error or "unknown source failure"))
