import asyncio
import time
from collections.abc import Callable
from typing import Any, Protocol

import httpx
import jwt
import structlog

logger = structlog.get_logger(__name__)

JWKS_CACHE_TTL_SECONDS = 600.0
JWKS_MIN_REFETCH_INTERVAL_SECONDS = 30.0
JWKS_FETCH_TIMEOUT_SECONDS = 5.0
_ASYMMETRIC_KEY_TYPES = frozenset({"RSA", "EC"})


class JWKSUnavailableError(Exception):
    """The JWKS could not be fetched and no cached keys exist."""


class JWKSProvider(Protocol):
    async def get_signing_key(self, kid: str) -> Any | None:
        """Return the public key for `kid`, or None when the key set has no such key."""
        ...


class HttpJWKSProvider:
    """Fetches a JWKS over HTTP and caches it.

    The cache lives for `ttl` seconds. An unknown `kid` triggers at most one extra fetch, and no
    fetch (for any reason) happens more often than every `min_refetch_interval` seconds, so
    forged `kid` values cannot be used to flood the JWKS endpoint.
    """

    def __init__(
        self,
        url: str,
        *,
        ttl: float = JWKS_CACHE_TTL_SECONDS,
        min_refetch_interval: float = JWKS_MIN_REFETCH_INTERVAL_SECONDS,
        timeout: float = JWKS_FETCH_TIMEOUT_SECONDS,
        transport: httpx.AsyncBaseTransport | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._url = url
        self._ttl = ttl
        self._min_refetch_interval = min_refetch_interval
        self._timeout = timeout
        self._transport = transport
        self._clock = clock
        self._keys: dict[str, jwt.PyJWK] = {}
        self._fetched_at: float | None = None
        self._last_attempt_at: float | None = None
        self._lock = asyncio.Lock()

    async def get_signing_key(self, kid: str) -> Any | None:
        async with self._lock:
            now = self._clock()
            if self._is_fresh(now) and kid in self._keys:
                return self._keys[kid].key
            if self._may_fetch(now):
                await self._fetch(now)
            key = self._keys.get(kid)
            if key is None:
                if not self._keys and self._fetched_at is None:
                    raise JWKSUnavailableError
                return None
            return key.key

    def _is_fresh(self, now: float) -> bool:
        return self._fetched_at is not None and now - self._fetched_at < self._ttl

    def _may_fetch(self, now: float) -> bool:
        return (
            self._last_attempt_at is None
            or now - self._last_attempt_at >= self._min_refetch_interval
        )

    async def _fetch(self, now: float) -> None:
        self._last_attempt_at = now
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout, transport=self._transport, follow_redirects=False
            ) as client:
                response = await client.get(self._url)
                response.raise_for_status()
                document = response.json()
            keys = _parse_keys(document["keys"])
        except Exception as exc:
            # Keep serving previously cached keys; never log the URL or response body.
            logger.warning("jwks_fetch_failed", error_type=type(exc).__name__)
            return
        self._keys = keys
        self._fetched_at = now


def _parse_keys(entries: list[Any]) -> dict[str, jwt.PyJWK]:
    keys: dict[str, jwt.PyJWK] = {}
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("kid"), str):
            continue
        if entry.get("kty") not in _ASYMMETRIC_KEY_TYPES:
            continue
        try:
            keys[entry["kid"]] = jwt.PyJWK(entry)
        except Exception:  # noqa: S112 - one malformed key must not reject the whole set
            continue
    return keys
