from collections.abc import Sequence
from datetime import UTC, datetime
from typing import TypeVar
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import BaseEntity

ModelT = TypeVar("ModelT", bound=BaseEntity)


class BaseRepository[ModelT: BaseEntity]:
    """Plain data access for a single entity type. No business rules belong here —
    that's the service layer's job (see Clean Architecture layering in SKILL.md).
    """

    model: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, entity_id: UUID) -> ModelT | None:
        return await self.session.get(self.model, entity_id)

    async def list(self, *, limit: int = 100, offset: int = 0) -> Sequence[ModelT]:
        stmt = (
            select(self.model)
            .where(self.model.deleted_at.is_(None))
            .order_by(self.model.created_at)
            .limit(limit)
            .offset(offset)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def add(self, entity: ModelT) -> ModelT:
        self.session.add(entity)
        await self.session.flush()
        return entity

    async def delete(self, entity: ModelT) -> None:
        """Hard delete — only for entities with no audit/ledger requirement."""
        await self.session.delete(entity)
        await self.session.flush()

    async def soft_delete(self, entity: ModelT) -> ModelT:
        entity.deleted_at = datetime.now(UTC)
        await self.session.flush()
        return entity
