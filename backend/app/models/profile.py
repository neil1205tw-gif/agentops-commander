import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Index, Text, Uuid, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

PROFILE_ROLES = ("viewer", "operator", "admin")


class Profile(Base):
    __tablename__ = "profiles"
    __table_args__ = (
        CheckConstraint("role IN ('viewer', 'operator', 'admin')", name="ck_profiles_role"),
        Index(
            "uq_profiles_email_lower",
            text("lower(email)"),
            unique=True,
            postgresql_where=text("email IS NOT NULL"),
        ),
    )
    __mapper_args__ = {"eager_defaults": True}

    # Equals the Supabase Auth user id; written by the app, never generated here.
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    email: Mapped[str | None] = mapped_column(Text)
    display_name: Mapped[str | None] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text, server_default="viewer")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
