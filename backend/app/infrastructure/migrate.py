from __future__ import annotations

import asyncio
from pathlib import Path

from app.core.config import settings
from app.infrastructure.postgres import create_postgres_pool

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


async def run() -> None:
    pool = await create_postgres_pool(settings.database_url)
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS public.schema_migrations (
                    version text PRIMARY KEY,
                    applied_at timestamptz NOT NULL DEFAULT now()
                )
                """
            )

        for migration in sorted(MIGRATIONS_DIR.glob("*.sql")):
            version = migration.name
            async with pool.acquire() as conn:
                applied = await conn.fetchval(
                    "SELECT 1 FROM public.schema_migrations WHERE version = $1", version
                )
                if applied:
                    continue
                sql = migration.read_text(encoding="utf-8")
                async with conn.transaction():
                    await conn.execute(sql)
                    await conn.execute(
                        "INSERT INTO public.schema_migrations(version) VALUES ($1)", version
                    )
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(run())
