import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser, get_current_user
from app.db import get_session
from app.scenarios import ScenarioRegistry
from app.schemas import (
    IncidentCreate,
    IncidentDetail,
    IncidentEventList,
    IncidentList,
    IncidentStatus,
    VisibilityUpdate,
)
from app.services import (
    IncidentForbiddenError,
    IncidentNotFoundError,
    IncidentService,
    UnknownScenarioError,
)

router = APIRouter(prefix="/incidents", tags=["incidents"])


def get_incident_service(
    request: Request, session: Annotated[AsyncSession, Depends(get_session)]
) -> IncidentService:
    registry: ScenarioRegistry = request.app.state.scenario_registry
    return IncidentService(session, registry)


User = Annotated[CurrentUser, Depends(get_current_user)]
Service = Annotated[IncidentService, Depends(get_incident_service)]


def _not_found() -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, detail="Incident not found")


def _forbidden() -> HTTPException:
    return HTTPException(status.HTTP_403_FORBIDDEN, detail="Insufficient role")


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_incident(body: IncidentCreate, user: User, service: Service) -> IncidentDetail:
    try:
        return await service.create(user, body)
    except IncidentForbiddenError:
        raise _forbidden() from None
    except UnknownScenarioError:
        raise HTTPException(422, detail="Unknown scenario_key") from None


@router.get("")
async def list_incidents(
    user: User,
    service: Service,
    status_filter: Annotated[IncidentStatus | None, Query(alias="status")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> IncidentList:
    return await service.list(user, status=status_filter, limit=limit, offset=offset)


@router.get("/{incident_id}")
async def get_incident(incident_id: uuid.UUID, user: User, service: Service) -> IncidentDetail:
    try:
        return await service.get(user, incident_id)
    except IncidentNotFoundError:
        raise _not_found() from None


@router.get("/{incident_id}/events")
async def list_incident_events(
    incident_id: uuid.UUID, user: User, service: Service
) -> IncidentEventList:
    try:
        return await service.list_events(user, incident_id)
    except IncidentNotFoundError:
        raise _not_found() from None


@router.delete("/{incident_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_incident(incident_id: uuid.UUID, user: User, service: Service) -> None:
    try:
        await service.delete(user, incident_id)
    except IncidentForbiddenError:
        raise _forbidden() from None
    except IncidentNotFoundError:
        raise _not_found() from None


@router.patch("/{incident_id}/visibility")
async def update_incident_visibility(
    incident_id: uuid.UUID, body: VisibilityUpdate, user: User, service: Service
) -> IncidentDetail:
    try:
        return await service.set_visibility(user, incident_id, body.is_public)
    except IncidentForbiddenError:
        raise _forbidden() from None
    except IncidentNotFoundError:
        raise _not_found() from None
