import uuid
from collections.abc import Sequence

from sqlalchemy import ColumnElement, and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Incident


def _conditions(
    *,
    owner_id: uuid.UUID | None,
    include_public: bool,
    is_public: bool | None,
    status: str | None,
) -> ColumnElement[bool]:
    """Visibility (deleted_at IS NULL AND (owner OR public)) plus optional extra filters.

    With owner_id=None and include_public=False no visibility restriction applies (admin).
    """
    conditions: list[ColumnElement[bool]] = [Incident.deleted_at.is_(None)]
    visible: list[ColumnElement[bool]] = []
    if owner_id is not None:
        visible.append(Incident.owner_id == owner_id)
    if include_public:
        visible.append(Incident.is_public.is_(True))
    if visible:
        conditions.append(or_(*visible))
    if is_public is not None:
        conditions.append(Incident.is_public.is_(is_public))
    if status is not None:
        conditions.append(Incident.status == status)
    return and_(*conditions)


class IncidentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        owner_id: uuid.UUID,
        scenario_key: str,
        title: str,
        affected_services: list[str] | None = None,
        severity: str | None = None,
    ) -> Incident:
        incident = Incident(
            owner_id=owner_id,
            scenario_key=scenario_key,
            title=title,
            severity=severity,
            affected_services=affected_services or [],
        )
        self._session.add(incident)
        await self._session.flush()
        return incident

    async def get(self, incident_id: uuid.UUID, include_deleted: bool = False) -> Incident | None:
        statement = select(Incident).where(Incident.id == incident_id)
        if not include_deleted:
            statement = statement.where(Incident.deleted_at.is_(None))
        return await self._session.scalar(statement.execution_options(populate_existing=True))

    async def list(
        self,
        *,
        owner_id: uuid.UUID | None = None,
        include_public: bool = False,
        is_public: bool | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Sequence[Incident]:
        statement = (
            select(Incident)
            .where(
                _conditions(
                    owner_id=owner_id,
                    include_public=include_public,
                    is_public=is_public,
                    status=status,
                )
            )
            .order_by(Incident.created_at.desc(), Incident.id.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await self._session.scalars(statement)
        return result.all()

    async def count(
        self,
        *,
        owner_id: uuid.UUID | None = None,
        include_public: bool = False,
        is_public: bool | None = None,
        status: str | None = None,
    ) -> int:
        statement = (
            select(func.count())
            .select_from(Incident)
            .where(
                _conditions(
                    owner_id=owner_id,
                    include_public=include_public,
                    is_public=is_public,
                    status=status,
                )
            )
        )
        return (await self._session.scalar(statement)) or 0

    async def soft_delete(self, incident_id: uuid.UUID) -> Incident | None:
        return await self._update(incident_id, deleted_at=func.now(), updated_at=func.now())

    async def set_public(self, incident_id: uuid.UUID, is_public: bool) -> Incident | None:
        return await self._update(incident_id, is_public=is_public, updated_at=func.now())

    async def touch(self, incident_id: uuid.UUID) -> Incident | None:
        return await self._update(incident_id, updated_at=func.now())

    async def _update(self, incident_id: uuid.UUID, **values: object) -> Incident | None:
        """Update a non-deleted incident and return the refreshed row, or None if not found."""
        statement = (
            update(Incident)
            .where(Incident.id == incident_id, Incident.deleted_at.is_(None))
            .values(**values)
            .returning(Incident)
            .execution_options(populate_existing=True)
        )
        return await self._session.scalar(statement)
