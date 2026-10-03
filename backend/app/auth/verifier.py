import uuid
from typing import Any, Literal

import jwt
import structlog
from pydantic import BaseModel, ConfigDict

from app.auth.errors import InvalidTokenError
from app.auth.jwks import HttpJWKSProvider, JWKSProvider, JWKSUnavailableError
from app.config import Settings

logger = structlog.get_logger(__name__)

DEV_ISSUER = "agentops-dev"
DEV_ALGORITHM = "HS256"
SUPABASE_ALGORITHMS = frozenset({"RS256", "ES256"})
_REQUIRED_CLAIMS = ["exp", "iss", "aud", "sub"]


class AuthClaims(BaseModel):
    model_config = ConfigDict(frozen=True)

    sub: uuid.UUID
    email: str | None = None
    source: Literal["supabase", "dev"]


class TokenVerifier:
    """Verifies bearer tokens. The path is chosen only by the header `alg` and the settings."""

    def __init__(self, settings: Settings, jwks_provider: JWKSProvider | None = None) -> None:
        self._settings = settings
        if jwks_provider is None and settings.SUPABASE_URL:
            jwks_provider = HttpJWKSProvider(
                f"{settings.SUPABASE_URL}/auth/v1/.well-known/jwks.json"
            )
        self._jwks_provider = jwks_provider

    async def verify(self, token: str) -> AuthClaims:
        """Return the claims or raise InvalidTokenError (reason is logged, never returned)."""
        try:
            claims = await self._verify(token)
        except InvalidTokenError as exc:
            logger.warning("token_rejected", reason=exc.reason)
            raise
        return claims

    async def _verify(self, token: str) -> AuthClaims:
        try:
            header = jwt.get_unverified_header(token)
        except jwt.PyJWTError:
            raise InvalidTokenError("malformed") from None
        alg = header.get("alg")
        if not isinstance(alg, str):
            raise InvalidTokenError("malformed")
        if alg.lower() == "none":
            raise InvalidTokenError("alg_none")
        if alg == DEV_ALGORITHM:
            if not self._settings.dev_auth_enabled:
                raise InvalidTokenError("dev_auth_disabled")
            payload = self._decode(
                token,
                self._settings.DEV_AUTH_SECRET.get_secret_value(),
                algorithm=DEV_ALGORITHM,
                issuer=DEV_ISSUER,
            )
            return self._claims(payload, "dev")
        if alg in SUPABASE_ALGORITHMS:
            key = await self._supabase_key(header.get("kid"))
            payload = self._decode(token, key, algorithm=alg, issuer=self._settings.JWT_ISSUER)
            return self._claims(payload, "supabase")
        raise InvalidTokenError("unsupported_alg")

    async def _supabase_key(self, kid: object) -> Any:
        if self._jwks_provider is None or not self._settings.JWT_ISSUER:
            raise InvalidTokenError("supabase_not_configured")
        if not isinstance(kid, str) or not kid:
            raise InvalidTokenError("missing_kid")
        try:
            key = await self._jwks_provider.get_signing_key(kid)
        except JWKSUnavailableError:
            raise InvalidTokenError("jwks_unavailable") from None
        if key is None:
            raise InvalidTokenError("unknown_kid")
        return key

    def _decode(self, token: str, key: Any, *, algorithm: str, issuer: str) -> dict[str, Any]:
        try:
            payload: dict[str, Any] = jwt.decode(
                token,
                key,
                algorithms=[algorithm],
                audience=self._settings.JWT_AUDIENCE,
                issuer=issuer,
                options={"require": _REQUIRED_CLAIMS},
            )
        except jwt.ExpiredSignatureError:
            raise InvalidTokenError("expired") from None
        except jwt.InvalidSignatureError:
            raise InvalidTokenError("bad_signature") from None
        except jwt.InvalidAudienceError:
            raise InvalidTokenError("bad_audience") from None
        except jwt.InvalidIssuerError:
            raise InvalidTokenError("bad_issuer") from None
        except jwt.MissingRequiredClaimError:
            raise InvalidTokenError("missing_claim") from None
        except (jwt.PyJWTError, TypeError, ValueError):
            # TypeError / ValueError: the JWKS key does not fit the algorithm in the header.
            raise InvalidTokenError("invalid_token") from None
        return payload

    @staticmethod
    def _claims(payload: dict[str, Any], source: Literal["supabase", "dev"]) -> AuthClaims:
        sub = payload["sub"]
        try:
            subject = uuid.UUID(sub) if isinstance(sub, str) else None
        except ValueError:
            subject = None
        if subject is None:
            raise InvalidTokenError("bad_subject")
        email = payload.get("email")
        return AuthClaims(
            sub=subject, email=email if isinstance(email, str) else None, source=source
        )
