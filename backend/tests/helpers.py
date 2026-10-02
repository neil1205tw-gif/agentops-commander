from typing import Any

from app.config import Settings


def make_settings(**values: Any) -> Settings:
    """Build Settings from explicit values only (ignores any local .env file)."""
    return Settings(_env_file=None, **values)  # type: ignore[call-arg]
