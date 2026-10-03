import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Incident, Profile
from app.repositories import IncidentEventRepository, IncidentRepository, ProfileRepository

BASE_TIME = datetime(2026, 1, 1, tzinfo=UTC)


async def _profile(session: AsyncSession) -> uuid.UUID:
    profile_id = uuid.uuid4()
    await ProfileRepository(session).create(profile_id, None, None, "operator")
    return profile_id


async def _incident(
    session: AsyncSession,
    owner_id: uuid.UUID,
    *,
    minutes: int = 0,
    public: bool = False,
    status: str | None = None,
    title: str = "incident",
) -> Incident:
    """Create an incident with created_at = BASE_TIME + minutes (now() is fixed per transaction)."""
    repo = IncidentRepository(session)
    incident = await repo.create(owner_id, "db-outage", title)
    values: dict[str, object] = {"created_at": BASE_TIME + timedelta(minutes=minutes)}
    if public:
        values["is_public"] = True
    if status:
        values["status"] = status
    await session.execute(update(Incident).where(Incident.id == incident.id).values(**values))
    await session.refresh(incident)
    return incident


async def test_create_applies_defaults(session: AsyncSession) -> None:
    owner = await _profile(session)
    incident = await IncidentRepository(session).create(
        owner, "db-outage", "Disk full", affected_services=["api", "db"]
    )
    assert incident.status == "open"
    assert incident.severity is None
    assert incident.is_public is False
    assert incident.affected_services == ["api", "db"]
    assert incident.deleted_at is None
    assert incident.created_at is not None
    assert incident.updated_at is not None


async def test_create_defaults_affected_services_to_empty(session: AsyncSession) -> None:
    owner = await _profile(session)
    incident = await IncidentRepository(session).create(owner, "db-outage", "t", severity="P2")
    assert incident.affected_services == []
    assert incident.severity == "P2"


async def test_create_rejects_invalid_title(session: AsyncSession) -> None:
    owner = await _profile(session)
    with pytest.raises(IntegrityError, match="ck_incidents_title_length"):
        await IncidentRepository(session).create(owner, "db-outage", "")


async def test_get_hides_soft_deleted_unless_requested(session: AsyncSession) -> None:
    owner = await _profile(session)
    repo = IncidentRepository(session)
    incident = await repo.create(owner, "db-outage", "t")

    assert (await repo.get(incident.id)) is not None
    await repo.soft_delete(incident.id)

    assert await repo.get(incident.id) is None
    deleted = await repo.get(incident.id, include_deleted=True)
    assert deleted is not None
    assert deleted.deleted_at is not None


async def test_get_unknown_id_returns_none(session: AsyncSession) -> None:
    assert await IncidentRepository(session).get(uuid.uuid4()) is None


class _Visibility:
    """Owner A: a_private, a_public. Owner B: b_private, b_public, b_deleted (public + deleted)."""

    def __init__(self) -> None:
        self.owner_a = uuid.uuid4()
        self.owner_b = uuid.uuid4()
        self.a_private: Incident
        self.a_public: Incident
        self.b_private: Incident
        self.b_public: Incident
        self.b_deleted: Incident


@pytest.fixture
async def visibility(session: AsyncSession) -> _Visibility:
    data = _Visibility()
    profiles = ProfileRepository(session)
    await profiles.create(data.owner_a, None, None, "operator")
    await profiles.create(data.owner_b, None, None, "operator")
    data.a_private = await _incident(session, data.owner_a, minutes=1)
    data.a_public = await _incident(session, data.owner_a, minutes=2, public=True)
    data.b_private = await _incident(session, data.owner_b, minutes=3)
    data.b_public = await _incident(session, data.owner_b, minutes=4, public=True)
    data.b_deleted = await _incident(session, data.owner_b, minutes=5, public=True)
    await IncidentRepository(session).soft_delete(data.b_deleted.id)
    return data


async def test_list_owner_only(session: AsyncSession, visibility: _Visibility) -> None:
    repo = IncidentRepository(session)
    result = await repo.list(owner_id=visibility.owner_a)
    assert [i.id for i in result] == [visibility.a_public.id, visibility.a_private.id]
    assert await repo.count(owner_id=visibility.owner_a) == 2


async def test_list_owner_plus_public(session: AsyncSession, visibility: _Visibility) -> None:
    repo = IncidentRepository(session)
    result = await repo.list(owner_id=visibility.owner_a, include_public=True)
    assert [i.id for i in result] == [
        visibility.b_public.id,
        visibility.a_public.id,
        visibility.a_private.id,
    ]
    assert await repo.count(owner_id=visibility.owner_a, include_public=True) == 3


async def test_list_public_only(session: AsyncSession, visibility: _Visibility) -> None:
    repo = IncidentRepository(session)
    result = await repo.list(include_public=True)
    assert [i.id for i in result] == [visibility.b_public.id, visibility.a_public.id]
    assert await repo.count(include_public=True) == 2


async def test_list_unrestricted_for_admin_excludes_soft_deleted(
    session: AsyncSession, visibility: _Visibility
) -> None:
    repo = IncidentRepository(session)
    result = await repo.list()
    assert [i.id for i in result] == [
        visibility.b_public.id,
        visibility.b_private.id,
        visibility.a_public.id,
        visibility.a_private.id,
    ]
    assert visibility.b_deleted.id not in {i.id for i in result}
    assert await repo.count() == 4


async def test_list_extra_filters(session: AsyncSession, visibility: _Visibility) -> None:
    repo = IncidentRepository(session)
    await session.execute(
        update(Incident).where(Incident.id == visibility.a_private.id).values(status="resolved")
    )

    resolved = await repo.list(status="resolved")
    assert [i.id for i in resolved] == [visibility.a_private.id]
    assert await repo.count(status="resolved") == 1

    private_only = await repo.list(owner_id=visibility.owner_a, is_public=False)
    assert [i.id for i in private_only] == [visibility.a_private.id]
    assert await repo.count(owner_id=visibility.owner_a, is_public=True) == 1


async def test_list_pagination_and_ordering(session: AsyncSession) -> None:
    owner = await _profile(session)
    repo = IncidentRepository(session)
    created = [await _incident(session, owner, minutes=m) for m in range(5)]
    expected = [i.id for i in reversed(created)]

    assert [i.id for i in await repo.list(limit=2)] == expected[:2]
    assert [i.id for i in await repo.list(limit=2, offset=2)] == expected[2:4]
    assert [i.id for i in await repo.list(limit=2, offset=4)] == expected[4:]
    assert await repo.list(limit=2, offset=5) == []
    assert await repo.count() == 5


async def test_list_breaks_created_at_ties_by_id_desc(session: AsyncSession) -> None:
    owner = await _profile(session)
    created = [await _incident(session, owner, minutes=0) for _ in range(4)]
    result = await IncidentRepository(session).list()
    assert [i.id for i in result] == sorted((i.id for i in created), reverse=True)


async def test_soft_delete_keeps_events_and_is_not_repeatable(session: AsyncSession) -> None:
    owner = await _profile(session)
    repo = IncidentRepository(session)
    incident = await repo.create(owner, "db-outage", "t")
    await IncidentEventRepository(session).append(incident.id, "created", "created")

    deleted = await repo.soft_delete(incident.id)

    assert deleted is not None
    assert deleted.deleted_at is not None
    assert await repo.soft_delete(incident.id) is None
    assert await repo.soft_delete(uuid.uuid4()) is None
    assert len(await IncidentEventRepository(session).list_for_incident(incident.id)) == 1


async def test_set_public_toggles_and_ignores_deleted(session: AsyncSession) -> None:
    owner = await _profile(session)
    repo = IncidentRepository(session)
    incident = await repo.create(owner, "db-outage", "t")

    made_public = await repo.set_public(incident.id, True)
    assert made_public is not None
    assert made_public.is_public is True
    made_private = await repo.set_public(incident.id, False)
    assert made_private is not None
    assert made_private.is_public is False

    await repo.soft_delete(incident.id)
    assert await repo.set_public(incident.id, True) is None
    assert await repo.set_public(uuid.uuid4(), True) is None


async def test_touch_updates_updated_at(session: AsyncSession) -> None:
    owner = await _profile(session)
    repo = IncidentRepository(session)
    incident = await repo.create(owner, "db-outage", "t")
    await session.execute(
        update(Incident).where(Incident.id == incident.id).values(updated_at=BASE_TIME)
    )

    touched = await repo.touch(incident.id)

    assert touched is not None
    assert touched.updated_at > BASE_TIME
    assert await repo.touch(uuid.uuid4()) is None


async def test_parameters_are_not_interpreted_as_sql(session: AsyncSession) -> None:
    owner = await _profile(session)
    repo = IncidentRepository(session)
    nasty = "x'); DROP TABLE incidents; --"
    incident = await repo.create(owner, "db-outage", nasty)

    fetched = await repo.get(incident.id)
    assert fetched is not None
    assert fetched.title == nasty
    assert await repo.list(status="open' OR '1'='1") == []
    assert (await session.execute(text("SELECT count(*) FROM incidents"))).scalar_one() == 1
    assert await session.get(Profile, owner) is not None
