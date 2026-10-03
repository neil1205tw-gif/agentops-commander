import asyncio
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.auth import TokenVerifier
from app.auth.dev import DEMO_ACCOUNTS
from app.db import create_session_factory, get_session
from app.main import create_app
from app.models import Incident, IncidentEvent
from app.repositories import IncidentEventRepository, IncidentRepository, ProfileRepository
from tests.auth_support import (
    FakeJWKSProvider,
    KeyPair,
    auth_settings,
    dev_token,
    supabase_claims,
)

KEY = KeyPair("rsa-1", "RS256")
CPU = "cpu_spike_after_deploy"
POOL = "db_pool_exhaustion"
STORM = "duplicate_alert_storm"
MISSING_ID = "00000000-0000-4000-8000-0000000000ff"


@dataclass(frozen=True)
class Actor:
    id: uuid.UUID
    headers: dict[str, str]


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _build_app(async_engine: AsyncEngine) -> FastAPI:
    settings = auth_settings()
    app = create_app(settings)
    # The lifespan does not run under ASGITransport; wire the state it would create.
    app.state.session_factory = create_session_factory(async_engine)
    app.state.token_verifier = TokenVerifier(settings, FakeJWKSProvider(KEY))
    return app


@pytest.fixture
async def app(async_engine: AsyncEngine) -> FastAPI:
    return _build_app(async_engine)


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        yield http


async def _demo(client: httpx.AsyncClient, role: str) -> Actor:
    response = await client.post("/api/v1/auth/dev-login", json={"role": role})
    assert response.status_code == 200
    return Actor(DEMO_ACCOUNTS[role].id, _bearer(response.json()["access_token"]))  # type: ignore[index]


@pytest.fixture
async def viewer(client: httpx.AsyncClient) -> Actor:
    return await _demo(client, "viewer")


@pytest.fixture
async def operator(client: httpx.AsyncClient) -> Actor:
    return await _demo(client, "operator")


@pytest.fixture
async def admin(client: httpx.AsyncClient) -> Actor:
    return await _demo(client, "admin")


@pytest.fixture
async def other_operator(client: httpx.AsyncClient, session: AsyncSession) -> Actor:
    sub = uuid.uuid4()
    await ProfileRepository(session).create(sub, f"{sub}@example.test", "Other", "operator")
    await session.commit()
    claims = supabase_claims(sub=str(sub), email=f"{sub}@example.test", iss="agentops-dev")
    return Actor(sub, _bearer(dev_token(claims)))


async def _create(
    client: httpx.AsyncClient, actor: Actor, scenario_key: str = CPU, **body: Any
) -> dict[str, Any]:
    response = await client.post(
        "/api/v1/incidents", json={"scenario_key": scenario_key, **body}, headers=actor.headers
    )
    assert response.status_code == 201, response.text
    created: dict[str, Any] = response.json()
    return created


async def _publish(client: httpx.AsyncClient, admin: Actor, incident_id: str) -> None:
    response = await client.patch(
        f"/api/v1/incidents/{incident_id}/visibility",
        json={"is_public": True},
        headers=admin.headers,
    )
    assert response.status_code == 200


async def _count(session: AsyncSession, model: type[Incident] | type[IncidentEvent]) -> int:
    return (await session.scalar(select(func.count()).select_from(model))) or 0


# --- authentication and role gates ---------------------------------------------------------


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("POST", "/api/v1/incidents", {"scenario_key": CPU}),
        ("GET", "/api/v1/incidents", None),
        ("GET", f"/api/v1/incidents/{MISSING_ID}", None),
        ("GET", f"/api/v1/incidents/{MISSING_ID}/events", None),
        ("DELETE", f"/api/v1/incidents/{MISSING_ID}", None),
        ("PATCH", f"/api/v1/incidents/{MISSING_ID}/visibility", {"is_public": True}),
    ],
)
async def test_every_endpoint_requires_a_token(
    client: httpx.AsyncClient, method: str, path: str, body: dict[str, Any] | None
) -> None:
    response = await client.request(method, path, json=body)
    assert response.status_code == 401
    bad = await client.request(method, path, json=body, headers=_bearer("garbage"))
    assert bad.status_code == 401


async def test_viewer_cannot_create(client: httpx.AsyncClient, viewer: Actor) -> None:
    response = await client.post(
        "/api/v1/incidents", json={"scenario_key": CPU}, headers=viewer.headers
    )
    assert response.status_code == 403
    assert response.json() == {"detail": "Insufficient role"}


async def test_viewer_gets_403_before_scenario_validation(
    client: httpx.AsyncClient, viewer: Actor
) -> None:
    response = await client.post(
        "/api/v1/incidents", json={"scenario_key": "nope"}, headers=viewer.headers
    )
    assert response.status_code == 403


@pytest.mark.parametrize("role", ["operator", "admin"])
async def test_operator_and_admin_can_create(
    client: httpx.AsyncClient, operator: Actor, admin: Actor, role: str
) -> None:
    actor = operator if role == "operator" else admin
    created = await _create(client, actor)
    assert created["owner_id"] == str(actor.id)


# --- create --------------------------------------------------------------------------------


async def test_create_uses_scenario_defaults(
    client: httpx.AsyncClient, operator: Actor, app: FastAPI
) -> None:
    created = await _create(client, operator, POOL)
    scenario = app.state.scenario_registry.get(POOL)
    assert uuid.UUID(created["id"])
    assert created["title"] == scenario.default_title
    assert created["scenario_key"] == POOL
    assert created["status"] == "open"
    assert created["severity"] is None
    assert created["is_public"] is False
    assert created["owner_id"] == str(operator.id)
    assert created["affected_services"] == scenario.affected_services
    assert created["resolved_at"] is None
    assert created["alert"] == scenario.alert.model_dump()
    assert created["created_at"] and created["updated_at"]


async def test_create_with_custom_title_strips_whitespace(
    client: httpx.AsyncClient, operator: Actor
) -> None:
    created = await _create(client, operator, title="  Checkout latency <b>alert</b>  ")
    assert created["title"] == "Checkout latency <b>alert</b>"


@pytest.mark.parametrize("title", [None, "", "   ", "\t\n"])
async def test_blank_or_missing_title_uses_default(
    client: httpx.AsyncClient, operator: Actor, app: FastAPI, title: str | None
) -> None:
    created = await _create(client, operator, title=title)
    assert created["title"] == app.state.scenario_registry.get(CPU).default_title


async def test_title_length_limits(client: httpx.AsyncClient, operator: Actor) -> None:
    assert (await _create(client, operator, title="x" * 200))["title"] == "x" * 200
    assert (await _create(client, operator, title=f"  {'y' * 200}  "))["title"] == "y" * 200
    response = await client.post(
        "/api/v1/incidents",
        json={"scenario_key": CPU, "title": "z" * 201},
        headers=operator.headers,
    )
    assert response.status_code == 422


async def test_title_with_nul_is_rejected(client: httpx.AsyncClient, operator: Actor) -> None:
    response = await client.post(
        "/api/v1/incidents",
        json={"scenario_key": CPU, "title": "bad\u0000title"},
        headers=operator.headers,
    )
    assert response.status_code == 422


@pytest.mark.parametrize(
    "body",
    [
        {"scenario_key": "not_a_scenario"},
        {"scenario_key": ""},
        {},
        {"scenario_key": 5},
        {"scenario_key": CPU, "title": 5},
    ],
)
async def test_invalid_create_body_is_422(
    client: httpx.AsyncClient, operator: Actor, session: AsyncSession, body: dict[str, Any]
) -> None:
    response = await client.post("/api/v1/incidents", json=body, headers=operator.headers)
    assert response.status_code == 422
    assert await _count(session, Incident) == 0
    assert await _count(session, IncidentEvent) == 0


async def test_create_writes_a_created_event(
    client: httpx.AsyncClient, operator: Actor, session: AsyncSession
) -> None:
    created = await _create(client, operator, STORM)
    events = (await session.scalars(select(IncidentEvent))).all()
    assert len(events) == 1
    event = events[0]
    assert str(event.incident_id) == created["id"]
    assert event.event_type == "incident.created"
    assert event.agent_name is None
    assert event.summary == f"Incident created from scenario {STORM}"
    assert event.payload == {"scenario_key": STORM, "created_by": str(operator.id)}


async def test_title_is_stored_verbatim_and_never_interpolated(
    client: httpx.AsyncClient, operator: Actor, session: AsyncSession
) -> None:
    title = "x'); DROP TABLE incidents; -- %s {0} <script>alert(1)</script>"
    created = await _create(client, operator, title=title)
    stored = await session.scalar(
        select(Incident.title).where(Incident.id == uuid.UUID(created["id"]))
    )
    assert stored == title
    fetched = await client.get(f"/api/v1/incidents/{created['id']}", headers=operator.headers)
    assert fetched.json()["title"] == title


# --- get and events ------------------------------------------------------------------------


async def test_get_returns_detail_with_alert(
    client: httpx.AsyncClient, operator: Actor, app: FastAPI
) -> None:
    created = await _create(client, operator)
    response = await client.get(f"/api/v1/incidents/{created['id']}", headers=operator.headers)
    assert response.status_code == 200
    assert response.json() == created
    assert response.json()["alert"] == app.state.scenario_registry.get(CPU).alert.model_dump()


async def test_get_has_null_alert_when_the_scenario_is_gone(
    client: httpx.AsyncClient, operator: Actor, session: AsyncSession
) -> None:
    created = await _create(client, operator)
    await session.execute(
        update(Incident)
        .where(Incident.id == uuid.UUID(created["id"]))
        .values(scenario_key="retired_scenario")
    )
    await session.commit()
    response = await client.get(f"/api/v1/incidents/{created['id']}", headers=operator.headers)
    assert response.status_code == 200
    assert response.json()["alert"] is None
    assert response.json()["scenario_key"] == "retired_scenario"


async def test_get_rejects_a_non_uuid_id(client: httpx.AsyncClient, operator: Actor) -> None:
    for path in ("not-a-uuid", "not-a-uuid/events"):
        response = await client.get(f"/api/v1/incidents/{path}", headers=operator.headers)
        assert response.status_code == 422
    response = await client.delete("/api/v1/incidents/not-a-uuid", headers=operator.headers)
    assert response.status_code == 422


async def test_events_are_listed_in_order(
    client: httpx.AsyncClient, operator: Actor, admin: Actor
) -> None:
    created = await _create(client, operator)
    await _publish(client, admin, created["id"])
    response = await client.get(
        f"/api/v1/incidents/{created['id']}/events", headers=operator.headers
    )
    assert response.status_code == 200
    items = response.json()["items"]
    assert [item["event_type"] for item in items] == [
        "incident.created",
        "incident.visibility_changed",
    ]
    assert set(items[0]) == {"id", "event_type", "agent_name", "summary", "payload", "created_at"}
    assert items[0]["payload"]["scenario_key"] == CPU


async def test_events_of_a_missing_incident_are_404(
    client: httpx.AsyncClient, operator: Actor
) -> None:
    response = await client.get(f"/api/v1/incidents/{MISSING_ID}/events", headers=operator.headers)
    assert response.status_code == 404


# --- visibility ----------------------------------------------------------------------------


async def test_viewer_cannot_see_private_incidents(
    client: httpx.AsyncClient, operator: Actor, viewer: Actor
) -> None:
    created = await _create(client, operator)
    listing = await client.get("/api/v1/incidents", headers=viewer.headers)
    assert listing.status_code == 200
    assert listing.json() == {"items": [], "total": 0, "limit": 20, "offset": 0}
    for suffix in ("", "/events"):
        response = await client.get(
            f"/api/v1/incidents/{created['id']}{suffix}", headers=viewer.headers
        )
        assert response.status_code == 404
        assert response.json() == {"detail": "Incident not found"}
    missing = await client.get(f"/api/v1/incidents/{MISSING_ID}", headers=viewer.headers)
    assert missing.status_code == 404
    assert missing.json() == response.json()


async def test_operator_sees_own_and_public_but_not_other_private(
    client: httpx.AsyncClient, operator: Actor, other_operator: Actor, admin: Actor
) -> None:
    mine = await _create(client, operator)
    theirs_private = await _create(client, other_operator, POOL)
    theirs_public = await _create(client, other_operator, STORM)
    await _publish(client, admin, theirs_public["id"])

    listing = await client.get("/api/v1/incidents", headers=operator.headers)
    assert {item["id"] for item in listing.json()["items"]} == {mine["id"], theirs_public["id"]}
    assert listing.json()["total"] == 2

    for visible in (mine, theirs_public):
        response = await client.get(f"/api/v1/incidents/{visible['id']}", headers=operator.headers)
        assert response.status_code == 200
    hidden = await client.get(f"/api/v1/incidents/{theirs_private['id']}", headers=operator.headers)
    assert hidden.status_code == 404
    hidden_events = await client.get(
        f"/api/v1/incidents/{theirs_private['id']}/events", headers=operator.headers
    )
    assert hidden_events.status_code == 404


async def test_admin_sees_everything(
    client: httpx.AsyncClient, operator: Actor, other_operator: Actor, admin: Actor
) -> None:
    first = await _create(client, operator)
    second = await _create(client, other_operator, POOL)
    listing = await client.get("/api/v1/incidents", headers=admin.headers)
    assert {item["id"] for item in listing.json()["items"]} == {first["id"], second["id"]}
    for incident in (first, second):
        response = await client.get(f"/api/v1/incidents/{incident['id']}", headers=admin.headers)
        assert response.status_code == 200
        events = await client.get(
            f"/api/v1/incidents/{incident['id']}/events", headers=admin.headers
        )
        assert events.status_code == 200


async def test_soft_deleted_incidents_are_invisible_to_everyone(
    client: httpx.AsyncClient, operator: Actor, admin: Actor, viewer: Actor
) -> None:
    created = await _create(client, operator)
    await _publish(client, admin, created["id"])
    assert (
        await client.get(f"/api/v1/incidents/{created['id']}", headers=viewer.headers)
    ).status_code == 200
    assert (
        await client.delete(f"/api/v1/incidents/{created['id']}", headers=operator.headers)
    ).status_code == 204
    for actor in (viewer, operator, admin):
        listing = await client.get("/api/v1/incidents", headers=actor.headers)
        assert listing.json()["items"] == []
        assert listing.json()["total"] == 0
        for suffix in ("", "/events"):
            response = await client.get(
                f"/api/v1/incidents/{created['id']}{suffix}", headers=actor.headers
            )
            assert response.status_code == 404


# --- list: pagination, ordering, status ----------------------------------------------------


async def test_pagination_and_ordering(client: httpx.AsyncClient, operator: Actor) -> None:
    ids = [(await _create(client, operator))["id"] for _ in range(5)]
    first = await client.get("/api/v1/incidents?limit=2", headers=operator.headers)
    assert first.status_code == 200
    body = first.json()
    assert (body["total"], body["limit"], body["offset"]) == (5, 2, 0)
    assert [item["id"] for item in body["items"]] == ids[::-1][:2]
    assert set(body["items"][0]) == {
        "id",
        "title",
        "scenario_key",
        "severity",
        "status",
        "affected_services",
        "is_public",
        "owner_id",
        "created_at",
        "updated_at",
    }
    second = await client.get("/api/v1/incidents?limit=2&offset=2", headers=operator.headers)
    assert [item["id"] for item in second.json()["items"]] == ids[::-1][2:4]
    last = await client.get("/api/v1/incidents?limit=2&offset=4", headers=operator.headers)
    assert [item["id"] for item in last.json()["items"]] == ids[::-1][4:]
    beyond = await client.get("/api/v1/incidents?offset=50", headers=operator.headers)
    assert beyond.json() == {"items": [], "total": 5, "limit": 20, "offset": 50}


async def test_ordering_is_stable_when_created_at_ties(
    client: httpx.AsyncClient, operator: Actor, session: AsyncSession
) -> None:
    repository = IncidentRepository(session)
    for _ in range(5):
        await repository.create(operator.id, CPU, "tie", ["checkout-api"])
    await session.execute(update(Incident).values(created_at=func.now()))
    await session.commit()
    ordered = sorted((await session.scalars(select(Incident.id))).all(), reverse=True)

    pages: list[uuid.UUID] = []
    for offset in (0, 2, 4):
        response = await client.get(
            f"/api/v1/incidents?limit=2&offset={offset}", headers=operator.headers
        )
        pages.extend(uuid.UUID(item["id"]) for item in response.json()["items"])
    assert pages == ordered


@pytest.mark.parametrize(
    "query",
    ["limit=0", "limit=101", "limit=-1", "limit=abc", "offset=-1", "offset=x", "status=bogus"],
)
async def test_invalid_list_parameters_are_422(
    client: httpx.AsyncClient, operator: Actor, query: str
) -> None:
    response = await client.get(f"/api/v1/incidents?{query}", headers=operator.headers)
    assert response.status_code == 422


async def test_limit_bounds_are_accepted(client: httpx.AsyncClient, operator: Actor) -> None:
    for limit in (1, 100):
        response = await client.get(f"/api/v1/incidents?limit={limit}", headers=operator.headers)
        assert response.status_code == 200
        assert response.json()["limit"] == limit


async def test_status_filter(
    client: httpx.AsyncClient, operator: Actor, session: AsyncSession
) -> None:
    opened = await _create(client, operator)
    resolved = await _create(client, operator, POOL)
    await session.execute(
        update(Incident).where(Incident.id == uuid.UUID(resolved["id"])).values(status="resolved")
    )
    await session.commit()

    only_open = await client.get("/api/v1/incidents?status=open", headers=operator.headers)
    assert [item["id"] for item in only_open.json()["items"]] == [opened["id"]]
    assert only_open.json()["total"] == 1
    only_resolved = await client.get("/api/v1/incidents?status=resolved", headers=operator.headers)
    assert [item["id"] for item in only_resolved.json()["items"]] == [resolved["id"]]
    none = await client.get("/api/v1/incidents?status=failed", headers=operator.headers)
    assert none.json()["items"] == []
    assert none.json()["total"] == 0
    everything = await client.get("/api/v1/incidents", headers=operator.headers)
    assert everything.json()["total"] == 2


# --- delete --------------------------------------------------------------------------------


async def test_owner_can_delete_and_events_are_kept(
    client: httpx.AsyncClient, operator: Actor, session: AsyncSession
) -> None:
    created = await _create(client, operator)
    response = await client.delete(f"/api/v1/incidents/{created['id']}", headers=operator.headers)
    assert response.status_code == 204
    assert response.content == b""

    incident = await session.scalar(select(Incident).where(Incident.id == uuid.UUID(created["id"])))
    assert incident is not None
    assert incident.deleted_at is not None
    events = await IncidentEventRepository(session).list_for_incident(uuid.UUID(created["id"]))
    assert [event.event_type for event in events] == ["incident.created", "incident.deleted"]
    assert events[1].payload == {"deleted_by": str(operator.id)}
    assert events[1].summary == "Incident deleted"

    again = await client.delete(f"/api/v1/incidents/{created['id']}", headers=operator.headers)
    assert again.status_code == 404
    assert await _count(session, IncidentEvent) == 2


async def test_admin_can_delete_anyones_incident(
    client: httpx.AsyncClient, operator: Actor, admin: Actor
) -> None:
    created = await _create(client, operator)
    response = await client.delete(f"/api/v1/incidents/{created['id']}", headers=admin.headers)
    assert response.status_code == 204
    assert (
        await client.get(f"/api/v1/incidents/{created['id']}", headers=operator.headers)
    ).status_code == 404


async def test_operator_deleting_someone_elses_incident(
    client: httpx.AsyncClient, operator: Actor, other_operator: Actor, admin: Actor
) -> None:
    private = await _create(client, other_operator)
    public = await _create(client, other_operator, POOL)
    await _publish(client, admin, public["id"])

    # Not visible -> 404 (existence is not revealed); visible but not owned -> 403.
    hidden = await client.delete(f"/api/v1/incidents/{private['id']}", headers=operator.headers)
    assert hidden.status_code == 404
    visible = await client.delete(f"/api/v1/incidents/{public['id']}", headers=operator.headers)
    assert visible.status_code == 403
    for incident in (private, public):
        still_there = await client.get(
            f"/api/v1/incidents/{incident['id']}", headers=other_operator.headers
        )
        assert still_there.status_code == 200


async def test_viewer_delete_is_always_403(
    client: httpx.AsyncClient, operator: Actor, admin: Actor, viewer: Actor
) -> None:
    private = await _create(client, operator)
    public = await _create(client, operator, POOL)
    await _publish(client, admin, public["id"])
    for target in (private["id"], public["id"], MISSING_ID):
        response = await client.delete(f"/api/v1/incidents/{target}", headers=viewer.headers)
        assert response.status_code == 403
    assert (
        await client.get(f"/api/v1/incidents/{public['id']}", headers=operator.headers)
    ).status_code == 200


async def test_deleting_a_missing_incident_is_404(
    client: httpx.AsyncClient, operator: Actor, admin: Actor
) -> None:
    for actor in (operator, admin):
        response = await client.delete(f"/api/v1/incidents/{MISSING_ID}", headers=actor.headers)
        assert response.status_code == 404


async def test_delete_of_an_incident_removed_concurrently_is_404(
    client: httpx.AsyncClient,
    operator: Actor,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created = await _create(client, operator)

    async def lost_race(self: IncidentRepository, incident_id: uuid.UUID) -> None:
        return None

    monkeypatch.setattr(IncidentRepository, "soft_delete", lost_race)
    response = await client.delete(f"/api/v1/incidents/{created['id']}", headers=operator.headers)
    assert response.status_code == 404


# --- visibility patch ----------------------------------------------------------------------


async def test_only_admin_can_change_visibility(
    client: httpx.AsyncClient, operator: Actor, other_operator: Actor, viewer: Actor
) -> None:
    created = await _create(client, operator)
    url = f"/api/v1/incidents/{created['id']}/visibility"
    for actor in (operator, other_operator, viewer):
        response = await client.patch(url, json={"is_public": True}, headers=actor.headers)
        assert response.status_code == 403
        missing = await client.patch(
            f"/api/v1/incidents/{MISSING_ID}/visibility",
            json={"is_public": True},
            headers=actor.headers,
        )
        assert missing.status_code == 403
    fetched = await client.get(f"/api/v1/incidents/{created['id']}", headers=operator.headers)
    assert fetched.json()["is_public"] is False


async def test_admin_visibility_change_is_audited_and_toggles_viewer_access(
    client: httpx.AsyncClient,
    operator: Actor,
    admin: Actor,
    viewer: Actor,
    session: AsyncSession,
) -> None:
    created = await _create(client, operator)
    url = f"/api/v1/incidents/{created['id']}"
    assert (await client.get(url, headers=viewer.headers)).status_code == 404

    response = await client.patch(
        f"{url}/visibility", json={"is_public": True}, headers=admin.headers
    )
    assert response.status_code == 200
    body = response.json()
    assert body["is_public"] is True
    assert body["id"] == created["id"]
    assert body["alert"] == created["alert"]
    assert body["updated_at"] >= created["updated_at"]
    assert (await client.get(url, headers=viewer.headers)).status_code == 200
    listing = await client.get("/api/v1/incidents", headers=viewer.headers)
    assert [item["id"] for item in listing.json()["items"]] == [created["id"]]

    back = await client.patch(f"{url}/visibility", json={"is_public": False}, headers=admin.headers)
    assert back.json()["is_public"] is False
    assert (await client.get(url, headers=viewer.headers)).status_code == 404

    events = await IncidentEventRepository(session).list_for_incident(uuid.UUID(created["id"]))
    changes = [event for event in events if event.event_type == "incident.visibility_changed"]
    assert [event.payload for event in changes] == [
        {"old_is_public": False, "new_is_public": True, "changed_by": str(admin.id)},
        {"old_is_public": True, "new_is_public": False, "changed_by": str(admin.id)},
    ]
    assert changes[0].summary == "Incident visibility changed to public"
    assert changes[1].summary == "Incident visibility changed to private"


async def test_visibility_patch_validation_and_404(
    client: httpx.AsyncClient, operator: Actor, admin: Actor
) -> None:
    created = await _create(client, operator)
    url = f"/api/v1/incidents/{created['id']}/visibility"
    assert (await client.patch(url, json={}, headers=admin.headers)).status_code == 422
    assert (
        await client.patch(url, json={"is_public": "maybe"}, headers=admin.headers)
    ).status_code == 422
    missing = await client.patch(
        f"/api/v1/incidents/{MISSING_ID}/visibility",
        json={"is_public": True},
        headers=admin.headers,
    )
    assert missing.status_code == 404
    await client.delete(f"/api/v1/incidents/{created['id']}", headers=operator.headers)
    gone = await client.patch(url, json={"is_public": True}, headers=admin.headers)
    assert gone.status_code == 404


async def test_visibility_patch_of_an_incident_removed_concurrently_is_404(
    client: httpx.AsyncClient,
    operator: Actor,
    admin: Actor,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created = await _create(client, operator)

    async def lost_race(self: IncidentRepository, incident_id: uuid.UUID, is_public: bool) -> None:
        return None

    monkeypatch.setattr(IncidentRepository, "set_public", lost_race)
    response = await client.patch(
        f"/api/v1/incidents/{created['id']}/visibility",
        json={"is_public": True},
        headers=admin.headers,
    )
    assert response.status_code == 404


# --- transaction consistency ---------------------------------------------------------------


async def _failing_append(*_args: Any, **_kwargs: Any) -> IncidentEvent:
    raise RuntimeError("event store unavailable")


async def test_incident_is_not_left_behind_when_the_created_event_fails(
    client: httpx.AsyncClient,
    operator: Actor,
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(IncidentEventRepository, "append", _failing_append)
    response = await client.post(
        "/api/v1/incidents", json={"scenario_key": CPU}, headers=operator.headers
    )
    assert response.status_code == 500
    assert await _count(session, Incident) == 0
    assert await _count(session, IncidentEvent) == 0


async def test_incident_is_not_deleted_when_the_deleted_event_fails(
    client: httpx.AsyncClient,
    operator: Actor,
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created = await _create(client, operator)
    monkeypatch.setattr(IncidentEventRepository, "append", _failing_append)
    response = await client.delete(f"/api/v1/incidents/{created['id']}", headers=operator.headers)
    assert response.status_code == 500
    incident = await session.scalar(select(Incident).where(Incident.id == uuid.UUID(created["id"])))
    assert incident is not None
    assert incident.deleted_at is None
    monkeypatch.undo()
    assert (
        await client.get(f"/api/v1/incidents/{created['id']}", headers=operator.headers)
    ).status_code == 200


async def test_visibility_is_unchanged_when_the_event_fails(
    client: httpx.AsyncClient,
    operator: Actor,
    admin: Actor,
    session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created = await _create(client, operator)
    monkeypatch.setattr(IncidentEventRepository, "append", _failing_append)
    response = await client.patch(
        f"/api/v1/incidents/{created['id']}/visibility",
        json={"is_public": True},
        headers=admin.headers,
    )
    assert response.status_code == 500
    incident = await session.scalar(select(Incident).where(Incident.id == uuid.UUID(created["id"])))
    assert incident is not None
    assert incident.is_public is False


async def test_writes_are_committed_before_the_response_is_sent(
    app: FastAPI,
    client: httpx.AsyncClient,
    operator: Actor,
    admin: Actor,
    session: AsyncSession,
) -> None:
    """The request-scoped dependency commits only after the response; make that a no-op here.

    The data must still be durable, which proves each write endpoint commits by itself.
    """
    factory = app.state.session_factory

    async def session_without_final_commit() -> AsyncIterator[AsyncSession]:
        async with factory() as db_session:
            yield db_session
            await db_session.rollback()

    app.dependency_overrides[get_session] = session_without_final_commit

    created = await _create(client, operator)
    incident_id = uuid.UUID(created["id"])
    assert await _count(session, Incident) == 1
    assert await _count(session, IncidentEvent) == 1

    patched = await client.patch(
        f"/api/v1/incidents/{created['id']}/visibility",
        json={"is_public": True},
        headers=admin.headers,
    )
    assert patched.status_code == 200
    await session.rollback()
    assert (
        await session.scalar(select(Incident.is_public).where(Incident.id == incident_id)) is True
    )
    assert await _count(session, IncidentEvent) == 2

    deleted = await client.delete(f"/api/v1/incidents/{created['id']}", headers=operator.headers)
    assert deleted.status_code == 204
    await session.rollback()
    assert (
        await session.scalar(select(Incident.deleted_at).where(Incident.id == incident_id))
    ) is not None
    assert await _count(session, IncidentEvent) == 3


async def test_concurrent_creates_all_land_with_their_events(
    client: httpx.AsyncClient, operator: Actor, session: AsyncSession
) -> None:
    responses = await asyncio.gather(
        *(
            client.post("/api/v1/incidents", json={"scenario_key": CPU}, headers=operator.headers)
            for _ in range(6)
        )
    )
    assert [r.status_code for r in responses] == [201] * 6
    assert await _count(session, Incident) == 6
    assert await _count(session, IncidentEvent) == 6
