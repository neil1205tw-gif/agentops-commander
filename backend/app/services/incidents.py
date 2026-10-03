import uuid
from dataclasses import dataclass

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser
from app.models import Incident
from app.repositories import IncidentEventRepository, IncidentRepository
from app.scenarios import ScenarioRegistry
from app.schemas import (
    IncidentCreate,
    IncidentDetail,
    IncidentEventList,
    IncidentEventOut,
    IncidentList,
    IncidentStatus,
    IncidentSummary,
)

logger = structlog.get_logger(__name__)


class IncidentNotFoundError(Exception):
    """The incident does not exist or is not visible to the caller (indistinguishable by design)."""


class IncidentForbiddenError(Exception):
    """The caller may see the incident or the endpoint but is not allowed to perform the action."""


class UnknownScenarioError(Exception):
    """The requested scenario_key is not in the registry."""


@dataclass(frozen=True)
class VisibilityScope:
    """Which non-deleted incidents a user may read; the single source of the visibility rule.

    owner_id=None with include_public=False means unrestricted (admin).
    """

    owner_id: uuid.UUID | None
    include_public: bool

    def allows(self, incident: Incident) -> bool:
        if incident.deleted_at is not None:
            return False
        if self.owner_id is None and not self.include_public:
            return True
        if self.owner_id is not None and incident.owner_id == self.owner_id:
            return True
        return self.include_public and incident.is_public


def visibility_scope(user: CurrentUser) -> VisibilityScope:
    """viewer: public only; operator: own plus public; admin: everything (deleted never)."""
    if user.role == "admin":
        return VisibilityScope(owner_id=None, include_public=False)
    if user.role == "operator":
        return VisibilityScope(owner_id=user.id, include_public=True)
    return VisibilityScope(owner_id=None, include_public=True)


class IncidentService:
    """Authorization and transaction boundary for incidents.

    Every write appends its event and then commits, so the incident change and its event land
    together; any failure before the commit leaves nothing behind (the session is rolled back).
    The commit is explicit so the data is durable before the response is sent.
    """

    def __init__(self, session: AsyncSession, registry: ScenarioRegistry) -> None:
        self._session = session
        self._registry = registry
        self._incidents = IncidentRepository(session)
        self._events = IncidentEventRepository(session)

    async def create(self, user: CurrentUser, body: IncidentCreate) -> IncidentDetail:
        if user.role == "viewer":
            raise IncidentForbiddenError
        scenario = self._registry.get(body.scenario_key)
        if scenario is None:
            raise UnknownScenarioError
        incident = await self._incidents.create(
            owner_id=user.id,
            scenario_key=scenario.key,
            title=body.title or scenario.default_title,
            affected_services=list(scenario.affected_services),
        )
        await self._events.append(
            incident.id,
            "incident.created",
            f"Incident created from scenario {scenario.key}",
            payload={"scenario_key": scenario.key, "created_by": str(user.id)},
        )
        detail = self._detail(incident)
        await self._session.commit()
        logger.info("incident_created", incident_id=str(incident.id), scenario_key=scenario.key)
        return detail

    async def list(
        self, user: CurrentUser, *, status: IncidentStatus | None, limit: int, offset: int
    ) -> IncidentList:
        scope = visibility_scope(user)
        incidents = await self._incidents.list(
            owner_id=scope.owner_id,
            include_public=scope.include_public,
            status=status,
            limit=limit,
            offset=offset,
        )
        total = await self._incidents.count(
            owner_id=scope.owner_id, include_public=scope.include_public, status=status
        )
        return IncidentList(
            items=[IncidentSummary.model_validate(incident) for incident in incidents],
            total=total,
            limit=limit,
            offset=offset,
        )

    async def get(self, user: CurrentUser, incident_id: uuid.UUID) -> IncidentDetail:
        return self._detail(await self._get_visible(user, incident_id))

    async def list_events(self, user: CurrentUser, incident_id: uuid.UUID) -> IncidentEventList:
        await self._get_visible(user, incident_id)
        events = await self._events.list_for_incident(incident_id)
        return IncidentEventList(items=[IncidentEventOut.model_validate(e) for e in events])

    async def delete(self, user: CurrentUser, incident_id: uuid.UUID) -> None:
        if user.role == "viewer":
            raise IncidentForbiddenError
        incident = await self._get_visible(user, incident_id)
        if user.role != "admin" and incident.owner_id != user.id:
            raise IncidentForbiddenError
        if await self._incidents.soft_delete(incident_id) is None:
            raise IncidentNotFoundError
        await self._events.append(
            incident_id,
            "incident.deleted",
            "Incident deleted",
            payload={"deleted_by": str(user.id)},
        )
        await self._session.commit()
        logger.info("incident_deleted", incident_id=str(incident_id))

    async def set_visibility(
        self, user: CurrentUser, incident_id: uuid.UUID, is_public: bool
    ) -> IncidentDetail:
        if user.role != "admin":
            raise IncidentForbiddenError
        was_public = (await self._get_visible(user, incident_id)).is_public
        incident = await self._incidents.set_public(incident_id, is_public)
        if incident is None:
            raise IncidentNotFoundError
        await self._events.append(
            incident_id,
            "incident.visibility_changed",
            f"Incident visibility changed to {'public' if is_public else 'private'}",
            payload={
                "old_is_public": was_public,
                "new_is_public": is_public,
                "changed_by": str(user.id),
            },
        )
        detail = self._detail(incident)
        await self._session.commit()
        logger.info(
            "incident_visibility_changed", incident_id=str(incident_id), is_public=is_public
        )
        return detail

    async def _get_visible(self, user: CurrentUser, incident_id: uuid.UUID) -> Incident:
        incident = await self._incidents.get(incident_id)
        if incident is None or not visibility_scope(user).allows(incident):
            raise IncidentNotFoundError
        return incident

    def _detail(self, incident: Incident) -> IncidentDetail:
        scenario = self._registry.get(incident.scenario_key)
        summary = IncidentSummary.model_validate(incident)
        return IncidentDetail(
            **summary.model_dump(),
            resolved_at=incident.resolved_at,
            alert=scenario.alert if scenario is not None else None,
        )
