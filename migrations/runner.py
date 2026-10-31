"""Idempotent migration runner: applies each migration file at most once.

Re-running `make migrate` must be a no-op (criterias.txt).
"""

import asyncio
import sys
from pathlib import Path

import asyncpg

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


async def migrate(database_url: str) -> None:
    conn = await asyncpg.connect(database_url)
    try:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
        applied = {r["version"] for r in await conn.fetch("SELECT version FROM schema_migrations")}
        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if path.stem in applied:
                continue
            await conn.execute(path.read_text(encoding="utf-8"))
            await conn.execute(
                "INSERT INTO schema_migrations (version) VALUES ($1) ON CONFLICT DO NOTHING",
                path.stem,
            )
    finally:
        await conn.close()


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else None
    if not url:
        print("usage: python -m migrations.runner <database_url>", file=sys.stderr)
        raise SystemExit(2)
    asyncio.run(migrate(url))
