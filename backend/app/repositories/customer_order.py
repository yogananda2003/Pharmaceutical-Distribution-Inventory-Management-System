from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer_order import (
    CustomerOrder,
    OrderItem,
    OrderItemAllocation,
    OrderStatus,
)
from app.repositories.base import BaseRepository


class CustomerOrderRepository(BaseRepository[CustomerOrder]):
    model = CustomerOrder

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def get_by_id_not_deleted(self, order_id: UUID) -> CustomerOrder | None:
        result = await self.session.execute(
            select(CustomerOrder).where(
                CustomerOrder.id == order_id,
                CustomerOrder.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def get_by_order_number(self, order_number: str) -> CustomerOrder | None:
        result = await self.session.execute(
            select(CustomerOrder).where(
                CustomerOrder.order_number == order_number,
                CustomerOrder.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def list_by_customer(self, customer_id: UUID) -> list[CustomerOrder]:
        result = await self.session.execute(
            select(CustomerOrder).where(
                CustomerOrder.customer_id == customer_id,
                CustomerOrder.deleted_at.is_(None),
            )
        )
        return list(result.scalars().all())

    async def list_by_status(self, status: OrderStatus) -> list[CustomerOrder]:
        result = await self.session.execute(
            select(CustomerOrder).where(
                CustomerOrder.status == status,
                CustomerOrder.deleted_at.is_(None),
            )
        )
        return list(result.scalars().all())

    async def list_all_not_deleted(self) -> list[CustomerOrder]:
        result = await self.session.execute(
            select(CustomerOrder).where(CustomerOrder.deleted_at.is_(None))
        )
        return list(result.scalars().all())


class OrderItemRepository:
    """Standalone — OrderItem does not extend BaseEntity."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, item_id: UUID) -> OrderItem | None:
        result = await self.session.execute(select(OrderItem).where(OrderItem.id == item_id))
        return result.scalar_one_or_none()

    async def list_by_order(self, order_id: UUID) -> list[OrderItem]:
        result = await self.session.execute(select(OrderItem).where(OrderItem.order_id == order_id))
        return list(result.scalars().all())


class OrderItemAllocationRepository:
    """Standalone — operational tracking, deleted (not soft-deleted) when fulfilled."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_by_order_item(self, order_item_id: UUID) -> list[OrderItemAllocation]:
        result = await self.session.execute(
            select(OrderItemAllocation).where(OrderItemAllocation.order_item_id == order_item_id)
        )
        return list(result.scalars().all())

    async def list_by_order(self, order_id: UUID) -> list[OrderItemAllocation]:
        """Return all allocations for all items in an order via join."""
        result = await self.session.execute(
            select(OrderItemAllocation)
            .join(OrderItem, OrderItemAllocation.order_item_id == OrderItem.id)
            .where(OrderItem.order_id == order_id)
        )
        return list(result.scalars().all())

    async def delete_by_order(self, order_id: UUID) -> None:
        """Hard-delete all allocations for an order (on cancel/dispatch)."""
        subq = select(OrderItem.id).where(OrderItem.order_id == order_id)
        await self.session.execute(
            delete(OrderItemAllocation).where(OrderItemAllocation.order_item_id.in_(subq))
        )
