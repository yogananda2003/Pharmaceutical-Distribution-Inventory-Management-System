from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.user import User, UserRole
from app.repositories.user import UserRepository
from app.schemas.user import UserUpdate, UserUpdateMe

logger = get_logger(__name__)


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = UserRepository(session)

    async def get_me(self, user_id: UUID) -> User:
        user = await self._repo.get_by_id_active(user_id)
        if not user:
            raise ValueError("user not found")
        return user

    async def update_me(self, user_id: UUID, data: UserUpdateMe) -> User:
        user = await self._repo.get_by_id_active(user_id)
        if not user:
            raise ValueError("user not found")
        if data.email is not None:
            existing = await self._repo.get_by_email(data.email)
            if existing and existing.id != user_id:
                raise ValueError("email already in use")
            user.email = data.email
        await self._session.flush()
        await self._session.commit()
        logger.info("user_updated_self", user_id=str(user_id))
        return user

    async def list_users(self, *, limit: int = 100, offset: int = 0) -> list[User]:
        return list(await self._repo.list(limit=limit, offset=offset))

    async def get_user(self, user_id: UUID) -> User:
        user = await self._repo.get_by_id(user_id)
        if not user:
            raise ValueError("user not found")
        return user

    async def update_user(self, user_id: UUID, data: UserUpdate) -> User:
        user = await self._repo.get_by_id(user_id)
        if not user:
            raise ValueError("user not found")
        if data.email is not None:
            existing = await self._repo.get_by_email(data.email)
            if existing and existing.id != user_id:
                raise ValueError("email already in use")
            user.email = data.email
        if data.is_active is not None:
            user.is_active = data.is_active
        if data.role is not None:
            user.role = UserRole(data.role)
        await self._session.flush()
        await self._session.commit()
        logger.info("user_updated_by_admin", target_user_id=str(user_id))
        return user

    async def delete_user(self, user_id: UUID) -> None:
        user = await self._repo.get_by_id(user_id)
        if not user:
            raise ValueError("user not found")
        await self._repo.soft_delete(user)
        await self._session.commit()
        logger.info("user_soft_deleted", target_user_id=str(user_id))
