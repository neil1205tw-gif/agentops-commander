from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine

from app.config import Settings

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

if context.is_offline_mode():
    raise RuntimeError("offline migration is not supported")


def run_migrations_online() -> None:
    # Sync psycopg engine; the URL comes from Settings and is never logged.
    url = Settings().DATABASE_URL.get_secret_value()  # type: ignore[call-arg]
    engine = create_engine(url)
    try:
        with engine.connect() as connection:
            context.configure(connection=connection, target_metadata=None)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        engine.dispose()


run_migrations_online()
