"""Async Postgres connection pool (asyncpg)."""

import asyncpg

from app.config import Settings


class Database:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._pool: asyncpg.Pool | None = None

    @property
    def pool(self) -> asyncpg.Pool:
        if self._pool is None:
            raise RuntimeError("Database pool is not initialized")
        return self._pool

    @property
    def is_ready(self) -> bool:
        return self._pool is not None

    async def connect(self) -> None:
        try:
            self._pool = await asyncpg.create_pool(
                self._settings.database_url, min_size=1, max_size=10
            )
        except Exception:
            self._pool = None
            raise

    async def disconnect(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
