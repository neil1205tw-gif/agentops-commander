from collections.abc import Awaitable, Callable
from typing import Annotated

import structlog
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.errors import InvalidTokenError, unauthorized
from app.auth.models import ROLE_LEVELS, CurrentUser, Role
from app.auth.verifier import TokenVerifier
from app.db import get_session
from app.repositories import ProfileRepository

logger = structlog.get_logger(__name__)

# auto_error=False so that a missing header yields the same 401 as an invalid token.
_bearer = HTTPBearer(auto_error=False)


def get_token_verifier(request: Request) -> TokenVerifier:
    verifier: TokenVerifier = request.app.state.token_verifier
    return verifier


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    verifier: Annotated[TokenVerifier, Depends(get_token_verifier)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> CurrentUser:
    """Authenticate the bearer token and load the profile; the role comes only from the database."""
    if credentials is None:
        logger.warning("token_rejected", reason="missing_credentials")
        raise unauthorized()
    try:
        claims = await verifier.verify(credentials.credentials)
    except InvalidTokenError:
        raise unauthorized() from None
    repository = ProfileRepository(session)
    profile = await repository.get(claims.sub)
    if profile is None:
        profile = await repository.create_if_absent(claims.sub, claims.email, None)
    if profile is None:
        # The id is new but its email is held by another profile: sign in without an email.
        profile = await repository.create_if_absent(claims.sub, None, None)
    if profile is None:
        raise unauthorized()
    return CurrentUser.model_validate(profile, from_attributes=True)


def require_role(*roles: Role) -> Callable[[CurrentUser], Awaitable[CurrentUser]]:
    """Dependency factory: allow users whose role is at least the lowest of `roles`."""
    if not roles or any(role not in ROLE_LEVELS for role in roles):
        raise ValueError("require_role needs one or more of: viewer, operator, admin")
    minimum = min(ROLE_LEVELS[role] for role in roles)

    async def dependency(user: Annotated[CurrentUser, Depends(get_current_user)]) -> CurrentUser:
        if ROLE_LEVELS[user.role] < minimum:
            raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return user

    return dependency
