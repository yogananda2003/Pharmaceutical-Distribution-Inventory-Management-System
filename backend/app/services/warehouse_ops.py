"""Warehouse Operations Service.

Three responsibilities:

transfer_stock  Move available units from one batch to another.
    Uses SELECT FOR UPDATE on both batches (deterministic lock order to prevent
    deadlocks), creates a TRANSFER InventoryTransaction for each side.
    All-or-nothing: single session.commit() at the end.

get_pending_orders  Return orders in APPROVED / ALLOCATED / PICKED / PACKED
    status — i.e. work that warehouse staff need to action.

get_pick_list  Build a pick list for an order from its OrderItemAllocations.
    Shows each order item with the batches FEFO selected, the warehouse location,
    expiry date, and quantity to pick.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.customer_order import OrderItemAllocation, OrderStatus
from app.models.inventory_batch import BatchStatus, InventoryBatch
from app.models.inventory_transaction import InventoryTransaction, TransactionType
from app.repositories.customer_order import (
    CustomerOrderRepository,
    OrderItemAllocationRepository,
    OrderItemRepository,
)
from app.repositories.inventory_batch import InventoryBatchRepository
from app.repositories.inventory_transaction import InventoryTransactionRepository
from app.schemas.warehouse_ops import (
    BatchPickInfo,
    PendingOrderSummary,
    PickListItemInfo,
    PickListResponse,
    StockTransferResponse,
)

logger = get_logger(__name__)

_PENDING_STATUSES: list[OrderStatus] = [
    OrderStatus.APPROVED,
    OrderStatus.ALLOCATED,
    OrderStatus.PICKED,
    OrderStatus.PACKED,
]

_PICK_LIST_STATUSES: set[OrderStatus] = {
    OrderStatus.APPROVED,
    OrderStatus.ALLOCATED,
    OrderStatus.PICKED,
    OrderStatus.PACKED,
}


class WarehouseOpsService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._batch_repo = InventoryBatchRepository(session)
        self._txn_repo = InventoryTransactionRepository(session)
        self._order_repo = CustomerOrderRepository(session)
        self._item_repo = OrderItemRepository(session)
        self._alloc_repo = OrderItemAllocationRepository(session)

    # ── stock transfer ─────────────────────────────────────────────────────────

    async def transfer_stock(
        self,
        source_batch_id: UUID,
        destination_batch_id: UUID,
        quantity: int,
        *,
        created_by: UUID | None,
        reference_number: str | None = None,
        remarks: str | None = None,
    ) -> StockTransferResponse:
        if source_batch_id == destination_batch_id:
            raise ValueError("Source and destination batches cannot be the same")

        # Lock in deterministic id order to prevent deadlocks under concurrent transfers.
        ids_sorted = sorted([source_batch_id, destination_batch_id], key=str)
        locked: dict[UUID, InventoryBatch | None] = {}
        for bid in ids_sorted:
            locked[bid] = await self._batch_repo.get_by_id_for_update(bid)

        source = locked[source_batch_id]
        dest = locked[destination_batch_id]

        if source is None:
            raise ValueError(f"Source batch {source_batch_id} not found")
        if dest is None:
            raise ValueError(f"Destination batch {destination_batch_id} not found")

        if source.status == BatchStatus.EXHAUSTED:
            raise ValueError("Source batch is exhausted — no available stock to transfer")
        if source.quantity_available < quantity:
            raise ValueError(
                f"Insufficient available stock in source batch: "
                f"{source.quantity_available} available, {quantity} requested"
            )

        source.quantity_available -= quantity
        if source.quantity_available == 0 and source.quantity_reserved == 0:
            source.status = BatchStatus.EXHAUSTED

        dest.quantity_available += quantity
        if dest.status == BatchStatus.EXHAUSTED:
            dest.status = BatchStatus.ACTIVE

        ref = reference_number or f"TRF-{source_batch_id.hex[:8]}"
        dest_hint = str(destination_batch_id)[:8]
        src_hint = str(source_batch_id)[:8]
        extra = f": {remarks}" if remarks else ""

        await self._txn_repo.create(
            InventoryTransaction(
                batch_id=source_batch_id,
                transaction_type=TransactionType.TRANSFER,
                quantity=quantity,
                reference_number=ref,
                remarks=f"Transfer out to {dest_hint}{extra}",
                created_by=created_by,
            )
        )
        await self._txn_repo.create(
            InventoryTransaction(
                batch_id=destination_batch_id,
                transaction_type=TransactionType.TRANSFER,
                quantity=quantity,
                reference_number=ref,
                remarks=f"Transfer in from {src_hint}{extra}",
                created_by=created_by,
            )
        )

        await self._session.commit()
        await self._session.refresh(source)
        await self._session.refresh(dest)

        logger.info(
            "stock_transferred",
            source_batch_id=str(source_batch_id),
            dest_batch_id=str(destination_batch_id),
            quantity=quantity,
        )
        return StockTransferResponse(
            source_batch_id=source_batch_id,
            destination_batch_id=destination_batch_id,
            quantity=quantity,
            reference_number=ref,
            source_quantity_available=source.quantity_available,
            destination_quantity_available=dest.quantity_available,
        )

    # ── warehouse views ────────────────────────────────────────────────────────

    async def get_pending_orders(self) -> list[PendingOrderSummary]:
        orders = await self._order_repo.list_by_statuses(_PENDING_STATUSES)
        return [
            PendingOrderSummary(
                id=o.id,
                order_number=o.order_number,
                status=o.status.value,
                total_amount=o.total_amount,
                order_date=o.order_date,
                customer_name=o.customer.business_name,
                item_count=len(o.items),
            )
            for o in orders
        ]

    async def get_pick_list(self, order_id: UUID) -> PickListResponse:
        order = await self._order_repo.get_by_id_not_deleted(order_id)
        if not order:
            raise ValueError("order not found")

        if order.status not in _PICK_LIST_STATUSES:
            raise ValueError(
                f"Pick list is only available for APPROVED/ALLOCATED/PICKED/PACKED orders; "
                f"current status: '{order.status}'"
            )

        items = await self._item_repo.list_by_order(order_id)
        allocations = await self._alloc_repo.list_by_order(order_id)

        # Group allocations by order_item_id for O(1) lookup below.
        alloc_map: dict[UUID, list[OrderItemAllocation]] = {}
        for alloc in allocations:
            alloc_map.setdefault(alloc.order_item_id, []).append(alloc)

        pick_items = []
        for item in items:
            item_allocs = alloc_map.get(item.id, [])
            batch_picks = [
                BatchPickInfo(
                    batch_id=alloc.batch_id,
                    batch_number=alloc.batch.batch_number,
                    warehouse_id=alloc.batch.warehouse_id,
                    warehouse_name=alloc.batch.warehouse.warehouse_name,
                    expiry_date=alloc.batch.expiry_date,
                    quantity_to_pick=alloc.quantity,
                )
                for alloc in item_allocs
            ]
            pick_items.append(
                PickListItemInfo(
                    order_item_id=item.id,
                    medicine_id=item.medicine_id,
                    medicine_code=item.medicine.code,
                    medicine_name=item.medicine.name,
                    total_quantity=item.quantity,
                    batches=batch_picks,
                )
            )

        return PickListResponse(
            order_id=order.id,
            order_number=order.order_number,
            customer_name=order.customer.business_name,
            order_status=order.status.value,
            items=pick_items,
        )
