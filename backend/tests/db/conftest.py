from collections.abc import AsyncIterator, Iterator

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from tests.db_support import require_test_database_url, run_alembic, temporary_database

TABLES = ("incident_events", "incidents", "profiles")


@pytest.fixture(scope="session")
def admin_database_url() -> str:
    return require_test_database_url()


@pytest.fixture(scope="session")
def migrated_database_url(admin_database_url: str) -> Iterator[str]:
    """A temporary database with `alembic upgrade head` applied, dropped at session end."""
    with temporary_database(admin_database_url) as url:
        run_alembic(url, "upgrade", "head")
        yield url


@pytest.fixture(scope="session")
def sync_engine(migrated_database_url: str) -> Iterator[Engine]:
    engine = create_engine(migrated_database_url)
    yield engine
    engine.dispose()


@pytest.fixture(autouse=True)
def clean_tables(sync_engine: Engine) -> None:
    with sync_engine.begin() as connection:
        connection.execute(text(f"TRUNCATE {', '.join(TABLES)} CASCADE"))


@pytest.fixture
async def async_engine(migrated_database_url: str) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(migrated_database_url, poolclass=NullPool)
    yield engine
    await engine.dispose()


@pytest.fixture
async def session(async_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    async with AsyncSession(async_engine, expire_on_commit=False) as db_session:
        yield db_session
        await db_session.rollback()
