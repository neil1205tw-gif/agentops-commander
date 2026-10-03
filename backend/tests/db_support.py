import os
import uuid
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

ALEMBIC_DIR = Path(__file__).resolve().parents[1] / "alembic"


def require_test_database_url() -> str:
    """Return TEST_DATABASE_URL; skip locally when unset, fail when CI=true."""
    url = os.environ.get("TEST_DATABASE_URL")
    if url:
        return url
    if os.environ.get("CI", "").lower() == "true":
        pytest.fail("TEST_DATABASE_URL must be set when CI=true; database tests cannot be skipped")
    pytest.skip("TEST_DATABASE_URL is not set; skipping database tests")


def database_url_for(admin_url: str, database: str) -> str:
    return make_url(admin_url).set(database=database).render_as_string(hide_password=False)


@contextmanager
def temporary_database(admin_url: str) -> Iterator[str]:
    """Create a randomly named database, yield its URL, and drop it afterwards."""
    name = f"agentops_test_{uuid.uuid4().hex}"
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{name}"'))
        try:
            yield database_url_for(admin_url, name)
        finally:
            with admin_engine.connect() as connection:
                connection.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
    finally:
        admin_engine.dispose()


def run_alembic(database_url: str, action: str, revision: str) -> None:
    """Run `alembic <action> <revision>` against database_url (env.py reads DATABASE_URL)."""
    config = Config()
    config.set_main_option("script_location", str(ALEMBIC_DIR))
    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = database_url
    try:
        getattr(command, action)(config, revision)
    finally:
        if previous is None:
            with suppress(KeyError):
                del os.environ["DATABASE_URL"]
        else:
            os.environ["DATABASE_URL"] = previous
