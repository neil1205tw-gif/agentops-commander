from typing import Any

import httpx
import pytest

from app.auth.jwks import HttpJWKSProvider, JWKSUnavailableError
from tests.auth_support import KeyPair

KEY_A = KeyPair("key-a", "RS256")
KEY_B = KeyPair("key-b", "ES256")
URL = "https://project.example.test/auth/v1/.well-known/jwks.json"


class FakeTransport(httpx.AsyncBaseTransport):
    """Serves a replaceable JWKS document and records every request."""

    def __init__(self, *pairs: KeyPair) -> None:
        self.keys = [pair.jwk for pair in pairs]
        self.requests: list[str] = []
        self.status = 200
        self.fail = False

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(str(request.url))
        if self.fail:
            raise httpx.ConnectTimeout("timed out")
        return httpx.Response(self.status, json={"keys": self.keys})


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def _provider(transport: FakeTransport, clock: Clock) -> HttpJWKSProvider:
    return HttpJWKSProvider(URL, ttl=600, min_refetch_interval=30, transport=transport, clock=clock)


async def test_fetches_the_configured_url_and_returns_the_key() -> None:
    transport, clock = FakeTransport(KEY_A, KEY_B), Clock()
    provider = _provider(transport, clock)
    key = await provider.get_signing_key("key-a")
    assert key is not None
    assert transport.requests == [URL]


async def test_cached_keys_are_reused_within_ttl() -> None:
    transport, clock = FakeTransport(KEY_A), Clock()
    provider = _provider(transport, clock)
    await provider.get_signing_key("key-a")
    clock.now += 599
    assert await provider.get_signing_key("key-a") is not None
    assert len(transport.requests) == 1


async def test_cache_is_refreshed_after_ttl() -> None:
    transport, clock = FakeTransport(KEY_A), Clock()
    provider = _provider(transport, clock)
    await provider.get_signing_key("key-a")
    transport.keys = [KEY_B.jwk]
    clock.now += 601
    assert await provider.get_signing_key("key-b") is not None
    assert await provider.get_signing_key("key-a") is None
    assert len(transport.requests) == 2


async def test_unknown_kid_triggers_one_refetch_then_is_rate_limited() -> None:
    transport, clock = FakeTransport(KEY_A), Clock()
    provider = _provider(transport, clock)
    await provider.get_signing_key("key-a")
    clock.now += 31
    transport.keys = [KEY_A.jwk, KEY_B.jwk]
    assert await provider.get_signing_key("key-b") is not None  # picked up by the refetch
    assert len(transport.requests) == 2
    # Unknown kids right after a fetch must not hit the network again.
    for _ in range(5):
        assert await provider.get_signing_key("forged") is None
    assert len(transport.requests) == 2
    clock.now += 31
    assert await provider.get_signing_key("forged") is None
    assert len(transport.requests) == 3


async def test_unknown_kid_on_first_use_fetches_once() -> None:
    transport, clock = FakeTransport(KEY_A), Clock()
    provider = _provider(transport, clock)
    assert await provider.get_signing_key("forged") is None
    assert await provider.get_signing_key("forged") is None
    assert len(transport.requests) == 1


async def test_fetch_failure_without_cache_raises_and_is_rate_limited() -> None:
    transport, clock = FakeTransport(KEY_A), Clock()
    transport.fail = True
    provider = _provider(transport, clock)
    with pytest.raises(JWKSUnavailableError):
        await provider.get_signing_key("key-a")
    with pytest.raises(JWKSUnavailableError):
        await provider.get_signing_key("key-a")
    assert len(transport.requests) == 1
    transport.fail = False
    clock.now += 31
    assert await provider.get_signing_key("key-a") is not None


async def test_fetch_failure_keeps_serving_cached_keys() -> None:
    transport, clock = FakeTransport(KEY_A), Clock()
    provider = _provider(transport, clock)
    await provider.get_signing_key("key-a")
    transport.fail = True
    clock.now += 601
    assert await provider.get_signing_key("key-a") is not None


async def test_http_error_status_counts_as_failure() -> None:
    transport, clock = FakeTransport(KEY_A), Clock()
    transport.status = 500
    with pytest.raises(JWKSUnavailableError):
        await _provider(transport, clock).get_signing_key("key-a")


async def test_unusable_entries_are_skipped() -> None:
    transport, clock = FakeTransport(KEY_A), Clock()
    entries: list[Any] = [
        {"kty": "oct", "kid": "no-such-type"},
        {"kty": "RSA", "kid": "broken"},
        {"kty": "RSA"},
        "not-an-object",
        KEY_A.jwk,
    ]
    transport.keys = entries
    provider = _provider(transport, clock)
    assert await provider.get_signing_key("key-a") is not None
    assert await provider.get_signing_key("broken") is None
