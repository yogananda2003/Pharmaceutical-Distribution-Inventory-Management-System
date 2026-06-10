from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.purchase_order import PurchaseOrder, PurchaseOrderItem, PurchaseStatus
from app.repositories.base import BaseRepository


class PurchaseOrderRepository(BaseRepository[PurchaseOrder]):
    model = PurchaseOrder

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_id_not_deleted(self, po_id: UUID) -> PurchaseOrder | None:
        result = await self.session.execute(
            select(PurchaseOrder).where(
                PurchaseOrder.id == po_id,
                PurchaseOrder.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_po_number(self, po_number: str) -> PurchaseOrder | None:
        result = await self.session.execute(
            select(PurchaseOrder).where(
                PurchaseOrder.po_number == po_number,
                PurchaseOrder.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def list_by_status(self, status: PurchaseStatus) -> list[PurchaseOrder]:
        result = await self.session.execute(
            select(PurchaseOrder).where(
                PurchaseOrder.status == status,
                PurchaseOrder.deleted_at.is_(None),
            )
        )
        return list(result.scalars().all())

    async def list_by_supplier(self, supplier_id: UUID) -> list[PurchaseOrder]:
        result = await self.session.execute(
            select(PurchaseOrder).where(
                PurchaseOrder.supplier_id == supplier_id,
                PurchaseOrder.deleted_at.is_(None),
            )
        )
        return list(result.scalars().all())

    async def list_all_not_deleted(self) -> list[PurchaseOrder]:
        result = await self.session.execute(
            select(PurchaseOrder).where(PurchaseOrder.deleted_at.is_(None))
        )
        return list(result.scalars().all())


class PurchaseOrderItemRepository:
    """Standalone repo — PurchaseOrderItem does not extend BaseEntity (no soft delete)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, item_id: UUID) -> PurchaseOrderItem | None:
        result = await self.session.execute(
            select(PurchaseOrderItem).where(PurchaseOrderItem.id == item_id)
        )
        return result.scalar_one_or_none()
