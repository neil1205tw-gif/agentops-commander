import json
from typing import Any

import pytest
import structlog

from app.logging import REDACTED, configure_logging, redact_processor
from tests.helpers import make_settings

DSN = "postgresql://a:b@h/d"


def _redact(event_dict: dict[str, Any]) -> dict[str, Any]:
    return dict(redact_processor(None, "info", event_dict))


@pytest.mark.parametrize(
    "key",
    [
        "authorization",
        "Authorization",
        "COOKIE",
        "Set-Cookie",
        "password",
        "Secret",
        "token",
        "api_key",
        "ApiKey",
        "apikey",
        "database_url",
        "DATABASE_URL",
        "gemini_api_key",
        "client_secret",
        "access_token",
        "SUPABASE_SECRET_KEY",
        "X-API-Key",
        "x-api-key",
        "X-Auth-Token",
        "x-client-secret",
        "Proxy-Authorization",
        "proxy-authorization",
        "SET-COOKIE",
    ],
)
def test_sensitive_keys_are_redacted(key: str) -> None:
    assert _redact({key: "value", "event": "x"}) == {key: REDACTED, "event": "x"}


def test_nested_sensitive_keys_are_redacted() -> None:
    result = _redact(
        {
            "headers": {"Authorization": "Bearer abc", "accept": "json"},
            "items": [{"cookie": "sid=1"}, "plain"],
        }
    )
    assert result == {
        "headers": {"Authorization": REDACTED, "accept": "json"},
        "items": [{"cookie": REDACTED}, "plain"],
    }


def test_nested_hyphenated_headers_are_redacted() -> None:
    result = _redact(
        {
            "request": {
                "headers": {
                    "X-API-Key": "k1",
                    "x-Auth-Token": "t1",
                    "Proxy-Authorization": "Basic abc",
                    "Set-Cookie": "sid=1",
                    "x-request-id": "r1",
                    "Content-Type": "application/json",
                }
            },
            "items": [{"X-Client-Secret": "s1"}],
        }
    )
    assert result == {
        "request": {
            "headers": {
                "X-API-Key": REDACTED,
                "x-Auth-Token": REDACTED,
                "Proxy-Authorization": REDACTED,
                "Set-Cookie": REDACTED,
                "x-request-id": "r1",
                "Content-Type": "application/json",
            }
        },
        "items": [{"X-Client-Secret": REDACTED}],
    }


def test_regular_fields_are_untouched() -> None:
    event = {
        "event": "hello",
        "user_id": 42,
        "keyboard": "k",
        "path": "/health/live",
        "x-request-id": "r1",
        "content-type": "application/json",
    }
    assert _redact(event) == event


@pytest.mark.parametrize(
    "dsn",
    [
        "postgresql://user:password@host:5432/db",
        "postgresql+psycopg://user:p@ss@host:5432/db",
        "POSTGRES://user:password@host/db",
    ],
)
def test_connection_string_credentials_are_masked(dsn: str) -> None:
    result = _redact({"event": f"connect failed: {dsn}", "detail": {"msg": dsn}})
    serialized = json.dumps(result)
    assert "password" not in serialized
    assert "p@ss" not in serialized
    assert "user:" not in serialized
    assert f"{REDACTED}@host" in result["event"]


def test_connection_string_without_credentials_is_unchanged() -> None:
    event = {"event": "postgresql://host:5432/db"}
    assert _redact(event) == event


def test_configure_logging_production_emits_redacted_json(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging(make_settings(APP_ENV="production", DATABASE_URL=DSN))
    structlog.get_logger().info(
        "boot",
        password="hunter2",  # noqa: S106
        url="postgresql+psycopg://x:y@127.0.0.1:1/none",
    )
    line = capsys.readouterr().out.strip()
    payload = json.loads(line)
    assert payload["event"] == "boot"
    assert payload["password"] == REDACTED
    assert "x:y" not in line
    assert "hunter2" not in line


def test_configure_logging_development_uses_console_and_redacts(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging(make_settings(APP_ENV="development", LOG_LEVEL="WARNING", DATABASE_URL=DSN))
    log = structlog.get_logger()
    log.info("hidden")
    log.warning("shown", token="abc")  # noqa: S106
    out = capsys.readouterr().out
    assert "hidden" not in out
    assert "shown" in out
    assert "abc" not in out
