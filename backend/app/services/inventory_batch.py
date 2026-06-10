from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory_batch import BatchStatus, InventoryBatch
from app.models.inventory_transaction import InventoryTransaction, TransactionType
from app.repositories.inventory_batch import InventoryBatchRepository
from app.repositories.inventory_transaction import InventoryTransactionRepository
from app.schemas.inventory_batch import (
    AdjustRequest,
    AllocateRequest,
    BatchCreate,
    DamageRequest,
    ReleaseRequest,
    StockInRequest,
    StockOutRequest,
)


class InventoryBatchService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._batch_repo = InventoryBatchRepository(session)
        self._txn_repo = InventoryTransactionRepository(session)

    # ── private helpers ───────────────────────────────────────────────────────

    async def _require_batch(self, batch_id: UUID) -> InventoryBatch:
        batch = await self._batch_repo.get_by_id_for_update(batch_id)
        if batch is None:
            raise ValueError(f"Inventory batch {batch_id} not found")
        return batch

    def _check_not_expired(self, batch: InventoryBatch, today: date) -> None:
        """Rule 2: expired inventory cannot be sold/allocated."""
        if batch.expiry_date < today:
            raise ValueError(
                f"Batch {batch.id} expired on {batch.expiry_date} — "
                "cannot allocate or sell expired stock"
            )

    def _record(
        self,
        batch_id: UUID,
        txn_type: TransactionType,
        quantity: int,
        *,
        reference_number: str | None,
        remarks: str | None,
        created_by: UUID | None,
    ) -> InventoryTransaction:
        """Rule 3: every movement creates a transaction record."""
        return InventoryTransaction(
            batch_id=batch_id,
            transaction_type=txn_type,
            quantity=quantity,
            reference_number=reference_number,
            remarks=remarks,
            created_by=created_by,
        )

    # ── public operations (each runs inside the caller's DB transaction) ──────

    async def create_batch(
        self,
        data: BatchCreate,
        *,
        tenant_id: UUID | None,
        created_by: UUID | None,
    ) -> InventoryBatch:
        existing = await self._batch_repo.get_by_batch_number(
            data.medicine_id, data.warehouse_id, data.batch_number
        )
        if existing is not None:
            raise ValueError(
                f"Batch '{data.batch_number}' already exists for this medicine/warehouse"
            )

        batch = InventoryBatch(
            medicine_id=data.medicine_id,
            warehouse_id=data.warehouse_id,
            batch_number=data.batch_number,
            manufacturing_date=data.manufacturing_date,
            expiry_date=data.expiry_date,
            quantity_available=0,
            quantity_reserved=0,
            quantity_damaged=0,
            status=BatchStatus.ACTIVE,
            tenant_id=tenant_id,
        )
        await self._batch_repo.add(batch)

        if data.initial_quantity > 0:
            batch.quantity_available = data.initial_quantity
            txn = self._record(
                batch.id,
                TransactionType.STOCK_IN,
                data.initial_quantity,
                reference_number=data.reference_number,
                remarks=data.remarks,
                created_by=created_by,
            )
            await self._txn_repo.create(txn)

        await self._session.commit()
        await self._session.refresh(batch)
        return batch

    async def stock_in(
        self,
        batch_id: UUID,
        data: StockInRequest,
        *,
        created_by: UUID | None,
    ) -> InventoryBatch:
        batch = await self._require_batch(batch_id)
        batch.quantity_available += data.quantity
        txn = self._record(
            batch_id,
            TransactionType.STOCK_IN,
            data.quantity,
            reference_number=data.reference_number,
            remarks=data.remarks,
            created_by=created_by,
        )
        await self._txn_repo.create(txn)
        await self._session.commit()
        await self._session.refresh(batch)
        return batch

    async def adjust(
        self,
        batch_id: UUID,
        data: AdjustRequest,
        *,
        created_by: UUID | None,
    ) -> InventoryBatch:
        batch = await self._require_batch(batch_id)
        new_available = batch.quantity_available + data.quantity_delta
        # Rule 1: quantity cannot go negative
        if new_available < 0:
            raise ValueError(
                f"Adjustment of {data.quantity_delta} would make quantity_available "
                f"negative (current: {batch.quantity_available})"
            )
        batch.quantity_available = new_available
        txn = self._record(
            batch_id,
            TransactionType.ADJUSTMENT,
            data.quantity_delta,  # signed: negative = downward correction
            reference_number=data.reference_number,
            remarks=data.remarks,
            created_by=created_by,
        )
        await self._txn_repo.create(txn)
        await self._session.commit()
        await self._session.refresh(batch)
        return batch

    async def damage(
        self,
        batch_id: UUID,
        data: DamageRequest,
        *,
        created_by: UUID | None,
    ) -> InventoryBatch:
        batch = await self._require_batch(batch_id)
        # Rule 1: cannot damage more than what's available
        if data.quantity > batch.quantity_available:
            raise ValueError(
                f"Cannot mark {data.quantity} units as damaged — "
                f"only {batch.quantity_available} available"
            )
        batch.quantity_available -= data.quantity
        batch.quantity_damaged += data.quantity
        txn = self._record(
            batch_id,
            TransactionType.DAMAGE,
            data.quantity,
            reference_number=data.reference_number,
            remarks=data.remarks,
            created_by=created_by,
        )
        await self._txn_repo.create(txn)
        await self._session.commit()
        await self._session.refresh(batch)
        return batch

    async def allocate(
        self,
        batch_id: UUID,
        data: AllocateRequest,
        *,
        created_by: UUID | None,
        today: date | None = None,
    ) -> InventoryBatch:
        batch = await self._require_batch(batch_id)
        # Rule 2: no expired stock
        self._check_not_expired(batch, today or date.today())
        # Rule 1: cannot reserve more than available
        if data.quantity > batch.quantity_available:
            raise ValueError(
                f"Cannot allocate {data.quantity} units — only {batch.quantity_available} available"
            )
        batch.quantity_available -= data.quantity
        batch.quantity_reserved += data.quantity
        txn = self._record(
            batch_id,
            TransactionType.ALLOCATION,
            data.quantity,
            reference_number=data.reference_number,
            remarks=data.remarks,
            created_by=created_by,
        )
        await self._txn_repo.create(txn)
        await self._session.commit()
        await self._session.refresh(batch)
        return batch

    async def release(
        self,
        batch_id: UUID,
        data: ReleaseRequest,
        *,
        created_by: UUID | None,
    ) -> InventoryBatch:
        batch = await self._require_batch(batch_id)
        # Rule 1: cannot release more than is reserved
        if data.quantity > batch.quantity_reserved:
            raise ValueError(
                f"Cannot release {data.quantity} units — only {batch.quantity_reserved} reserved"
            )
        batch.quantity_reserved -= data.quantity
        batch.quantity_available += data.quantity
        txn = self._record(
            batch_id,
            TransactionType.RELEASE,
            data.quantity,
            reference_number=data.reference_number,
            remarks=data.remarks,
            created_by=created_by,
        )
        await self._txn_repo.create(txn)
        await self._session.commit()
        await self._session.refresh(batch)
        return batch

    async def stock_out(
        self,
        batch_id: UUID,
        data: StockOutRequest,
        *,
        created_by: UUID | None,
    ) -> InventoryBatch:
        batch = await self._require_batch(batch_id)
        # Rule 1: cannot ship more than is reserved
        if data.quantity > batch.quantity_reserved:
            raise ValueError(
                f"Cannot dispatch {data.quantity} units — only {batch.quantity_reserved} reserved"
            )
        batch.quantity_reserved -= data.quantity
        txn = self._record(
            batch_id,
            TransactionType.STOCK_OUT,
            data.quantity,
            reference_number=data.reference_number,
            remarks=data.remarks,
            created_by=created_by,
        )
        await self._txn_repo.create(txn)
        # auto-exhaust if nothing remains
        if batch.quantity_available == 0 and batch.quantity_reserved == 0:
            batch.status = BatchStatus.EXHAUSTED
        await self._session.commit()
        await self._session.refresh(batch)
        return batch

    # ── read operations ───────────────────────────────────────────────────────

    async def get(self, batch_id: UUID) -> InventoryBatch:
        batch = await self._batch_repo.get_by_id_not_deleted(batch_id)
        if batch is None:
            raise ValueError(f"Inventory batch {batch_id} not found")
        return batch

    async def list_batches(self, *, limit: int = 100, offset: int = 0) -> Sequence[InventoryBatch]:
        return await self._batch_repo.list_all(limit=limit, offset=offset)

    async def list_active(self, *, limit: int = 100, offset: int = 0) -> Sequence[InventoryBatch]:
        return await self._batch_repo.list_active(limit=limit, offset=offset)

    async def list_by_medicine(
        self, medicine_id: UUID, *, limit: int = 100, offset: int = 0
    ) -> Sequence[InventoryBatch]:
        return await self._batch_repo.list_by_medicine(medicine_id, limit=limit, offset=offset)

    async def get_transactions(
        self, batch_id: UUID, *, limit: int = 200, offset: int = 0
    ) -> list[InventoryTransaction]:
        await self.get(batch_id)  # ensures batch exists and not deleted
        txns = await self._txn_repo.list_by_batch(batch_id, limit=limit, offset=offset)
        return list(txns)

    async def list_all_transactions(
        self, *, limit: int = 200, offset: int = 0
    ) -> list[InventoryTransaction]:
        txns = await self._txn_repo.list_all(limit=limit, offset=offset)
        return list(txns)
