from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_email(self, email: str) -> User | None:
        result = await self.session.execute(
            select(User).where(User.email == email, User.deleted_at.is_(None))
        )
        return result.scalar_one_or_none()

    async def get_by_id_active(self, user_id: UUID) -> User | None:
        result = await self.session.execute(
            select(User).where(
                User.id == user_id,
                User.is_active.is_(True),
                User.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        email: str,
        password_hash: str,
        role: str,
        tenant_id: UUID | None = None,
    ) -> User:
        from app.models.user import UserRole

        user = User(
            email=email,
            password_hash=password_hash,
            role=UserRole(role),
            tenant_id=tenant_id,
        )
        return await self.add(user)

    async def update_password(self, user: User, password_hash: str) -> User:
        user.password_hash = password_hash
        await self.session.flush()
        return user

    async def set_verified(self, user: User) -> User:
        user.is_verified = True
        await self.session.flush()
        return user
