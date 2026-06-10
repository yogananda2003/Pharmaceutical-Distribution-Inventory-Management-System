from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer import Customer, CustomerStatus
from app.repositories.base import BaseRepository


class CustomerRepository(BaseRepository[Customer]):
    model = Customer

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_id_not_deleted(self, customer_id: UUID) -> Customer | None:
        result = await self.session.execute(
            select(Customer).where(
                Customer.id == customer_id,
                Customer.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_code(self, code: str) -> Customer | None:
        result = await self.session.execute(
            select(Customer).where(
                Customer.customer_code == code,
                Customer.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def list_active(self) -> list[Customer]:
        result = await self.session.execute(
            select(Customer).where(
                Customer.status == CustomerStatus.ACTIVE,
                Customer.deleted_at.is_(None),
            )
        )
        return list(result.scalars().all())

    async def list_all_not_deleted(self) -> list[Customer]:
        result = await self.session.execute(select(Customer).where(Customer.deleted_at.is_(None)))
        return list(result.scalars().all())
