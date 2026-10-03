from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dev import DEMO_ACCOUNTS, issue_dev_token
from app.auth.models import Role
from app.config import Settings
from app.db import get_session
from app.repositories import ProfileRepository

router = APIRouter(prefix="/auth", tags=["auth"])
# Registered only when Settings.dev_auth_enabled; in other environments the path does not exist.
dev_router = APIRouter(prefix="/auth", tags=["auth"])


class AuthConfig(BaseModel):
    dev_login_enabled: bool


class DevLoginRequest(BaseModel):
    role: Role


class DevLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"  # noqa: S105 - OAuth token type, not a credential
    expires_in: int


def get_settings_from_app(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


@router.get("/config")
async def auth_config(settings: Annotated[Settings, Depends(get_settings_from_app)]) -> AuthConfig:
    return AuthConfig(dev_login_enabled=settings.dev_auth_enabled)


@dev_router.post("/dev-login")
async def dev_login(
    body: DevLoginRequest,
    settings: Annotated[Settings, Depends(get_settings_from_app)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> DevLoginResponse:
    account = DEMO_ACCOUNTS[body.role]
    await ProfileRepository(session).upsert_demo(
        account.id, account.email, account.display_name, body.role
    )
    # Commit before handing out the token so the profile exists when it is first used.
    await session.commit()
    return DevLoginResponse(
        access_token=issue_dev_token(settings, account), expires_in=settings.DEV_JWT_TTL_SECONDS
    )
