from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory_batch import BatchStatus, InventoryBatch


class InventoryBatchRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id_not_deleted(self, batch_id: UUID) -> InventoryBatch | None:
        result = await self.session.execute(
            select(InventoryBatch).where(
                InventoryBatch.id == batch_id,
                InventoryBatch.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id_for_update(self, batch_id: UUID) -> InventoryBatch | None:
        """Acquires a row-level lock — use for all quantity mutations."""
        result = await self.session.execute(
            select(InventoryBatch)
            .where(
                InventoryBatch.id == batch_id,
                InventoryBatch.deleted_at.is_(None),
            )
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def get_by_batch_number(
        self, medicine_id: UUID, warehouse_id: UUID, batch_number: str
    ) -> InventoryBatch | None:
        result = await self.session.execute(
            select(InventoryBatch).where(
                InventoryBatch.medicine_id == medicine_id,
                InventoryBatch.warehouse_id == warehouse_id,
                InventoryBatch.batch_number == batch_number,
                InventoryBatch.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def list_active(self, *, limit: int = 100, offset: int = 0) -> Sequence[InventoryBatch]:
        result = await self.session.execute(
            select(InventoryBatch)
            .where(
                InventoryBatch.status == BatchStatus.ACTIVE,
                InventoryBatch.deleted_at.is_(None),
            )
            .order_by(InventoryBatch.expiry_date)
            .limit(limit)
            .offset(offset)
        )
        return result.scalars().all()

    async def list_by_medicine(
        self, medicine_id: UUID, *, limit: int = 100, offset: int = 0
    ) -> Sequence[InventoryBatch]:
        result = await self.session.execute(
            select(InventoryBatch)
            .where(
                InventoryBatch.medicine_id == medicine_id,
                InventoryBatch.deleted_at.is_(None),
            )
            .order_by(InventoryBatch.expiry_date)
            .limit(limit)
            .offset(offset)
        )
        return result.scalars().all()

    async def list_expiring_before(
        self, cutoff: date, *, limit: int = 500
    ) -> Sequence[InventoryBatch]:
        """Returns non-deleted, non-exhausted batches whose expiry_date < cutoff."""
        result = await self.session.execute(
            select(InventoryBatch)
            .where(
                InventoryBatch.expiry_date < cutoff,
                InventoryBatch.status.not_in([BatchStatus.EXHAUSTED]),
                InventoryBatch.deleted_at.is_(None),
            )
            .order_by(InventoryBatch.expiry_date)
            .limit(limit)
        )
        return result.scalars().all()

    async def list_all(self, *, limit: int = 100, offset: int = 0) -> Sequence[InventoryBatch]:
        result = await self.session.execute(
            select(InventoryBatch)
            .where(InventoryBatch.deleted_at.is_(None))
            .order_by(InventoryBatch.expiry_date)
            .limit(limit)
            .offset(offset)
        )
        return result.scalars().all()

    async def list_allocatable_fefo(
        self,
        medicine_id: UUID,
        today: date,
        *,
        warehouse_id: UUID | None = None,
    ) -> Sequence[InventoryBatch]:
        """FEFO candidates: active, not expired, has available stock, ordered earliest-expiry first.

        Does NOT lock rows — callers must use get_by_id_for_update before mutating.
        """
        stmt = (
            select(InventoryBatch)
            .where(
                InventoryBatch.medicine_id == medicine_id,
                InventoryBatch.expiry_date >= today,
                InventoryBatch.quantity_available > 0,
                InventoryBatch.status == BatchStatus.ACTIVE,
                InventoryBatch.deleted_at.is_(None),
            )
            .order_by(InventoryBatch.expiry_date)
        )
        if warehouse_id is not None:
            stmt = stmt.where(InventoryBatch.warehouse_id == warehouse_id)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def add(self, batch: InventoryBatch) -> InventoryBatch:
        self.session.add(batch)
        await self.session.flush()
        return batch
