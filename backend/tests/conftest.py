import asyncio
import os
from collections.abc import Callable

import pytest

# app.main builds the module-level `app` on import, which needs DATABASE_URL.
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://u:p@127.0.0.1:1/none")
os.environ.setdefault("APP_ENV", "test")


def pytest_asyncio_loop_factories(
    config: pytest.Config, item: pytest.Item
) -> dict[str, Callable[[], asyncio.AbstractEventLoop]]:
    # psycopg's async mode cannot run on the Windows ProactorEventLoop.
    return {"selector": asyncio.SelectorEventLoop}
