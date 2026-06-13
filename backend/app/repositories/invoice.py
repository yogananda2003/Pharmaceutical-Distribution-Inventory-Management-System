from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.invoice import Invoice, InvoiceStatus
from app.repositories.base import BaseRepository


class InvoiceRepository(BaseRepository[Invoice]):
    model = Invoice

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_id_not_deleted(self, invoice_id: UUID) -> Invoice | None:
        result = await self.session.execute(
            select(Invoice).where(
                Invoice.id == invoice_id,
                Invoice.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_order_id(self, order_id: UUID) -> Invoice | None:
        result = await self.session.execute(
            select(Invoice).where(
                Invoice.order_id == order_id,
                Invoice.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def list_all_not_deleted(self) -> list[Invoice]:
        result = await self.session.execute(select(Invoice).where(Invoice.deleted_at.is_(None)))
        return list(result.scalars().all())

    async def list_by_customer(self, customer_id: UUID) -> list[Invoice]:
        result = await self.session.execute(
            select(Invoice).where(
                Invoice.customer_id == customer_id,
                Invoice.deleted_at.is_(None),
            )
        )
        return list(result.scalars().all())

    async def list_by_status(self, status: InvoiceStatus) -> list[Invoice]:
        result = await self.session.execute(
            select(Invoice).where(
                Invoice.status == status,
                Invoice.deleted_at.is_(None),
            )
        )
        return list(result.scalars().all())
