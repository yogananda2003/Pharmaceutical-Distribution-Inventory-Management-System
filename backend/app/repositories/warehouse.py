from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.warehouse import Warehouse
from app.repositories.base import BaseRepository


class WarehouseRepository(BaseRepository[Warehouse]):
    model = Warehouse

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_code(self, code: str) -> Warehouse | None:
        result = await self.session.execute(
            select(Warehouse).where(
                Warehouse.warehouse_code == code,
                Warehouse.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id_not_deleted(self, warehouse_id: UUID) -> Warehouse | None:
        result = await self.session.execute(
            select(Warehouse).where(
                Warehouse.id == warehouse_id,
                Warehouse.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def list_active(self, *, limit: int = 100, offset: int = 0) -> list[Warehouse]:
        result = await self.session.execute(
            select(Warehouse)
            .where(Warehouse.deleted_at.is_(None), Warehouse.is_active.is_(True))
            .order_by(Warehouse.warehouse_name)
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())
