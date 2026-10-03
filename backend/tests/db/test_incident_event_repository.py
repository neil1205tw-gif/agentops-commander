import uuid

import pytest
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories import IncidentEventRepository, IncidentRepository, ProfileRepository


async def _incident_id(session: AsyncSession) -> uuid.UUID:
    owner = uuid.uuid4()
    await ProfileRepository(session).create(owner, None, None, "operator")
    incident = await IncidentRepository(session).create(owner, "db-outage", "t")
    return incident.id


async def test_append_returns_event_with_defaults(session: AsyncSession) -> None:
    incident_id = await _incident_id(session)
    event = await IncidentEventRepository(session).append(
        incident_id, "created", "Incident created"
    )
    assert event.id is not None
    assert event.created_at is not None
    assert event.agent_name is None
    assert event.payload == {}


async def test_append_stores_agent_name_and_payload(session: AsyncSession) -> None:
    incident_id = await _incident_id(session)
    payload = {"step": 1, "nested": {"ok": True}, "items": ["a", "b"]}
    repo = IncidentEventRepository(session)
    await repo.append(incident_id, "triage", "Triaged", agent_name="triage", payload=payload)

    (stored,) = await repo.list_for_incident(incident_id)
    assert stored.agent_name == "triage"
    assert stored.payload == payload


async def test_list_returns_append_order_within_one_transaction(session: AsyncSession) -> None:
    incident_id = await _incident_id(session)
    repo = IncidentEventRepository(session)
    summaries = [f"event {n}" for n in range(8)]
    for summary in summaries:
        await repo.append(incident_id, "note", summary)

    events = await repo.list_for_incident(incident_id)

    assert [e.summary for e in events] == summaries


async def test_list_is_scoped_to_incident(session: AsyncSession) -> None:
    first = await _incident_id(session)
    second = await _incident_id(session)
    repo = IncidentEventRepository(session)
    await repo.append(first, "note", "first")
    await repo.append(second, "note", "second")

    assert [e.summary for e in await repo.list_for_incident(first)] == ["first"]
    assert await repo.list_for_incident(uuid.uuid4()) == []


async def test_append_requires_existing_incident(session: AsyncSession) -> None:
    with pytest.raises(IntegrityError, match="incident_events_incident_id_fkey"):
        await IncidentEventRepository(session).append(uuid.uuid4(), "note", "orphan")


def test_repository_has_no_update_or_delete_methods() -> None:
    public = {name for name in dir(IncidentEventRepository) if not name.startswith("_")}
    assert public == {"append", "list_for_incident"}


async def test_stored_event_cannot_be_modified(session: AsyncSession) -> None:
    incident_id = await _incident_id(session)
    event = await IncidentEventRepository(session).append(incident_id, "note", "original")
    event.summary = "changed"
    with pytest.raises(DBAPIError, match="append-only"):
        await session.flush()
