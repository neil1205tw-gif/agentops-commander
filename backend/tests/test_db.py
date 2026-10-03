import asyncio
from typing import Any, cast

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

import app.db
from app.db import check_database, create_engine
from app.main import create_app
from tests.helpers import make_settings


class _BrokenEngine:
    def connect(self) -> Any:
        raise RuntimeError("boom: postgresql://user:secret@host/db")


class _SlowConnection:
    async def __aenter__(self) -> "_SlowConnection":
        await asyncio.sleep(5)
        return self

    async def __aexit__(self, *args: object) -> None:
        return None


class _SlowEngine:
    def connect(self) -> _SlowConnection:
        return _SlowConnection()


class _HealthyConnection:
    async def __aenter__(self) -> "_HealthyConnection":
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def execute(self, statement: object) -> None:
        assert str(statement) == "SELECT 1"


class _HealthyEngine:
    def connect(self) -> _HealthyConnection:
        return _HealthyConnection()


async def test_check_database_true_when_query_succeeds() -> None:
    assert await check_database(cast(AsyncEngine, _HealthyEngine())) is True


async def test_check_database_false_on_exception(capsys: pytest.CaptureFixture[str]) -> None:
    assert await check_database(cast(AsyncEngine, _BrokenEngine())) is False
    out = capsys.readouterr().out
    assert "RuntimeError" in out
    assert "secret" not in out


async def test_check_database_false_on_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(app.db, "DB_CHECK_TIMEOUT_SECONDS", 0.05)
    assert await check_database(cast(AsyncEngine, _SlowEngine())) is False


async def test_check_database_false_when_unreachable() -> None:
    engine = create_engine(make_settings(DATABASE_URL="postgresql+psycopg://x:y@127.0.0.1:1/none"))
    try:
        assert await check_database(engine) is False
    finally:
        await engine.dispose()


def test_lifespan_exposes_session_factory() -> None:
    settings = make_settings(DATABASE_URL="postgresql+psycopg://x:y@127.0.0.1:1/none")
    with TestClient(create_app(settings)) as client:
        factory = client.app.state.session_factory  # type: ignore[attr-defined]
        assert isinstance(factory, async_sessionmaker)
