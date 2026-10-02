from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncEngine

from app.db import check_database

router = APIRouter(prefix="/health", tags=["health"])


def get_engine(request: Request) -> AsyncEngine:
    engine: AsyncEngine = request.app.state.engine
    return engine


@router.get("/live")
async def live() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
async def ready(
    response: Response, engine: Annotated[AsyncEngine, Depends(get_engine)]
) -> dict[str, object]:
    if await check_database(engine):
        return {"status": "ready", "checks": {"app": "ok", "database": "ok"}}
    response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {"status": "not_ready", "checks": {"app": "ok", "database": "error"}}
