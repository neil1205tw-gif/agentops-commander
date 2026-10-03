import uuid

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Profile


class ProfileRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, profile_id: uuid.UUID) -> Profile | None:
        return await self._session.get(Profile, profile_id)

    async def get_by_email(self, email: str) -> Profile | None:
        statement = select(Profile).where(func.lower(Profile.email) == email.lower())
        return await self._session.scalar(statement)

    async def create(
        self,
        profile_id: uuid.UUID,
        email: str | None,
        display_name: str | None,
        role: str = "viewer",
    ) -> Profile:
        profile = Profile(id=profile_id, email=email, display_name=display_name, role=role)
        self._session.add(profile)
        await self._session.flush()
        return profile

    async def upsert_demo(
        self,
        profile_id: uuid.UUID,
        email: str | None,
        display_name: str | None,
        role: str,
    ) -> Profile:
        """Insert the profile, or update email, display_name and role when the id exists."""
        values = {"email": email, "display_name": display_name, "role": role}
        statement = (
            insert(Profile)
            .values(id=profile_id, **values)
            .on_conflict_do_update(index_elements=[Profile.id], set_=values)
            .returning(Profile)
        )
        result = await self._session.scalars(
            statement, execution_options={"populate_existing": True}
        )
        return result.one()

    async def set_role(self, profile_id: uuid.UUID, role: str) -> Profile | None:
        profile = await self.get(profile_id)
        if profile is None:
            return None
        profile.role = role
        await self._session.flush()
        return profile
