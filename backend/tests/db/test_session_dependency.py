import uuid

import httpx
import pytest
from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.db import create_session_factory, get_session
from app.models import Profile
from app.repositories import ProfileRepository


def _build_app(engine: AsyncEngine) -> FastAPI:
    app = FastAPI()
    app.state.session_factory = create_session_factory(engine)

    @app.post("/profiles/{profile_id}")
    async def create_profile(
        profile_id: uuid.UUID, fail: str = "", session: AsyncSession = Depends(get_session)
    ) -> dict[str, str]:
        await ProfileRepository(session).create(profile_id, None, None)
        if fail == "http":
            raise HTTPException(status_code=409, detail="conflict")
        if fail == "crash":
            raise RuntimeError("boom")
        return {"id": str(profile_id)}

    return app


async def _count(session: AsyncSession) -> int:
    return (await session.scalar(select(func.count()).select_from(Profile))) or 0


async def test_commits_on_success(async_engine: AsyncEngine, session: AsyncSession) -> None:
    transport = httpx.ASGITransport(app=_build_app(async_engine))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(f"/profiles/{uuid.uuid4()}")
    assert response.status_code == 200
    assert await _count(session) == 1


@pytest.mark.parametrize("fail", ["http", "crash"])
async def test_rolls_back_on_error(
    async_engine: AsyncEngine, session: AsyncSession, fail: str
) -> None:
    transport = httpx.ASGITransport(app=_build_app(async_engine), raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(f"/profiles/{uuid.uuid4()}", params={"fail": fail})
    assert response.status_code in (409, 500)
    assert await _count(session) == 0
