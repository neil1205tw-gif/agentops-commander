import uuid
from datetime import UTC, datetime
from typing import get_args

import pytest
from pydantic import ValidationError

from app.auth import CurrentUser
from app.auth.models import Role
from app.models import Incident
from app.models.incident import INCIDENT_SEVERITIES, INCIDENT_STATUSES
from app.schemas import IncidentCreate, IncidentSeverity, IncidentStatus
from app.services import visibility_scope

OWNER = uuid.uuid4()
OTHER = uuid.uuid4()


def _user(role: Role, user_id: uuid.UUID) -> CurrentUser:
    return CurrentUser(id=user_id, email=None, display_name=None, role=role)


def _incident(owner_id: uuid.UUID, *, is_public: bool = False, deleted: bool = False) -> Incident:
    return Incident(
        owner_id=owner_id,
        is_public=is_public,
        deleted_at=datetime.now(UTC) if deleted else None,
    )


@pytest.mark.parametrize(
    ("role", "user_id", "is_public", "expected"),
    [
        ("viewer", OTHER, False, False),
        ("viewer", OWNER, False, False),
        ("viewer", OTHER, True, True),
        ("operator", OWNER, False, True),
        ("operator", OTHER, False, False),
        ("operator", OTHER, True, True),
        ("admin", OTHER, False, True),
        ("admin", OWNER, True, True),
    ],
)
def test_visibility_matrix(role: Role, user_id: uuid.UUID, is_public: bool, expected: bool) -> None:
    scope = visibility_scope(_user(role, user_id))
    assert scope.allows(_incident(OWNER, is_public=is_public)) is expected


@pytest.mark.parametrize("role", ["viewer", "operator", "admin"])
def test_deleted_incidents_are_never_visible(role: Role) -> None:
    scope = visibility_scope(_user(role, OWNER))
    assert scope.allows(_incident(OWNER, is_public=True, deleted=True)) is False


def test_schema_literals_match_the_database_constraints() -> None:
    assert get_args(IncidentStatus) == INCIDENT_STATUSES
    assert get_args(IncidentSeverity) == INCIDENT_SEVERITIES


def test_title_normalization() -> None:
    assert IncidentCreate(scenario_key="a", title="  hi  ").title == "hi"
    assert IncidentCreate(scenario_key="a", title="   ").title is None
    assert IncidentCreate(scenario_key="a").title is None
    assert IncidentCreate(scenario_key="a", title="x" * 200).title == "x" * 200
    with pytest.raises(ValidationError):
        IncidentCreate(scenario_key="a", title="x" * 201)
    with pytest.raises(ValidationError):
        IncidentCreate(scenario_key="a", title="a\x00b")
