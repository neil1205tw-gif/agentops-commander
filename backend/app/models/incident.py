import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Text,
    Uuid,
    false,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

INCIDENT_SEVERITIES = ("P1", "P2", "P3", "P4")
INCIDENT_STATUSES = (
    "open",
    "investigating",
    "awaiting_approval",
    "executing",
    "verifying",
    "resolved",
    "mitigated",
    "escalated",
    "failed",
)


class Incident(Base):
    __tablename__ = "incidents"
    __table_args__ = (
        CheckConstraint("char_length(title) BETWEEN 1 AND 200", name="ck_incidents_title_length"),
        CheckConstraint(
            "severity IS NULL OR severity IN ('P1', 'P2', 'P3', 'P4')",
            name="ck_incidents_severity",
        ),
        CheckConstraint(
            "status IN ('open', 'investigating', 'awaiting_approval', 'executing', "
            "'verifying', 'resolved', 'mitigated', 'escalated', 'failed')",
            name="ck_incidents_status",
        ),
        Index("ix_incidents_owner_id_created_at", "owner_id", text("created_at DESC")),
        Index(
            "ix_incidents_public_created_at",
            "is_public",
            text("created_at DESC"),
            postgresql_where=text("deleted_at IS NULL"),
        ),
    )
    __mapper_args__ = {"eager_defaults": True}

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, server_default=func.gen_random_uuid()
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("profiles.id"))
    scenario_key: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(Text)
    severity: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, server_default="open")
    affected_services: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default=text("'{}'"))
    is_public: Mapped[bool] = mapped_column(Boolean, server_default=false())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
