import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.scenarios import ScenarioAlert

IncidentStatus = Literal[
    "open",
    "investigating",
    "awaiting_approval",
    "executing",
    "verifying",
    "resolved",
    "mitigated",
    "escalated",
    "failed",
]
IncidentSeverity = Literal["P1", "P2", "P3", "P4"]

TITLE_MAX_LENGTH = 200


class IncidentCreate(BaseModel):
    scenario_key: str = Field(min_length=1, max_length=100)
    # None means "use the scenario's default title"; a blank title is treated the same way.
    title: str | None = None

    @field_validator("title")
    @classmethod
    def _normalize_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        title = value.strip()
        if not title:
            return None
        if len(title) > TITLE_MAX_LENGTH:
            raise ValueError(f"title must be at most {TITLE_MAX_LENGTH} characters")
        if "\x00" in title:
            raise ValueError("title must not contain NUL characters")
        return title


class VisibilityUpdate(BaseModel):
    is_public: bool


class IncidentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    scenario_key: str
    severity: IncidentSeverity | None
    status: IncidentStatus
    affected_services: list[str]
    is_public: bool
    owner_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class IncidentDetail(IncidentSummary):
    resolved_at: datetime | None
    # None when the incident's scenario is no longer in the registry.
    alert: ScenarioAlert | None


class IncidentList(BaseModel):
    items: list[IncidentSummary]
    total: int
    limit: int
    offset: int


class IncidentEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    event_type: str
    agent_name: str | None
    summary: str
    payload: dict[str, Any]
    created_at: datetime


class IncidentEventList(BaseModel):
    items: list[IncidentEventOut]
