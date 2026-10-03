import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Profile
from app.repositories import ProfileRepository


async def test_create_and_get(session: AsyncSession) -> None:
    repo = ProfileRepository(session)
    profile_id = uuid.uuid4()
    created = await repo.create(profile_id, "a@example.com", "Alice", "operator")
    assert created.role == "operator"
    assert created.created_at is not None

    fetched = await repo.get(profile_id)
    assert fetched is not None
    assert (fetched.email, fetched.display_name, fetched.role) == (
        "a@example.com",
        "Alice",
        "operator",
    )


async def test_create_defaults_to_viewer_and_allows_null_email(session: AsyncSession) -> None:
    repo = ProfileRepository(session)
    created = await repo.create(uuid.uuid4(), None, None)
    assert created.role == "viewer"
    assert created.email is None


async def test_get_returns_none_for_unknown_id(session: AsyncSession) -> None:
    assert await ProfileRepository(session).get(uuid.uuid4()) is None


async def test_get_by_email_is_case_insensitive(session: AsyncSession) -> None:
    repo = ProfileRepository(session)
    profile_id = uuid.uuid4()
    await repo.create(profile_id, "Alice@Example.com", "Alice")
    found = await repo.get_by_email("alice@EXAMPLE.com")
    assert found is not None
    assert found.id == profile_id
    assert await repo.get_by_email("nobody@example.com") is None


async def test_create_rejects_invalid_role(session: AsyncSession) -> None:
    with pytest.raises(IntegrityError, match="ck_profiles_role"):
        await ProfileRepository(session).create(uuid.uuid4(), None, None, "root")


async def test_upsert_demo_inserts_then_is_idempotent(session: AsyncSession) -> None:
    repo = ProfileRepository(session)
    profile_id = uuid.uuid4()

    first = await repo.upsert_demo(profile_id, "demo@agentops.local", "Demo", "operator")
    second = await repo.upsert_demo(profile_id, "demo@agentops.local", "Demo", "operator")

    assert first.id == second.id == profile_id
    assert second.created_at == first.created_at
    count = await session.scalar(select(func.count()).select_from(Profile))
    assert count == 1


async def test_upsert_demo_updates_role_and_fields(session: AsyncSession) -> None:
    repo = ProfileRepository(session)
    profile_id = uuid.uuid4()
    await repo.upsert_demo(profile_id, "demo@agentops.local", "Demo", "viewer")

    updated = await repo.upsert_demo(profile_id, "demo2@agentops.local", "Demo 2", "admin")

    assert (updated.email, updated.display_name, updated.role) == (
        "demo2@agentops.local",
        "Demo 2",
        "admin",
    )
    fetched = await repo.get(profile_id)
    assert fetched is not None
    assert fetched.role == "admin"


async def test_set_role(session: AsyncSession) -> None:
    repo = ProfileRepository(session)
    profile_id = uuid.uuid4()
    await repo.create(profile_id, None, None)

    updated = await repo.set_role(profile_id, "admin")

    assert updated is not None
    assert updated.role == "admin"


async def test_set_role_unknown_profile_returns_none(session: AsyncSession) -> None:
    assert await ProfileRepository(session).set_role(uuid.uuid4(), "admin") is None
