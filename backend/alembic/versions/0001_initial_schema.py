"""initial schema: profiles, incidents, incident_events

Revision ID: 0001
Revises:
Create Date: 2026-10-03
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = ("profiles", "incidents", "incident_events")

UUID_DEFAULT = sa.text("gen_random_uuid()")
NOW = sa.text("now()")

# Supabase 的 anon / authenticated role 在本機 pgvector image 不存在，存在時才 REVOKE。
REVOKE_API_ROLES_SQL = """
DO $$
DECLARE
    api_role text;
BEGIN
    FOREACH api_role IN ARRAY ARRAY['anon', 'authenticated'] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = api_role) THEN
            EXECUTE format(
                'REVOKE ALL ON TABLE profiles, incidents, incident_events FROM %I', api_role
            );
        END IF;
    END LOOP;
END
$$
"""

FORBID_MUTATION_FUNCTION_SQL = """
CREATE FUNCTION incident_events_forbid_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'incident_events is append-only (% not allowed)', TG_OP;
END
$$
"""


def upgrade() -> None:
    op.create_table(
        "profiles",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("display_name", sa.Text(), nullable=True),
        sa.Column("role", sa.Text(), nullable=False, server_default="viewer"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.CheckConstraint("role IN ('viewer', 'operator', 'admin')", name="ck_profiles_role"),
    )
    op.create_index(
        "uq_profiles_email_lower",
        "profiles",
        [sa.text("lower(email)")],
        unique=True,
        postgresql_where=sa.text("email IS NOT NULL"),
    )

    op.create_table(
        "incidents",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=UUID_DEFAULT),
        sa.Column("owner_id", sa.Uuid(), sa.ForeignKey("profiles.id"), nullable=False),
        sa.Column("scenario_key", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("severity", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="open"),
        sa.Column(
            "affected_services",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "char_length(title) BETWEEN 1 AND 200", name="ck_incidents_title_length"
        ),
        sa.CheckConstraint(
            "severity IS NULL OR severity IN ('P1', 'P2', 'P3', 'P4')",
            name="ck_incidents_severity",
        ),
        sa.CheckConstraint(
            "status IN ('open', 'investigating', 'awaiting_approval', 'executing', "
            "'verifying', 'resolved', 'mitigated', 'escalated', 'failed')",
            name="ck_incidents_status",
        ),
    )
    op.create_index(
        "ix_incidents_owner_id_created_at",
        "incidents",
        ["owner_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_incidents_public_created_at",
        "incidents",
        ["is_public", sa.text("created_at DESC")],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "incident_events",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=UUID_DEFAULT),
        sa.Column("incident_id", sa.Uuid(), sa.ForeignKey("incidents.id"), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("agent_name", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column(
            "payload",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
    )
    op.create_index(
        "ix_incident_events_incident_id_created_at_id",
        "incident_events",
        ["incident_id", "created_at", "id"],
    )

    op.execute(FORBID_MUTATION_FUNCTION_SQL)
    op.execute(
        "CREATE TRIGGER incident_events_append_only "
        "BEFORE UPDATE OR DELETE ON incident_events "
        "FOR EACH ROW EXECUTE FUNCTION incident_events_forbid_mutation()"
    )

    for table in TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
    op.execute(REVOKE_API_ROLES_SQL)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS incident_events_append_only ON incident_events")
    op.execute("DROP FUNCTION IF EXISTS incident_events_forbid_mutation()")
    op.drop_table("incident_events")
    op.drop_table("incidents")
    op.drop_table("profiles")
