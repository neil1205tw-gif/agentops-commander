import base64
import json
import time
import uuid

import jwt
import pytest
import structlog

from app.auth import TokenVerifier
from app.auth.errors import InvalidTokenError
from app.auth.jwks import JWKSUnavailableError
from tests.auth_support import (
    AUDIENCE,
    DEV_SECRET,
    ISSUER,
    FakeJWKSProvider,
    KeyPair,
    auth_settings,
    dev_token,
    supabase_claims,
)

RSA_KEY = KeyPair("rsa-1", "RS256")
EC_KEY = KeyPair("ec-1", "ES256")


def _verifier(**settings: object) -> TokenVerifier:
    return TokenVerifier(auth_settings(**settings), FakeJWKSProvider(RSA_KEY, EC_KEY))


def _dev_claims(**overrides: object) -> dict[str, object]:
    claims = supabase_claims(iss="agentops-dev")
    claims.update(overrides)
    return {key: value for key, value in claims.items() if value is not None}


async def _reason(verifier: TokenVerifier, token: str) -> str:
    with pytest.raises(InvalidTokenError) as excinfo:
        await verifier.verify(token)
    return excinfo.value.reason


@pytest.mark.parametrize("key", [RSA_KEY, EC_KEY], ids=["rs256", "es256"])
async def test_valid_supabase_token(key: KeyPair) -> None:
    sub = uuid.uuid4()
    claims = await _verifier().verify(
        key.sign(supabase_claims(sub=str(sub), email="a@example.test"))
    )
    assert claims.sub == sub
    assert claims.email == "a@example.test"
    assert claims.source == "supabase"


async def test_valid_token_without_email_claim() -> None:
    claims = await _verifier().verify(RSA_KEY.sign(supabase_claims(email=None)))
    assert claims.email is None


async def test_valid_dev_token() -> None:
    sub = uuid.uuid4()
    claims = await _verifier().verify(dev_token(_dev_claims(sub=str(sub))))
    assert claims.sub == sub
    assert claims.source == "dev"


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"exp": int(time.time()) - 10}, "expired"),
        ({"iss": "https://other.example.test"}, "bad_issuer"),
        ({"aud": "someone-else"}, "bad_audience"),
        ({"exp": None}, "missing_claim"),
        ({"aud": None}, "missing_claim"),
        ({"iss": None}, "missing_claim"),
        ({"sub": None}, "missing_claim"),
        ({"sub": "not-a-uuid"}, "bad_subject"),
        ({"sub": 12345}, "invalid_token"),
    ],
)
@pytest.mark.parametrize("key", [RSA_KEY, EC_KEY], ids=["rs256", "es256"])
async def test_supabase_claim_failures(
    key: KeyPair, overrides: dict[str, object], reason: str
) -> None:
    assert await _reason(_verifier(), key.sign(supabase_claims(**overrides))) == reason


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"exp": int(time.time()) - 10}, "expired"),
        ({"iss": ISSUER}, "bad_issuer"),
        ({"aud": "someone-else"}, "bad_audience"),
        ({"exp": None}, "missing_claim"),
        ({"sub": "not-a-uuid"}, "bad_subject"),
    ],
)
async def test_dev_claim_failures(overrides: dict[str, object], reason: str) -> None:
    assert await _reason(_verifier(), dev_token(_dev_claims(**overrides))) == reason


async def test_dev_token_with_wrong_secret() -> None:
    assert await _reason(_verifier(), dev_token(_dev_claims(), "x" * 40)) == "bad_signature"


async def test_bad_signature_from_another_key() -> None:
    forged = KeyPair("rsa-1", "RS256").sign(supabase_claims())
    assert await _reason(_verifier(), forged) == "bad_signature"


async def test_unknown_kid() -> None:
    token = RSA_KEY.sign(supabase_claims(), kid="rotated-away")
    assert await _reason(_verifier(), token) == "unknown_kid"


async def test_missing_kid() -> None:
    token = jwt.encode(supabase_claims(), RSA_KEY.private_key, algorithm="RS256")
    assert await _reason(_verifier(), token) == "missing_kid"


async def test_key_type_must_match_algorithm() -> None:
    # Header claims ES256 but the kid resolves to an RSA key.
    token = EC_KEY.sign(supabase_claims(), kid=RSA_KEY.kid)
    assert await _reason(_verifier(), token) == "invalid_token"


def _unsigned_token() -> str:
    def part(data: dict[str, object]) -> str:
        return base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b"=").decode()

    return f"{part({'alg': 'none', 'typ': 'JWT'})}.{part(supabase_claims())}."


async def test_alg_none_is_rejected() -> None:
    assert await _reason(_verifier(), _unsigned_token()) == "alg_none"


async def test_hs256_is_rejected_on_the_supabase_path() -> None:
    # Algorithm confusion: HS256 token signed with the RSA public key as the secret, with a kid.
    token = jwt.encode(supabase_claims(), "k" * 40, algorithm="HS256", headers={"kid": RSA_KEY.kid})
    # In test env dev auth is on: the token is treated as a dev token and fails the secret check.
    assert await _reason(_verifier(), token) == "bad_signature"
    # With dev auth off (production) HS256 is not accepted at all.
    production = _verifier(APP_ENV="production")
    assert await _reason(production, token) == "dev_auth_disabled"


async def test_hs256_signed_with_dev_secret_has_no_effect_with_forged_issuer() -> None:
    # A token claiming the Supabase issuer but signed with HS256 never reaches the Supabase path.
    token = dev_token(supabase_claims())
    assert await _reason(_verifier(), token) == "bad_issuer"


async def test_dev_token_rejected_when_dev_auth_is_disabled() -> None:
    verifier = _verifier(APP_ENV="production")
    assert await _reason(verifier, dev_token(_dev_claims())) == "dev_auth_disabled"
    # Even a token signed with the (default) secret value is refused.
    assert await _reason(verifier, dev_token(_dev_claims(), DEV_SECRET)) == "dev_auth_disabled"


async def test_unsupported_algorithm() -> None:
    token = jwt.encode(supabase_claims(), "k" * 64, algorithm="HS512")
    assert await _reason(_verifier(), token) == "unsupported_alg"


@pytest.mark.parametrize("token", ["", "garbage", "a.b.c", "a.b"])
async def test_malformed_tokens(token: str) -> None:
    assert await _reason(_verifier(), token) == "malformed"


async def test_token_without_alg_header() -> None:
    header = base64.urlsafe_b64encode(b'{"typ": "JWT"}').rstrip(b"=").decode()
    assert await _reason(_verifier(), f"{header}.e30.") == "malformed"


async def test_supabase_path_requires_configuration() -> None:
    verifier = TokenVerifier(auth_settings(SUPABASE_URL="", JWT_ISSUER=""))
    assert await _reason(verifier, RSA_KEY.sign(supabase_claims())) == "supabase_not_configured"


async def test_default_provider_is_built_from_supabase_url() -> None:
    from app.auth.jwks import HttpJWKSProvider

    verifier = TokenVerifier(auth_settings())
    assert isinstance(verifier._jwks_provider, HttpJWKSProvider)


async def test_failure_logs_only_the_category() -> None:
    token = RSA_KEY.sign(supabase_claims(aud="someone-else"))
    with structlog.testing.capture_logs() as logs:
        await _reason(_verifier(), token)
    assert logs == [{"event": "token_rejected", "reason": "bad_audience", "log_level": "warning"}]
    assert token not in json.dumps(logs)
    assert AUDIENCE not in json.dumps(logs)


async def test_unavailable_jwks_is_rejected() -> None:
    class UnavailableProvider:
        async def get_signing_key(self, kid: str) -> object | None:
            raise JWKSUnavailableError

    verifier = TokenVerifier(auth_settings(), UnavailableProvider())
    assert await _reason(verifier, RSA_KEY.sign(supabase_claims())) == "jwks_unavailable"
