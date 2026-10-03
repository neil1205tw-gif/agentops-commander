import json
import time
import uuid
from typing import Any

import jwt
from cryptography.hazmat.primitives.asymmetric import ec, rsa

from app.config import Settings
from tests.helpers import make_settings

SUPABASE_URL = "https://project.example.test"
ISSUER = f"{SUPABASE_URL}/auth/v1"
AUDIENCE = "authenticated"
DEV_SECRET = "test-dev-secret-0123456789abcdef0123456789"


def auth_settings(**overrides: Any) -> Settings:
    values: dict[str, Any] = {
        "APP_ENV": "test",
        "DATABASE_URL": "postgresql+psycopg://x:y@127.0.0.1:1/none",
        "SUPABASE_URL": SUPABASE_URL,
        "JWT_ISSUER": ISSUER,
        "DEV_AUTH_SECRET": DEV_SECRET,
    }
    values.update(overrides)
    return make_settings(**values)


class KeyPair:
    """A generated signing key plus its public JWK (kid is the lookup key)."""

    def __init__(self, kid: str, algorithm: str) -> None:
        self.kid = kid
        self.algorithm = algorithm
        if algorithm == "RS256":
            self.private_key: Any = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        else:
            self.private_key = ec.generate_private_key(ec.SECP256R1())
        self.public_key = self.private_key.public_key()

    @property
    def jwk(self) -> dict[str, Any]:
        algorithm = jwt.get_algorithm_by_name(self.algorithm)
        data: dict[str, Any] = json.loads(algorithm.to_jwk(self.public_key))
        data.update({"kid": self.kid, "alg": self.algorithm, "use": "sig"})
        return data

    def sign(self, claims: dict[str, Any], *, kid: str | None = None) -> str:
        return jwt.encode(
            claims, self.private_key, algorithm=self.algorithm, headers={"kid": kid or self.kid}
        )


class FakeJWKSProvider:
    """Replaces the HTTP-backed provider in tests; serves keys from memory."""

    def __init__(self, *pairs: KeyPair) -> None:
        self.keys = {pair.kid: pair.public_key for pair in pairs}
        self.calls: list[str] = []

    async def get_signing_key(self, kid: str) -> Any | None:
        self.calls.append(kid)
        return self.keys.get(kid)


def supabase_claims(**overrides: Any) -> dict[str, Any]:
    claims: dict[str, Any] = {
        "sub": str(uuid.uuid4()),
        "email": "user@example.test",
        "iss": ISSUER,
        "aud": AUDIENCE,
        "exp": int(time.time()) + 3600,
    }
    claims.update(overrides)
    return {key: value for key, value in claims.items() if value is not None}


def dev_token(claims: dict[str, Any], secret: str = DEV_SECRET) -> str:
    return jwt.encode(claims, secret, algorithm="HS256")
