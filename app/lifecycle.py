"""Lifespan wiring: fail-fast settings, DB pool, Temporal client handle."""

import contextlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import get_settings
from app.db import Database


def build_db(app: FastAPI) -> Database:
    return Database(get_settings())


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    db = build_db(app)
    app.state.db = db
    with contextlib.suppress(Exception):  # live must keep serving; ready will report 503
        await db.connect()
    yield
    await db.disconnect()
