from __future__ import annotations

import uuid
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.customer_order import (
    ORDER_STATUS_TRANSITIONS,
    CustomerOrder,
    OrderItem,
    OrderStatus,
)
from app.repositories.customer_order import CustomerOrderRepository, OrderItemRepository
from app.schemas.customer_order import OrderCreate

logger = get_logger(__name__)


def _line_total(unit_price: Decimal, quantity: int, discount: Decimal, tax: Decimal) -> Decimal:
    return (unit_price * quantity - discount + tax).quantize(Decimal("0.01"))


class CustomerOrderService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo = CustomerOrderRepository(session)
        self._item_repo = OrderItemRepository(session)

    # ── helpers ────────────────────────────────────────────────────────────────

    async def _require_order(self, order_id: UUID) -> CustomerOrder:
        order = await self._repo.get_by_id_not_deleted(order_id)
        if not order:
            raise ValueError("order not found")
        return order

    # ── create ─────────────────────────────────────────────────────────────────

    async def create(self, data: OrderCreate, *, tenant_id: UUID | None = None) -> CustomerOrder:
        order_number = (data.order_number or f"ORD-{uuid.uuid4().hex[:8].upper()}").strip().upper()
        if await self._repo.get_by_order_number(order_number):
            raise ValueError(f"order number '{order_number}' already exists")

        order = CustomerOrder(
            order_number=order_number,
            customer_id=data.customer_id,
            sales_rep_id=data.sales_rep_id,
            order_date=data.order_date,
            notes=data.notes,
            status=OrderStatus.DRAFT,
            total_amount=Decimal("0.00"),
            tenant_id=tenant_id,
        )
        await self._repo.add(order)
        await self._session.flush()

        total = Decimal("0.00")
        for item_data in data.items:
            lt = _line_total(
                item_data.unit_price,
                item_data.quantity,
                item_data.discount,
                item_data.tax_amount,
            )
            item = OrderItem(
                order_id=order.id,
                medicine_id=item_data.medicine_id,
                quantity=item_data.quantity,
                unit_price=item_data.unit_price,
                discount=item_data.discount,
                tax_amount=item_data.tax_amount,
                line_total=lt,
            )
            self._session.add(item)
            total += lt

        order.total_amount = total
        await self._session.commit()
        await self._session.refresh(order)
        logger.info("order_created", order_number=order_number)
        return order

    # ── read ───────────────────────────────────────────────────────────────────

    async def get(self, order_id: UUID) -> CustomerOrder:
        return await self._require_order(order_id)

    async def list_all(
        self,
        *,
        customer_id: UUID | None = None,
        status: OrderStatus | None = None,
    ) -> list[CustomerOrder]:
        if customer_id:
            return await self._repo.list_by_customer(customer_id)
        if status:
            return await self._repo.list_by_status(status)
        return await self._repo.list_all_not_deleted()

    # ── generic status transition (no stock ops) ───────────────────────────────

    async def transition_status(self, order_id: UUID, new_status: OrderStatus) -> CustomerOrder:
        order = await self._require_order(order_id)
        allowed = ORDER_STATUS_TRANSITIONS.get(order.status, [])
        if new_status not in allowed:
            raise ValueError(
                f"Cannot transition from '{order.status}' to '{new_status}'. "
                f"Allowed: {[s.value for s in allowed]}"
            )
        order.status = new_status
        await self._session.commit()
        await self._session.refresh(order)
        logger.info("order_status_updated", order_id=str(order_id), new_status=new_status)
        return order

    # ── soft delete (DRAFT only) ───────────────────────────────────────────────

    async def delete(self, order_id: UUID) -> None:
        order = await self._require_order(order_id)
        if order.status != OrderStatus.DRAFT:
            raise ValueError("Only DRAFT orders can be deleted")
        await self._repo.soft_delete(order)
        await self._session.commit()
        logger.info("order_deleted", order_id=str(order_id))
