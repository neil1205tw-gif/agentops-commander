from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from tests.helpers import make_settings


@pytest.fixture
def client() -> Iterator[TestClient]:
    settings = make_settings(
        APP_ENV="test",
        DATABASE_URL="postgresql+psycopg://x:y@127.0.0.1:1/none",
        CORS_ORIGINS="http://localhost:5173",
    )
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def test_live_returns_ok_without_database(client: TestClient) -> None:
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready_ok_when_database_is_healthy(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def healthy(engine: object) -> bool:
        return True

    monkeypatch.setattr("app.api.health.check_database", healthy)
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "checks": {"app": "ok", "database": "ok"}}


def test_ready_503_without_leaking_details(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def failing(engine: object) -> bool:
        return False

    monkeypatch.setattr("app.api.health.check_database", failing)
    response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "checks": {"app": "ok", "database": "error"},
    }


def test_ready_503_when_database_unreachable(client: TestClient) -> None:
    response = client.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["checks"]["database"] == "error"
    assert "127.0.0.1" not in response.text
    assert "x:y" not in response.text


def test_cors_allows_only_configured_origin(client: TestClient) -> None:
    allowed = client.get("/health/live", headers={"Origin": "http://localhost:5173"})
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:5173"
    denied = client.get("/health/live", headers={"Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in denied.headers


def test_api_v1_router_has_no_endpoints(client: TestClient) -> None:
    assert client.get("/api/v1/anything").status_code == 404
