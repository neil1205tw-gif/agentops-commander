from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.auth import TokenVerifier
from app.main import create_app
from tests.auth_support import FakeJWKSProvider, KeyPair, auth_settings, dev_token, supabase_claims

UNAUTHORIZED = {"detail": "Invalid or expired token"}


def _client(**settings: object) -> TestClient:
    resolved = auth_settings(**settings)
    app = create_app(resolved)
    # No network in tests: the JWKS comes from memory (and has no keys).
    app.state.token_verifier = TokenVerifier(resolved, FakeJWKSProvider())
    return TestClient(app)


@pytest.fixture
def production_client() -> Iterator[TestClient]:
    with _client(APP_ENV="production") as client:
        yield client


def test_auth_config_in_development() -> None:
    with _client(APP_ENV="development") as client:
        response = client.get("/api/v1/auth/config")
    assert response.status_code == 200
    assert response.json() == {"dev_login_enabled": True}


def test_auth_config_in_production(production_client: TestClient) -> None:
    response = production_client.get("/api/v1/auth/config")
    assert response.status_code == 200
    assert response.json() == {"dev_login_enabled": False}


def test_dev_login_route_does_not_exist_in_production(production_client: TestClient) -> None:
    response = production_client.post("/api/v1/auth/dev-login", json={"role": "admin"})
    assert response.status_code == 404
    assert "/api/v1/auth/dev-login" not in production_client.get("/openapi.json").text


def test_dev_login_route_is_registered_in_development() -> None:
    with _client(APP_ENV="development") as client:
        assert "/api/v1/auth/dev-login" in client.get("/openapi.json").json()["paths"]


@pytest.mark.parametrize("path", ["/api/v1/me", "/api/v1/scenarios"])
def test_missing_or_malformed_credentials_are_401(production_client: TestClient, path: str) -> None:
    for headers in ({}, {"Authorization": "Basic abc"}, {"Authorization": "Bearer"}):
        response = production_client.get(path, headers=headers)
        assert response.status_code == 401
        assert response.json() == UNAUTHORIZED
        assert response.headers["www-authenticate"] == "Bearer"


def test_dev_token_is_refused_in_production(production_client: TestClient) -> None:
    token = dev_token(supabase_claims(iss="agentops-dev"))
    response = production_client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert response.json() == UNAUTHORIZED
    assert token not in response.text


def test_invalid_token_response_is_uniform_and_leaks_nothing() -> None:
    other_key = KeyPair("k1", "RS256")
    with _client(APP_ENV="production") as client:
        for token in (
            "garbage",
            other_key.sign(supabase_claims()),
            other_key.sign(supabase_claims(exp=1)),
        ):
            response = client.get("/api/v1/me", headers={"Authorization": f"Bearer {token}"})
            assert response.status_code == 401
            assert response.json() == UNAUTHORIZED
            assert response.headers["www-authenticate"] == "Bearer"
            assert token not in response.text
