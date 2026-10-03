from fastapi import APIRouter

from app.api import auth, me, scenarios
from app.config import Settings


def create_api_router(settings: Settings) -> APIRouter:
    api_router = APIRouter(prefix="/api/v1")
    api_router.include_router(auth.router)
    if settings.dev_auth_enabled:
        api_router.include_router(auth.dev_router)
    api_router.include_router(me.router)
    api_router.include_router(scenarios.router)
    return api_router
