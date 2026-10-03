import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import IncidentEvent


class IncidentEventRepository:
    """Append-only access; there is intentionally no update or delete method."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def append(
        self,
        incident_id: uuid.UUID,
        event_type: str,
        summary: str,
        agent_name: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> IncidentEvent:
        # clock_timestamp() (not the transaction-wide now()) keeps events appended within one
        # transaction ordered by their append order.
        statement = (
            insert(IncidentEvent)
            .values(
                incident_id=incident_id,
                event_type=event_type,
                summary=summary,
                agent_name=agent_name,
                payload=payload if payload is not None else {},
                created_at=func.clock_timestamp(),
            )
            .returning(IncidentEvent)
        )
        result = await self._session.scalars(
            statement, execution_options={"populate_existing": True}
        )
        return result.one()

    async def list_for_incident(self, incident_id: uuid.UUID) -> Sequence[IncidentEvent]:
        statement = (
            select(IncidentEvent)
            .where(IncidentEvent.incident_id == incident_id)
            .order_by(IncidentEvent.created_at.asc(), IncidentEvent.id.asc())
        )
        result = await self._session.scalars(statement)
        return result.all()
