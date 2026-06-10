"""Goods Receipt Service — receives physical stock against a Purchase Order.

Orchestrates in a single DB transaction:
  1. Validates the PO is in a receivable state (CONFIRMED or PARTIALLY_RECEIVED).
  2. For each receipt line: finds or creates an InventoryBatch, adds stock, creates
     a STOCK_IN InventoryTransaction, and increments quantity_received on the PO item.
  3. Re-computes PO status (PARTIALLY_RECEIVED or RECEIVED) based on fulfillment ratios.
  4. Single session.commit() at the end — no intermediate commits.

Bypasses InventoryBatchService deliberately — that service calls session.commit()
internally which would break the all-or-nothing guarantee here.
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.inventory_batch import BatchStatus, InventoryBatch
from app.models.inventory_transaction import InventoryTransaction, TransactionType
from app.models.purchase_order import PurchaseOrder, PurchaseOrderItem, PurchaseStatus
from app.repositories.inventory_batch import InventoryBatchRepository
from app.repositories.inventory_transaction import InventoryTransactionRepository
from app.repositories.purchase_order import PurchaseOrderItemRepository, PurchaseOrderRepository
from app.schemas.purchase_order import (
    GoodsReceiptItemResult,
    GoodsReceiptRequest,
    GoodsReceiptResponse,
)

logger = get_logger(__name__)

_RECEIVABLE = {PurchaseStatus.CONFIRMED, PurchaseStatus.PARTIALLY_RECEIVED}


class PurchaseReceiptService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._po_repo = PurchaseOrderRepository(session)
        self._item_repo = PurchaseOrderItemRepository(session)
        self._batch_repo = InventoryBatchRepository(session)
        self._txn_repo = InventoryTransactionRepository(session)

    # ── public ─────────────────────────────────────────────────────────────────

    async def receive(
        self,
        po_id: UUID,
        request: GoodsReceiptRequest,
        *,
        created_by: UUID | None,
    ) -> GoodsReceiptResponse:
        po = await self._po_repo.get_by_id_not_deleted(po_id)
        if po is None:
            raise ValueError("purchase order not found")
        if po.status not in _RECEIVABLE:
            raise ValueError(
                f"Cannot receive goods for a PO in '{po.status}' status. "
                f"PO must be CONFIRMED or PARTIALLY_RECEIVED."
            )

        results: list[GoodsReceiptItemResult] = []

        for line in request.items:
            item = await self._item_repo.get_by_id(line.purchase_order_item_id)
            if item is None:
                raise ValueError(f"PO item {line.purchase_order_item_id} not found")
            if item.purchase_order_id != po.id:
                raise ValueError(
                    f"PO item {line.purchase_order_item_id} does not belong to PO {po_id}"
                )

            batch = await self._find_or_create_batch(
                medicine_id=item.medicine_id,
                warehouse_id=line.warehouse_id,
                batch_number=line.batch_number,
                manufacturing_date=line.manufacturing_date,
                expiry_date=line.expiry_date,
                tenant_id=po.tenant_id,
            )

            # Add stock directly (no InventoryBatchService — avoids mid-tx commit)
            batch.quantity_available += line.quantity
            if batch.status == BatchStatus.EXHAUSTED:
                batch.status = BatchStatus.ACTIVE

            txn = InventoryTransaction(
                batch_id=batch.id,
                transaction_type=TransactionType.STOCK_IN,
                quantity=line.quantity,
                reference_number=request.reference_number or po.po_number,
                remarks=request.remarks,
                created_by=created_by,
            )
            await self._txn_repo.create(txn)

            item.quantity_received += line.quantity

            results.append(
                GoodsReceiptItemResult(
                    purchase_order_item_id=item.id,
                    batch_id=batch.id,
                    batch_number=batch.batch_number,
                    quantity_received=line.quantity,
                )
            )

        # Flush so item.quantity_received is visible before computing PO status
        await self._session.flush()
        new_status = self._compute_new_po_status(po)
        po.status = new_status

        await self._session.commit()
        await self._session.refresh(po)

        logger.info(
            "goods_received",
            po_id=str(po_id),
            line_count=len(results),
            new_status=new_status,
        )
        return GoodsReceiptResponse(
            purchase_order_id=po.id,
            po_number=po.po_number,
            new_status=new_status,
            items_received=results,
        )

    # ── helpers ────────────────────────────────────────────────────────────────

    async def _find_or_create_batch(
        self,
        *,
        medicine_id: UUID,
        warehouse_id: UUID,
        batch_number: str,
        manufacturing_date: date | None,
        expiry_date: date,
        tenant_id: UUID | None,
    ) -> InventoryBatch:
        existing = await self._batch_repo.get_by_batch_number(
            medicine_id=medicine_id,
            warehouse_id=warehouse_id,
            batch_number=batch_number,
        )
        if existing:
            return existing

        batch = InventoryBatch(
            medicine_id=medicine_id,
            warehouse_id=warehouse_id,
            batch_number=batch_number,
            manufacturing_date=manufacturing_date,
            expiry_date=expiry_date,
            quantity_available=0,
            quantity_reserved=0,
            quantity_damaged=0,
            status=BatchStatus.ACTIVE,
            tenant_id=tenant_id,
        )
        await self._batch_repo.add(batch)
        await self._session.flush()  # assign batch.id
        return batch

    @staticmethod
    def _compute_new_po_status(po: PurchaseOrder) -> PurchaseStatus:
        items: list[PurchaseOrderItem] = po.items
        if not items:
            return po.status

        total_ordered = sum(i.quantity_ordered for i in items)
        total_received = sum(i.quantity_received for i in items)

        if total_received == 0:
            return po.status  # nothing changed yet — shouldn't happen but be safe
        if total_received >= total_ordered:
            return PurchaseStatus.RECEIVED
        return PurchaseStatus.PARTIALLY_RECEIVED
