import uuid
from datetime import UTC, datetime, timedelta
from typing import NamedTuple

import jwt

from app.auth.models import Role
from app.auth.verifier import DEV_ALGORITHM, DEV_ISSUER
from app.config import Settings


class DemoAccount(NamedTuple):
    id: uuid.UUID
    email: str
    display_name: str


DEMO_ACCOUNTS: dict[Role, DemoAccount] = {
    "viewer": DemoAccount(
        uuid.UUID("00000000-0000-4000-8000-00000000d001"),
        "demo-viewer@agentops.local",
        "Demo Viewer",
    ),
    "operator": DemoAccount(
        uuid.UUID("00000000-0000-4000-8000-00000000d002"),
        "demo-operator@agentops.local",
        "Demo Operator",
    ),
    "admin": DemoAccount(
        uuid.UUID("00000000-0000-4000-8000-00000000d003"),
        "demo-admin@agentops.local",
        "Demo Admin",
    ),
}


def issue_dev_token(
    settings: Settings, account: DemoAccount, *, now: datetime | None = None
) -> str:
    """Sign a dev JWT. The role is deliberately not a claim: it is always read from the database."""
    issued_at = now or datetime.now(UTC)
    claims = {
        "sub": str(account.id),
        "email": account.email,
        "iss": DEV_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "iat": issued_at,
        "exp": issued_at + timedelta(seconds=settings.DEV_JWT_TTL_SECONDS),
    }
    return jwt.encode(claims, settings.DEV_AUTH_SECRET.get_secret_value(), algorithm=DEV_ALGORITHM)
