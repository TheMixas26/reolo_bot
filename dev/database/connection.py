from __future__ import annotations

import os
from typing import Any

import asyncpg


_pool: asyncpg.Pool | None = None
_database_url: str | None = None

_conn = None      # Ура, ненужная совместимость номер 1
_DB_LOCK = None   # Ура, ненужная совместимость номер 2


def database_url() -> str:
    url = _database_url or os.getenv("DATABASE_URL")
    if url:
        return url

    try:
        import config as cfg
    except Exception:
        cfg = None

    if cfg is not None:
        url = getattr(cfg, "DATABASE_URL", None) or getattr(cfg, "POSTGRES_DSN", None)
        if url:
            return url

    return "postgresql://postgres:postgres@localhost:5432/reolo_bot"


async def init_pool(database_url_value: str | None = None) -> asyncpg.Pool:
    global _pool, _database_url
    if database_url_value is not None:
        _database_url = database_url_value
    if _pool is None:
        _pool = await asyncpg.create_pool(dsn=database_url(), min_size=1, max_size=10)
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


async def get_pool() -> asyncpg.Pool:
    if _pool is None:
        return await init_pool()
    return _pool


async def execute(query: str, *args: Any) -> str:
    pool = await get_pool()
    return await pool.execute(query, *args)


async def fetch(query: str, *args: Any) -> list[asyncpg.Record]:
    pool = await get_pool()
    return await pool.fetch(query, *args)


async def fetchrow(query: str, *args: Any) -> asyncpg.Record | None:
    pool = await get_pool()
    return await pool.fetchrow(query, *args)


async def fetchval(query: str, *args: Any) -> Any:
    pool = await get_pool()
    return await pool.fetchval(query, *args)
