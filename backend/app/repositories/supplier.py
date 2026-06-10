from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.supplier import Supplier
from app.repositories.base import BaseRepository


class SupplierRepository(BaseRepository[Supplier]):
    model = Supplier

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_code(self, code: str) -> Supplier | None:
        result = await self.session.execute(
            select(Supplier).where(
                Supplier.supplier_code == code,
                Supplier.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id_not_deleted(self, supplier_id: UUID) -> Supplier | None:
        result = await self.session.execute(
            select(Supplier).where(
                Supplier.id == supplier_id,
                Supplier.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()
