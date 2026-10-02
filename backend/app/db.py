import asyncio

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.config import Settings

logger = structlog.get_logger(__name__)

DB_CHECK_TIMEOUT_SECONDS = 2.0


def create_engine(settings: Settings) -> AsyncEngine:
    return create_async_engine(
        settings.DATABASE_URL.get_secret_value(),
        connect_args={"connect_timeout": 2},
    )


async def check_database(engine: AsyncEngine) -> bool:
    """Run SELECT 1 within DB_CHECK_TIMEOUT_SECONDS; never raises or logs the connection string."""
    try:
        async with asyncio.timeout(DB_CHECK_TIMEOUT_SECONDS), engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except Exception as exc:
        logger.error("database_check_failed", error_type=type(exc).__name__)
        return False
    return True
