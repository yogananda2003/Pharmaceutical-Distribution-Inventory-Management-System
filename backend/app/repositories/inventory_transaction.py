from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory_transaction import InventoryTransaction


class InventoryTransactionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, transaction: InventoryTransaction) -> InventoryTransaction:
        self.session.add(transaction)
        await self.session.flush()
        return transaction

    async def list_by_batch(
        self, batch_id: UUID, *, limit: int = 200, offset: int = 0
    ) -> Sequence[InventoryTransaction]:
        result = await self.session.execute(
            select(InventoryTransaction)
            .where(InventoryTransaction.batch_id == batch_id)
            .order_by(InventoryTransaction.created_at)
            .limit(limit)
            .offset(offset)
        )
        return result.scalars().all()

    async def list_all(
        self, *, limit: int = 200, offset: int = 0
    ) -> Sequence[InventoryTransaction]:
        result = await self.session.execute(
            select(InventoryTransaction)
            .order_by(InventoryTransaction.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return result.scalars().all()
