from pathlib import Path

import httpx
import pytest

from app.modules.mobility.sources.http import (
    ResilientBinaryDownloader,
    ResilientJsonClient,
    RetryPolicy,
)


@pytest.mark.asyncio
async def test_transient_http_is_retried_with_backoff() -> None:
    calls = 0
    sleeps: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls < 3:
            return httpx.Response(503, json={"error": "temporary"})
        return httpx.Response(200, json={"ok": True})

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = ResilientJsonClient(
            http_client,
            policy=RetryPolicy(max_attempts=4, base_delay_seconds=1, jitter_ratio=0),
            sleep=fake_sleep,
        )
        payload = await client.get_json("https://example.invalid/data")

    assert payload == {"ok": True}
    assert calls == 3
    assert sleeps == [1, 2]


@pytest.mark.asyncio
async def test_response_size_is_bounded() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, content=b'{"payload":"' + b'x' * 100 + b'"}')
    )
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = ResilientJsonClient(http_client, max_response_bytes=32)
        with pytest.raises(Exception, match="size limit"):
            await client.get_json("https://example.invalid/data")


@pytest.mark.asyncio
async def test_invalid_content_length_is_rejected() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            headers={"content-length": "not-a-number"},
            content=b'{"ok":true}',
        )
    )
    async with httpx.AsyncClient(transport=transport) as http_client:
        client = ResilientJsonClient(http_client)
        with pytest.raises(Exception, match="invalid content-length"):
            await client.get_json("https://example.invalid/data")


def test_external_source_url_requires_https_and_allowlisted_host() -> None:
    from app.modules.mobility.sources.http import validate_external_source_url

    validate_external_source_url(
        "https://dados.mobilidade.rio/gps/sppo",
        allowed_hosts={"dados.mobilidade.rio"},
    )

    with pytest.raises(ValueError):
        validate_external_source_url(
            "http://dados.mobilidade.rio/gps/sppo",
            allowed_hosts={"dados.mobilidade.rio"},
        )
    with pytest.raises(ValueError):
        validate_external_source_url(
            "https://127.0.0.1/internal",
            allowed_hosts={"dados.mobilidade.rio"},
        )
    with pytest.raises(ValueError):
        validate_external_source_url(
            "https://user:pass@dados.mobilidade.rio/gps/sppo",
            allowed_hosts={"dados.mobilidade.rio"},
        )


@pytest.mark.asyncio
async def test_binary_download_is_streamed_and_hashed(tmp_path: Path) -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            headers={"content-type": "application/zip"},
            content=b"PK-safe-test",
        )
    )
    destination = tmp_path / "feed.zip"
    async with httpx.AsyncClient(transport=transport) as http_client:
        artifact = await ResilientBinaryDownloader(http_client).download(
            "https://www.arcgis.com/feed.zip",
            destination,
            allowed_hosts={"www.arcgis.com"},
        )

    assert artifact.path.read_bytes() == b"PK-safe-test"
    assert artifact.byte_size == 12
    assert artifact.sha256 == "2a51200673f8bc830f921c4ce625159f5755ba3c9abf0003549259519b6ee7ad"


@pytest.mark.asyncio
async def test_binary_download_rejects_wrong_type_and_removes_partial(tmp_path: Path) -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            headers={"content-type": "text/html"},
            content=b"blocked",
        )
    )
    destination = tmp_path / "feed.zip"
    async with httpx.AsyncClient(transport=transport) as http_client:
        downloader = ResilientBinaryDownloader(http_client)
        with pytest.raises(Exception, match="unexpected content-type"):
            await downloader.download(
                "https://www.arcgis.com/feed.zip",
                destination,
                allowed_hosts={"www.arcgis.com"},
            )

    assert not destination.exists()
    assert not list(tmp_path.glob("*.part"))


@pytest.mark.asyncio
async def test_binary_download_validates_allowlist_before_network(tmp_path: Path) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(200, content=b"unexpected")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http_client:
        with pytest.raises(ValueError, match="not allowlisted"):
            await ResilientBinaryDownloader(http_client).download(
                "https://evil.invalid/feed.zip",
                tmp_path / "feed.zip",
                allowed_hosts={"www.arcgis.com"},
            )

    assert calls == 0
