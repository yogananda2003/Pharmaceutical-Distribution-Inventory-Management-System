"""Order Fulfillment Service — stock-touching order lifecycle transitions.

Three operations, each in a single DB transaction:

approve_order  PLACED → APPROVED
    FEFO-allocates stock for every order item:
    available → reserved (ALLOCATION transactions + OrderItemAllocation records).
    All-or-nothing: any item failing to allocate rolls back the whole approval.

dispatch_order  PACKED → DISPATCHED
    Converts reservations to stock reductions for every OrderItemAllocation:
    reserved → 0 (STOCK_OUT transactions).  Allocations records deleted after.

cancel_order  any cancellable status → CANCELLED
    If order was in a reserved state (APPROVED/ALLOCATED/PICKED/PACKED):
    reverses reserved quantities back to available (RELEASE transactions).
    Allocation records deleted after.

All three bypass CustomerOrderService/InventoryBatchService to avoid
intermediate session.commit() calls that would break atomicity.
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.customer_order import (
    CANCELLABLE_STATUSES,
    RESERVED_STATUSES,
    CustomerOrder,
    OrderItemAllocation,
    OrderStatus,
)
from app.models.inventory_batch import BatchStatus
from app.models.inventory_transaction import InventoryTransaction, TransactionType
from app.repositories.customer_order import (
    CustomerOrderRepository,
    OrderItemAllocationRepository,
    OrderItemRepository,
)
from app.repositories.inventory_batch import InventoryBatchRepository
from app.repositories.inventory_transaction import InventoryTransactionRepository

logger = get_logger(__name__)


class OrderFulfillmentService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._order_repo = CustomerOrderRepository(session)
        self._item_repo = OrderItemRepository(session)
        self._alloc_repo = OrderItemAllocationRepository(session)
        self._batch_repo = InventoryBatchRepository(session)
        self._txn_repo = InventoryTransactionRepository(session)

    # ── approve ────────────────────────────────────────────────────────────────

    async def approve_order(
        self,
        order_id: UUID,
        *,
        created_by: UUID | None,
        today: date | None = None,
    ) -> CustomerOrder:
        order = await self._require_order(order_id)
        if order.status != OrderStatus.PLACED:
            raise ValueError(f"Order must be PLACED to approve; current status: '{order.status}'")

        effective_today = today or date.today()
        items = await self._item_repo.list_by_order(order_id)

        # Pre-check: enough stock available for every item?
        for item in items:
            candidates = await self._batch_repo.list_allocatable_fefo(
                item.medicine_id, effective_today
            )
            total_available = sum(b.quantity_available for b in candidates)
            if total_available < item.quantity:
                raise ValueError(
                    f"Insufficient stock for medicine {item.medicine_id}: "
                    f"{total_available} available, {item.quantity} required"
                )

        # Allocate per item — FEFO, SELECT FOR UPDATE per batch
        for item in items:
            remaining = item.quantity
            candidates = await self._batch_repo.list_allocatable_fefo(
                item.medicine_id, effective_today
            )

            for candidate in candidates:
                if remaining <= 0:
                    break
                batch = await self._batch_repo.get_by_id_for_update(candidate.id)
                if batch is None:
                    continue
                if (
                    batch.expiry_date < effective_today
                    or batch.quantity_available <= 0
                    or batch.status != BatchStatus.ACTIVE
                    or batch.deleted_at is not None
                ):
                    continue

                qty = min(remaining, batch.quantity_available)
                batch.quantity_available -= qty
                batch.quantity_reserved += qty

                txn = InventoryTransaction(
                    batch_id=batch.id,
                    transaction_type=TransactionType.ALLOCATION,
                    quantity=qty,
                    reference_number=order.order_number,
                    remarks=f"Order approval: {order.order_number}",
                    created_by=created_by,
                )
                await self._txn_repo.create(txn)

                alloc = OrderItemAllocation(
                    order_item_id=item.id,
                    batch_id=batch.id,
                    quantity=qty,
                )
                self._session.add(alloc)
                remaining -= qty

            if remaining > 0:
                raise ValueError(
                    f"Could only secure {item.quantity - remaining} of {item.quantity} "
                    f"units for medicine {item.medicine_id} (concurrent changes)"
                )

        order.status = OrderStatus.APPROVED
        await self._session.commit()
        await self._session.refresh(order)
        logger.info("order_approved", order_id=str(order_id))
        return order

    # ── dispatch ───────────────────────────────────────────────────────────────

    async def dispatch_order(
        self,
        order_id: UUID,
        *,
        created_by: UUID | None,
    ) -> CustomerOrder:
        order = await self._require_order(order_id)
        if order.status != OrderStatus.PACKED:
            raise ValueError(f"Order must be PACKED to dispatch; current status: '{order.status}'")

        allocations = await self._alloc_repo.list_by_order(order_id)
        if not allocations:
            raise ValueError("No stock allocations found for this order; cannot dispatch")

        for alloc in allocations:
            batch = await self._batch_repo.get_by_id_for_update(alloc.batch_id)
            if batch is None:
                raise ValueError(f"Batch {alloc.batch_id} not found")
            if alloc.quantity > batch.quantity_reserved:
                raise ValueError(
                    f"Batch {alloc.batch_id} has only {batch.quantity_reserved} reserved "
                    f"but dispatch needs {alloc.quantity}"
                )

            batch.quantity_reserved -= alloc.quantity
            if batch.quantity_available == 0 and batch.quantity_reserved == 0:
                batch.status = BatchStatus.EXHAUSTED

            txn = InventoryTransaction(
                batch_id=batch.id,
                transaction_type=TransactionType.STOCK_OUT,
                quantity=alloc.quantity,
                reference_number=order.order_number,
                remarks=f"Order dispatch: {order.order_number}",
                created_by=created_by,
            )
            await self._txn_repo.create(txn)

        await self._alloc_repo.delete_by_order(order_id)
        order.status = OrderStatus.DISPATCHED
        await self._session.commit()
        await self._session.refresh(order)
        logger.info("order_dispatched", order_id=str(order_id))
        return order

    # ── cancel ─────────────────────────────────────────────────────────────────

    async def cancel_order(
        self,
        order_id: UUID,
        *,
        created_by: UUID | None,
    ) -> CustomerOrder:
        order = await self._require_order(order_id)
        if order.status not in CANCELLABLE_STATUSES:
            raise ValueError(f"Order in '{order.status}' status cannot be cancelled")

        # Release any reserved stock
        if order.status in RESERVED_STATUSES:
            allocations = await self._alloc_repo.list_by_order(order_id)
            for alloc in allocations:
                batch = await self._batch_repo.get_by_id_for_update(alloc.batch_id)
                if batch is None:
                    continue
                batch.quantity_reserved -= alloc.quantity
                batch.quantity_available += alloc.quantity
                if batch.status == BatchStatus.EXHAUSTED:
                    batch.status = BatchStatus.ACTIVE

                txn = InventoryTransaction(
                    batch_id=batch.id,
                    transaction_type=TransactionType.RELEASE,
                    quantity=alloc.quantity,
                    reference_number=order.order_number,
                    remarks=f"Order cancellation: {order.order_number}",
                    created_by=created_by,
                )
                await self._txn_repo.create(txn)

            await self._alloc_repo.delete_by_order(order_id)

        order.status = OrderStatus.CANCELLED
        await self._session.commit()
        await self._session.refresh(order)
        logger.info("order_cancelled", order_id=str(order_id))
        return order

    # ── helper ─────────────────────────────────────────────────────────────────

    async def _require_order(self, order_id: UUID) -> CustomerOrder:
        order = await self._order_repo.get_by_id_not_deleted(order_id)
        if not order:
            raise ValueError("order not found")
        return order
