from __future__ import annotations

import uuid
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.purchase_order import (
    PURCHASE_STATUS_TRANSITIONS,
    PurchaseOrder,
    PurchaseOrderItem,
    PurchaseStatus,
)
from app.repositories.purchase_order import PurchaseOrderItemRepository, PurchaseOrderRepository
from app.schemas.purchase_order import PurchaseOrderCreate

logger = get_logger(__name__)


class PurchaseOrderService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = PurchaseOrderRepository(session)
        self._item_repo = PurchaseOrderItemRepository(session)

    # ── helpers ────────────────────────────────────────────────────────────────

    async def _require_po(self, po_id: UUID) -> PurchaseOrder:
        po = await self._repo.get_by_id_not_deleted(po_id)
        if not po:
            raise ValueError("purchase order not found")
        return po

    @staticmethod
    def _compute_total(items: list[PurchaseOrderItem]) -> Decimal:
        return sum(
            (item.unit_price * item.quantity_ordered for item in items),
            Decimal("0.00"),
        )

    # ── create ─────────────────────────────────────────────────────────────────

    async def create(
        self,
        data: PurchaseOrderCreate,
        *,
        tenant_id: UUID | None = None,
    ) -> PurchaseOrder:
        po_number = (data.po_number or f"PO-{uuid.uuid4().hex[:8].upper()}").strip().upper()
        if await self._repo.get_by_po_number(po_number):
            raise ValueError(f"PO number '{po_number}' already exists")

        po = PurchaseOrder(
            po_number=po_number,
            supplier_id=data.supplier_id,
            order_date=data.order_date,
            expected_delivery_date=data.expected_delivery_date,
            notes=data.notes,
            status=PurchaseStatus.DRAFT,
            total_amount=Decimal("0.00"),
            tenant_id=tenant_id,
        )
        await self._repo.add(po)
        await self._session.flush()  # get po.id before building items

        for item_data in data.items:
            item = PurchaseOrderItem(
                purchase_order_id=po.id,
                medicine_id=item_data.medicine_id,
                quantity_ordered=item_data.quantity_ordered,
                quantity_received=0,
                unit_price=item_data.unit_price,
            )
            self._session.add(item)

        await self._session.flush()
        # Compute total from input data — avoids accessing po.items before selectin loads
        po.total_amount = sum(
            (i.unit_price * i.quantity_ordered for i in data.items),
            Decimal("0.00"),
        )
        await self._session.commit()
        await self._session.refresh(po)
        logger.info("purchase_order_created", po_number=po_number)
        return po

    # ── read ───────────────────────────────────────────────────────────────────

    async def get(self, po_id: UUID) -> PurchaseOrder:
        return await self._require_po(po_id)

    async def list_all(
        self,
        *,
        supplier_id: UUID | None = None,
        status: PurchaseStatus | None = None,
    ) -> list[PurchaseOrder]:
        if supplier_id:
            return await self._repo.list_by_supplier(supplier_id)
        if status:
            return await self._repo.list_by_status(status)
        return await self._repo.list_all_not_deleted()

    # ── update ─────────────────────────────────────────────────────────────────

    async def transition_status(self, po_id: UUID, new_status: PurchaseStatus) -> PurchaseOrder:
        po = await self._require_po(po_id)
        allowed = PURCHASE_STATUS_TRANSITIONS.get(po.status, [])
        if new_status not in allowed:
            raise ValueError(
                f"Cannot transition from '{po.status}' to '{new_status}'. "
                f"Allowed: {[s.value for s in allowed]}"
            )
        po.status = new_status
        await self._session.commit()
        await self._session.refresh(po)
        logger.info("po_status_updated", po_id=str(po_id), new_status=new_status)
        return po

    async def cancel(self, po_id: UUID) -> PurchaseOrder:
        return await self.transition_status(po_id, PurchaseStatus.CANCELLED)

    # ── soft delete ────────────────────────────────────────────────────────────

    async def delete(self, po_id: UUID) -> None:
        po = await self._require_po(po_id)
        if po.status not in (PurchaseStatus.DRAFT, PurchaseStatus.CANCELLED):
            raise ValueError("Only DRAFT or CANCELLED purchase orders can be deleted")
        await self._repo.soft_delete(po)
        await self._session.commit()
        logger.info("purchase_order_deleted", po_id=str(po_id))
