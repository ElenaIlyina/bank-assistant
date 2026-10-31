"""Tests for fail-fast config and health endpoints (criterias.txt)."""

import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

os.environ.setdefault("DATABASE_URL", "postgresql://invalid/none")
os.environ.setdefault("TEMPORAL_HOST", "localhost:7233")

from app.config import get_settings  # noqa: E402
from app.db import Database  # noqa: E402
from app.main import create_app  # noqa: E402


@pytest.fixture
def client() -> Iterator[TestClient]:
    """App whose DB pool is permanently broken (DB stopped)."""
    with TestClient(create_app(), raise_server_exceptions=False) as c:
        db = Database.__new__(Database)
        db._pool = None  # simulate __init__ before a successful connect()
        c.app.state.db = db
        yield c


def test_missing_env_prevents_startup(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("DATABASE_URL", "TEMPORAL_HOST"):
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(ValidationError):
        get_settings()


def test_live_ok_without_db(client: TestClient) -> None:
    assert client.get("/live").status_code == 200


def test_ready_fails_without_db(client: TestClient) -> None:
    assert client.get("/ready").status_code == 503
