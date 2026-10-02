import logging
import re
from collections.abc import Mapping, MutableMapping
from typing import Any

import structlog
from structlog.typing import EventDict, Processor, WrappedLogger

from app.config import Settings

REDACTED = "[REDACTED]"

_SENSITIVE_KEYS = frozenset(
    {
        "authorization",
        "proxy_authorization",
        "cookie",
        "set_cookie",
        "password",
        "secret",
        "token",
        "api_key",
        "apikey",
        "database_url",
    }
)
_SENSITIVE_SUFFIXES = ("_key", "_secret", "_token")

# scheme://userinfo@host -> userinfo is masked; userinfo runs to the last "@" before a "/" or space.
_DSN_PATTERN = re.compile(r"(postgres(?:ql)?(?:\+\w+)?://)[^/\s]*@", re.IGNORECASE)


def _is_sensitive_key(key: object) -> bool:
    if not isinstance(key, str):
        return False
    lowered = key.lower().replace("-", "_")
    return lowered in _SENSITIVE_KEYS or lowered.endswith(_SENSITIVE_SUFFIXES)


def _redact_value(value: Any) -> Any:
    if isinstance(value, str):
        return _DSN_PATTERN.sub(rf"\1{REDACTED}@", value)
    if isinstance(value, Mapping):
        return {
            key: REDACTED if _is_sensitive_key(key) else _redact_value(item)
            for key, item in value.items()
        }
    if isinstance(value, list | tuple):
        return type(value)(_redact_value(item) for item in value)
    return value


def redact_processor(
    logger: WrappedLogger, method_name: str, event_dict: MutableMapping[str, Any]
) -> EventDict:
    """Mask sensitive keys (recursively) and credentials embedded in DSN-like strings."""
    return dict(_redact_value(dict(event_dict)))


def configure_logging(settings: Settings) -> None:
    renderer: Processor = (
        structlog.processors.JSONRenderer()
        if settings.APP_ENV == "production"
        else structlog.dev.ConsoleRenderer()
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.format_exc_info,
            redact_processor,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelNamesMapping()[settings.LOG_LEVEL]
        ),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False,
    )
