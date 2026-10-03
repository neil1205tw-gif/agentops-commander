import asyncio
import uuid
from collections.abc import AsyncIterator
from typing import Annotated, Any

import httpx
import jwt
import pytest
from fastapi import Depends, FastAPI
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.auth import CurrentUser, TokenVerifier, require_role
from app.auth.dev import DEMO_ACCOUNTS
from app.db import create_session_factory
from app.main import create_app
from app.models import Profile
from app.repositories import ProfileRepository
from tests.auth_support import (
    DEV_SECRET,
    FakeJWKSProvider,
    KeyPair,
    auth_settings,
    dev_token,
    supabase_claims,
)

KEY = KeyPair("rsa-1", "RS256")


def _build_app(async_engine: AsyncEngine, **settings: Any) -> FastAPI:
    resolved = auth_settings(**settings)
    app = create_app(resolved)
    # The lifespan does not run under ASGITransport; wire the state it would create.
    app.state.session_factory = create_session_factory(async_engine)
    app.state.token_verifier = TokenVerifier(resolved, FakeJWKSProvider(KEY))
    return app


def _http(app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


@pytest.fixture
async def app(async_engine: AsyncEngine) -> FastAPI:
    return _build_app(async_engine)


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    async with _http(app) as http:
        yield http


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _dev_login(client: httpx.AsyncClient, role: str) -> dict[str, Any]:
    response = await client.post("/api/v1/auth/dev-login", json={"role": role})
    assert response.status_code == 200
    body: dict[str, Any] = response.json()
    return body


# --- dev-login ---------------------------------------------------------------------------


@pytest.mark.parametrize("role", ["viewer", "operator", "admin"])
async def test_dev_login_issues_a_token_for_the_demo_account(
    client: httpx.AsyncClient, session: AsyncSession, role: str
) -> None:
    body = await _dev_login(client, role)
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 28800
    claims = jwt.decode(
        body["access_token"], DEV_SECRET, algorithms=["HS256"], audience="authenticated"
    )
    account = DEMO_ACCOUNTS[role]  # type: ignore[index]
    assert claims["sub"] == str(account.id)
    assert claims["email"] == account.email
    assert claims["iss"] == "agentops-dev"
    assert claims["exp"] - claims["iat"] == 28800
    assert "role" not in claims
    profile = await session.get(Profile, account.id)
    assert profile is not None
    assert profile.role == role


async def test_dev_login_rejects_unknown_role(client: httpx.AsyncClient) -> None:
    response = await client.post("/api/v1/auth/dev-login", json={"role": "root"})
    assert response.status_code == 422


async def test_dev_login_resets_a_changed_demo_role(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    await _dev_login(client, "operator")
    await ProfileRepository(session).set_role(DEMO_ACCOUNTS["operator"].id, "viewer")
    await session.commit()
    token = (await _dev_login(client, "operator"))["access_token"]
    me = await client.get("/api/v1/me", headers=_bearer(token))
    assert me.json()["role"] == "operator"


async def test_dev_login_is_unavailable_in_production(async_engine: AsyncEngine) -> None:
    async with _http(_build_app(async_engine, APP_ENV="production")) as http:
        response = await http.post("/api/v1/auth/dev-login", json={"role": "admin"})
    assert response.status_code == 404


# --- /me and /scenarios ------------------------------------------------------------------


async def test_me_returns_the_logged_in_demo_user(client: httpx.AsyncClient) -> None:
    token = (await _dev_login(client, "operator"))["access_token"]
    response = await client.get("/api/v1/me", headers=_bearer(token))
    assert response.status_code == 200
    assert response.json() == {
        "id": str(DEMO_ACCOUNTS["operator"].id),
        "email": "demo-operator@agentops.local",
        "display_name": "Demo Operator",
        "role": "operator",
    }


async def test_me_and_scenarios_require_a_token(client: httpx.AsyncClient) -> None:
    assert (await client.get("/api/v1/me")).status_code == 401
    assert (await client.get("/api/v1/scenarios")).status_code == 401


@pytest.mark.parametrize("role", ["viewer", "operator", "admin"])
async def test_scenarios_are_listed_for_every_role(client: httpx.AsyncClient, role: str) -> None:
    token = (await _dev_login(client, role))["access_token"]
    response = await client.get("/api/v1/scenarios", headers=_bearer(token))
    assert response.status_code == 200
    scenarios = response.json()
    assert {s["key"] for s in scenarios} == {
        "cpu_spike_after_deploy",
        "db_pool_exhaustion",
        "duplicate_alert_storm",
    }
    assert set(scenarios[0]) == {
        "key",
        "name",
        "description",
        "default_title",
        "affected_services",
        "alert",
    }


# --- get_current_user --------------------------------------------------------------------


async def test_first_login_creates_a_viewer_profile(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    sub = uuid.uuid4()
    token = KEY.sign(supabase_claims(sub=str(sub), email="New.User@example.test"))
    response = await client.get("/api/v1/me", headers=_bearer(token))
    assert response.status_code == 200
    assert response.json() == {
        "id": str(sub),
        "email": "New.User@example.test",
        "display_name": None,
        "role": "viewer",
    }
    profile = await session.get(Profile, sub)
    assert profile is not None
    assert profile.role == "viewer"
    assert profile.display_name is None


async def test_role_claims_in_the_token_are_ignored(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    sub = uuid.uuid4()
    claims = supabase_claims(sub=str(sub), role="admin", app_metadata={"role": "admin"})
    response = await client.get("/api/v1/me", headers=_bearer(KEY.sign(claims)))
    assert response.json()["role"] == "viewer"
    # An existing operator stays operator even when the token says viewer.
    await ProfileRepository(session).set_role(sub, "operator")
    await session.commit()
    claims = supabase_claims(sub=str(sub), role="viewer")
    response = await client.get("/api/v1/me", headers=_bearer(KEY.sign(claims)))
    assert response.json()["role"] == "operator"


async def test_concurrent_first_logins_create_one_profile(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    sub = uuid.uuid4()
    token = KEY.sign(supabase_claims(sub=str(sub), email="race@example.test"))
    responses = await asyncio.gather(
        *(client.get("/api/v1/me", headers=_bearer(token)) for _ in range(8))
    )
    assert [r.status_code for r in responses] == [200] * 8
    assert {r.json()["id"] for r in responses} == {str(sub)}
    count = await session.scalar(select(func.count()).select_from(Profile))
    assert count == 1


async def test_email_already_used_by_another_profile_still_logs_in(
    client: httpx.AsyncClient, session: AsyncSession
) -> None:
    await ProfileRepository(session).create(uuid.uuid4(), "taken@example.test", None)
    await session.commit()
    token = KEY.sign(supabase_claims(email="TAKEN@example.test"))
    response = await client.get("/api/v1/me", headers=_bearer(token))
    assert response.status_code == 200
    assert response.json()["email"] is None
    assert response.json()["role"] == "viewer"


async def test_dev_token_for_unknown_user_creates_a_viewer(client: httpx.AsyncClient) -> None:
    token = dev_token(supabase_claims(iss="agentops-dev"))
    response = await client.get("/api/v1/me", headers=_bearer(token))
    assert response.status_code == 200
    assert response.json()["role"] == "viewer"


async def test_dev_token_is_refused_when_dev_auth_is_disabled(async_engine: AsyncEngine) -> None:
    token = dev_token(supabase_claims(iss="agentops-dev"))
    async with _http(_build_app(async_engine, APP_ENV="production")) as http:
        response = await http.get("/api/v1/me", headers=_bearer(token))
    assert response.status_code == 401


# --- require_role ------------------------------------------------------------------------


def _with_role_routes(app: FastAPI) -> FastAPI:
    @app.get("/t/viewer")
    async def viewer(user: Annotated[CurrentUser, Depends(require_role("viewer"))]) -> str:
        return user.role

    @app.get("/t/operator")
    async def operator(user: Annotated[CurrentUser, Depends(require_role("operator"))]) -> str:
        return user.role

    @app.get("/t/admin")
    async def admin(user: Annotated[CurrentUser, Depends(require_role("admin"))]) -> str:
        return user.role

    @app.get("/t/either")
    async def either(
        user: Annotated[CurrentUser, Depends(require_role("admin", "operator"))],
    ) -> str:
        return user.role

    return app


@pytest.mark.parametrize(
    ("role", "allowed"),
    [
        ("viewer", {"viewer"}),
        ("operator", {"viewer", "operator", "either"}),
        ("admin", {"viewer", "operator", "admin", "either"}),
    ],
)
async def test_role_hierarchy(app: FastAPI, role: str, allowed: set[str]) -> None:
    async with _http(_with_role_routes(app)) as http:
        token = (await _dev_login(http, role))["access_token"]
        for name in ("viewer", "operator", "admin", "either"):
            response = await http.get(f"/t/{name}", headers=_bearer(token))
            if name in allowed:
                assert response.status_code == 200, name
                assert response.json() == role
            else:
                assert response.status_code == 403, name
                assert response.json() == {"detail": "Insufficient role"}


async def test_require_role_distinguishes_401_from_403(app: FastAPI) -> None:
    async with _http(_with_role_routes(app)) as http:
        assert (await http.get("/t/admin")).status_code == 401
        assert (await http.get("/t/admin", headers=_bearer("garbage"))).status_code == 401
        viewer = (await _dev_login(http, "viewer"))["access_token"]
        assert (await http.get("/t/admin", headers=_bearer(viewer))).status_code == 403


@pytest.mark.parametrize("roles", [(), ("root",)])
def test_require_role_rejects_bad_arguments(roles: tuple[str, ...]) -> None:
    with pytest.raises(ValueError):
        require_role(*roles)  # type: ignore[arg-type]
