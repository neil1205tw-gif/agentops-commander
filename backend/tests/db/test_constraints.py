import uuid

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.exc import DBAPIError, IntegrityError

from app.models import INCIDENT_SEVERITIES, INCIDENT_STATUSES, PROFILE_ROLES

OWNER_ID = uuid.UUID("00000000-0000-0000-0000-0000000000a1")


def _insert_profile(
    engine: Engine, profile_id: uuid.UUID = OWNER_ID, email: str | None = None, role: str = "viewer"
) -> None:
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO profiles (id, email, role) VALUES (:id, :email, :role)"),
            {"id": profile_id, "email": email, "role": role},
        )


def _insert_incident(
    engine: Engine,
    *,
    title: str = "disk full",
    severity: str | None = None,
    status: str = "open",
) -> uuid.UUID:
    with engine.begin() as connection:
        incident_id: uuid.UUID = connection.execute(
            text(
                "INSERT INTO incidents (owner_id, scenario_key, title, severity, status) "
                "VALUES (:owner, 'db-outage', :title, :severity, :status) RETURNING id"
            ),
            {"owner": OWNER_ID, "title": title, "severity": severity, "status": status},
        ).scalar_one()
    return incident_id


def _insert_event(engine: Engine, incident_id: uuid.UUID) -> uuid.UUID:
    with engine.begin() as connection:
        event_id: uuid.UUID = connection.execute(
            text(
                "INSERT INTO incident_events (incident_id, event_type, summary) "
                "VALUES (:incident, 'created', 'created') RETURNING id"
            ),
            {"incident": incident_id},
        ).scalar_one()
    return event_id


@pytest.mark.parametrize("role", PROFILE_ROLES)
def test_profile_accepts_valid_roles(sync_engine: Engine, role: str) -> None:
    _insert_profile(sync_engine, role=role)


def test_profile_rejects_invalid_role(sync_engine: Engine) -> None:
    with pytest.raises(IntegrityError, match="ck_profiles_role"):
        _insert_profile(sync_engine, role="superuser")


def test_profile_role_defaults_to_viewer(sync_engine: Engine) -> None:
    with sync_engine.begin() as connection:
        connection.execute(text("INSERT INTO profiles (id) VALUES (:id)"), {"id": OWNER_ID})
        role = connection.execute(text("SELECT role FROM profiles")).scalar_one()
    assert role == "viewer"


def test_profile_email_unique_case_insensitively(sync_engine: Engine) -> None:
    _insert_profile(sync_engine, uuid.uuid4(), email="Alice@Example.com")
    with pytest.raises(IntegrityError, match="uq_profiles_email_lower"):
        _insert_profile(sync_engine, uuid.uuid4(), email="alice@example.COM")


def test_profile_allows_multiple_null_emails(sync_engine: Engine) -> None:
    _insert_profile(sync_engine, uuid.uuid4(), email=None)
    _insert_profile(sync_engine, uuid.uuid4(), email=None)


@pytest.mark.parametrize("status", INCIDENT_STATUSES)
def test_incident_accepts_valid_statuses(sync_engine: Engine, status: str) -> None:
    _insert_profile(sync_engine)
    _insert_incident(sync_engine, status=status)


@pytest.mark.parametrize("severity", [*INCIDENT_SEVERITIES, None])
def test_incident_accepts_valid_severities(sync_engine: Engine, severity: str | None) -> None:
    _insert_profile(sync_engine)
    _insert_incident(sync_engine, severity=severity)


def test_incident_rejects_invalid_status(sync_engine: Engine) -> None:
    _insert_profile(sync_engine)
    with pytest.raises(IntegrityError, match="ck_incidents_status"):
        _insert_incident(sync_engine, status="done")


def test_incident_rejects_invalid_severity(sync_engine: Engine) -> None:
    _insert_profile(sync_engine)
    with pytest.raises(IntegrityError, match="ck_incidents_severity"):
        _insert_incident(sync_engine, severity="P0")


@pytest.mark.parametrize("title", ["", "x" * 201])
def test_incident_rejects_bad_title_length(sync_engine: Engine, title: str) -> None:
    _insert_profile(sync_engine)
    with pytest.raises(IntegrityError, match="ck_incidents_title_length"):
        _insert_incident(sync_engine, title=title)


@pytest.mark.parametrize("title", ["x", "x" * 200])
def test_incident_accepts_title_length_bounds(sync_engine: Engine, title: str) -> None:
    _insert_profile(sync_engine)
    _insert_incident(sync_engine, title=title)


def test_incident_defaults(sync_engine: Engine) -> None:
    _insert_profile(sync_engine)
    incident_id = _insert_incident(sync_engine)
    with sync_engine.connect() as connection:
        row = connection.execute(
            text(
                "SELECT status, severity, affected_services, is_public, deleted_at, resolved_at "
                "FROM incidents WHERE id = :id"
            ),
            {"id": incident_id},
        ).one()
    assert tuple(row) == ("open", None, [], False, None, None)


def test_incident_requires_existing_owner(sync_engine: Engine) -> None:
    with pytest.raises(IntegrityError, match="incidents_owner_id_fkey"):
        _insert_incident(sync_engine)


def test_event_requires_existing_incident(sync_engine: Engine) -> None:
    with pytest.raises(IntegrityError, match="incident_events_incident_id_fkey"):
        _insert_event(sync_engine, uuid.uuid4())


def test_event_update_is_rejected(sync_engine: Engine) -> None:
    _insert_profile(sync_engine)
    event_id = _insert_event(sync_engine, _insert_incident(sync_engine))
    with pytest.raises(DBAPIError, match="append-only"), sync_engine.begin() as connection:
        connection.execute(
            text("UPDATE incident_events SET summary = 'changed' WHERE id = :id"), {"id": event_id}
        )


def test_event_delete_is_rejected(sync_engine: Engine) -> None:
    _insert_profile(sync_engine)
    event_id = _insert_event(sync_engine, _insert_incident(sync_engine))
    with pytest.raises(DBAPIError, match="append-only"), sync_engine.begin() as connection:
        connection.execute(text("DELETE FROM incident_events WHERE id = :id"), {"id": event_id})
    with sync_engine.connect() as connection:
        count = connection.execute(text("SELECT count(*) FROM incident_events")).scalar_one()
    assert count == 1
