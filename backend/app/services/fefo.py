"""FEFO (First-Expiry-First-Out) allocation engine.

Allocates stock across batches in expiry-date order (earliest first), skipping
expired batches. The operation is all-or-nothing: if the full requested quantity
cannot be fulfilled, no stock is reserved and the request fails.

Concurrency safety: each batch is locked with SELECT ... FOR UPDATE before its
quantities are modified. Inventory state is re-validated after the lock is
acquired so that concurrent allocations see consistent data.
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory_batch import BatchStatus
from app.models.inventory_transaction import InventoryTransaction, TransactionType
from app.repositories.inventory_batch import InventoryBatchRepository
from app.repositories.inventory_transaction import InventoryTransactionRepository
from app.schemas.fefo import (
    BatchAllocationDetail,
    FEFOAllocationRequest,
    FEFOAllocationResponse,
    FEFOReleaseRequest,
)


class FEFOService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._batch_repo = InventoryBatchRepository(session)
        self._txn_repo = InventoryTransactionRepository(session)

    async def allocate(
        self,
        request: FEFOAllocationRequest,
        *,
        created_by: UUID | None,
        today: date | None = None,
    ) -> FEFOAllocationResponse:
        effective_today = today or date.today()

        # Step 1: Optimistic pre-check — no locks, fail fast if obviously insufficient.
        candidates = await self._batch_repo.list_allocatable_fefo(
            request.medicine_id,
            effective_today,
            warehouse_id=request.warehouse_id,
        )
        total_optimistic = sum(b.quantity_available for b in candidates)
        if total_optimistic < request.quantity:
            raise ValueError(
                f"Insufficient stock: {total_optimistic} unit(s) available across all "
                f"valid batches, {request.quantity} requested"
            )

        # Step 2: Allocate from earliest-expiry batch first, locking each row.
        remaining = request.quantity
        allocations: list[BatchAllocationDetail] = []

        for candidate in candidates:
            if remaining <= 0:
                break

            batch = await self._batch_repo.get_by_id_for_update(candidate.id)
            if batch is None:
                continue

            # Re-validate after acquiring the lock (concurrent writes may have changed state).
            if (
                batch.expiry_date < effective_today
                or batch.quantity_available <= 0
                or batch.status != BatchStatus.ACTIVE
                or batch.deleted_at is not None
            ):
                continue

            qty_to_take = min(remaining, batch.quantity_available)
            batch.quantity_available -= qty_to_take
            batch.quantity_reserved += qty_to_take

            txn = InventoryTransaction(
                batch_id=batch.id,
                transaction_type=TransactionType.ALLOCATION,
                quantity=qty_to_take,
                reference_number=request.reference_number,
                remarks=request.remarks,
                created_by=created_by,
            )
            await self._txn_repo.create(txn)

            allocations.append(
                BatchAllocationDetail(
                    batch_id=batch.id,
                    batch_number=batch.batch_number,
                    expiry_date=batch.expiry_date,
                    quantity_allocated=qty_to_take,
                )
            )
            remaining -= qty_to_take

        # Step 3: All-or-nothing — if still short (race condition), rollback by raising.
        if remaining > 0:
            raise ValueError(
                f"Could only secure {request.quantity - remaining} of "
                f"{request.quantity} requested unit(s); "
                "concurrent stock changes reduced availability"
            )

        await self._session.commit()
        return FEFOAllocationResponse(
            medicine_id=request.medicine_id,
            total_quantity_requested=request.quantity,
            total_quantity_allocated=request.quantity,
            allocations=allocations,
        )

    async def release_allocation(
        self,
        request: FEFOReleaseRequest,
        *,
        created_by: UUID | None,
    ) -> None:
        """Releases a previous FEFO allocation back to available stock.

        Each item in request.allocations must correspond to a batch that was
        previously allocated. The operation is all-or-nothing.
        """
        for item in request.allocations:
            batch = await self._batch_repo.get_by_id_for_update(item.batch_id)
            if batch is None:
                raise ValueError(f"Batch {item.batch_id} not found")
            if item.quantity > batch.quantity_reserved:
                raise ValueError(
                    f"Cannot release {item.quantity} unit(s) from batch "
                    f"{item.batch_id} — only {batch.quantity_reserved} reserved"
                )
            batch.quantity_reserved -= item.quantity
            batch.quantity_available += item.quantity
            txn = InventoryTransaction(
                batch_id=batch.id,
                transaction_type=TransactionType.RELEASE,
                quantity=item.quantity,
                reference_number=request.reference_number,
                remarks=request.remarks,
                created_by=created_by,
            )
            await self._txn_repo.create(txn)

        await self._session.commit()
