from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest

from app.infrastructure.postgres import create_postgres_pool


@pytest.mark.asyncio
async def test_postgres_pool_uses_short_default_command_timeout(monkeypatch) -> None:
    observed = {}

    async def fake_create_pool(**kwargs):
        observed.update(kwargs)
        return object()

    monkeypatch.setitem(sys.modules, "asyncpg", SimpleNamespace(create_pool=fake_create_pool))

    await create_postgres_pool("postgresql://example")

    assert observed["command_timeout"] == 10


@pytest.mark.asyncio
async def test_postgres_pool_allows_unbounded_maintenance_commands(monkeypatch) -> None:
    observed = {}

    async def fake_create_pool(**kwargs):
        observed.update(kwargs)
        return object()

    monkeypatch.setitem(sys.modules, "asyncpg", SimpleNamespace(create_pool=fake_create_pool))

    await create_postgres_pool("postgresql://example", command_timeout=None)

    assert observed["command_timeout"] is None
