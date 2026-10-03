import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import Engine, create_engine, inspect, text

from app.models import Base
from tests.db_support import run_alembic, temporary_database

TABLES = ("profiles", "incidents", "incident_events")
API_ROLES = ("anon", "authenticated")
TABLE_PRIVILEGES = ("SELECT", "INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER")


def _table_names(url: str) -> set[str]:
    engine = create_engine(url)
    try:
        return set(inspect(engine).get_table_names())
    finally:
        engine.dispose()


def test_upgrade_downgrade_upgrade(admin_database_url: str) -> None:
    with temporary_database(admin_database_url) as url:
        run_alembic(url, "upgrade", "head")
        assert set(TABLES) <= _table_names(url)

        run_alembic(url, "downgrade", "base")
        assert not set(TABLES) & _table_names(url)

        run_alembic(url, "upgrade", "head")
        assert set(TABLES) <= _table_names(url)


def test_upgrade_head_is_idempotent(admin_database_url: str) -> None:
    with temporary_database(admin_database_url) as url:
        run_alembic(url, "upgrade", "head")
        run_alembic(url, "upgrade", "head")
        assert set(TABLES) <= _table_names(url)


def test_downgrade_removes_trigger_function(admin_database_url: str) -> None:
    with temporary_database(admin_database_url) as url:
        run_alembic(url, "upgrade", "head")
        run_alembic(url, "downgrade", "base")
        engine = create_engine(url)
        try:
            with engine.connect() as connection:
                remaining = connection.execute(
                    text(
                        "SELECT count(*) FROM pg_proc "
                        "WHERE proname = 'incident_events_forbid_mutation'"
                    )
                ).scalar_one()
        finally:
            engine.dispose()
        assert remaining == 0


def test_rls_enabled_without_policies(sync_engine: Engine) -> None:
    with sync_engine.connect() as connection:
        rows = connection.execute(
            text(
                "SELECT relname, relrowsecurity FROM pg_class "
                "WHERE relname = ANY(:names) AND relkind = 'r'"
            ),
            {"names": list(TABLES)},
        ).all()
        policies = connection.execute(
            text("SELECT count(*) FROM pg_policies WHERE tablename = ANY(:names)"),
            {"names": list(TABLES)},
        ).scalar_one()
    assert {name: enabled for name, enabled in rows} == dict.fromkeys(TABLES, True)
    assert policies == 0


def test_api_roles_have_no_table_privileges(admin_database_url: str) -> None:
    admin = create_engine(admin_database_url, isolation_level="AUTOCOMMIT")
    created: list[str] = []
    try:
        with admin.connect() as connection:
            for role in API_ROLES:
                exists = connection.execute(
                    text("SELECT 1 FROM pg_roles WHERE rolname = :role"), {"role": role}
                ).scalar()
                if not exists:
                    connection.execute(text(f'CREATE ROLE "{role}"'))
                    created.append(role)

        with temporary_database(admin_database_url) as url:
            engine = create_engine(url, isolation_level="AUTOCOMMIT")
            try:
                # Mirror Supabase: new tables are granted to the API roles by default.
                with engine.connect() as connection:
                    connection.execute(
                        text(
                            "ALTER DEFAULT PRIVILEGES IN SCHEMA public "
                            'GRANT ALL ON TABLES TO "anon", "authenticated"'
                        )
                    )
                run_alembic(url, "upgrade", "head")

                with engine.connect() as connection:
                    connection.execute(text("CREATE TABLE control_table (id int)"))
                    for role in API_ROLES:
                        granted = connection.execute(
                            text("SELECT has_table_privilege(:role, 'control_table', 'SELECT')"),
                            {"role": role},
                        ).scalar_one()
                        assert granted, "control: default privileges should have granted access"
                        for table in TABLES:
                            for privilege in TABLE_PRIVILEGES:
                                allowed = connection.execute(
                                    text("SELECT has_table_privilege(:role, :table, :privilege)"),
                                    {"role": role, "table": table, "privilege": privilege},
                                ).scalar_one()
                                assert not allowed, f"{role} has {privilege} on {table}"
            finally:
                engine.dispose()
    finally:
        with admin.connect() as connection:
            for role in created:
                connection.execute(text(f'DROP ROLE IF EXISTS "{role}"'))
        admin.dispose()


def test_models_match_migrated_schema(sync_engine: Engine) -> None:
    with sync_engine.connect() as connection:
        context = MigrationContext.configure(connection)
        diff = compare_metadata(context, Base.metadata)
    assert diff == []


@pytest.mark.parametrize("table", TABLES)
def test_tables_use_uuid_primary_keys(sync_engine: Engine, table: str) -> None:
    columns = {column["name"]: column for column in inspect(sync_engine).get_columns(table)}
    assert columns["id"]["type"].__class__.__name__ == "UUID"
