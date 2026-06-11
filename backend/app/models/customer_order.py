from __future__ import annotations

import enum
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Date, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.base import TenantedEntity, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.customer import Customer
    from app.models.inventory_batch import InventoryBatch
    from app.models.medicine import Medicine
    from app.models.user import User


class OrderStatus(enum.StrEnum):
    DRAFT = "draft"
    PLACED = "placed"
    APPROVED = "approved"
    ALLOCATED = "allocated"
    PICKED = "picked"
    PACKED = "packed"
    DISPATCHED = "dispatched"
    DELIVERED = "delivered"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


# Transitions that do NOT touch inventory (handled by generic PATCH /status).
ORDER_STATUS_TRANSITIONS: dict[OrderStatus, list[OrderStatus]] = {
    OrderStatus.DRAFT: [OrderStatus.PLACED, OrderStatus.CANCELLED],
    OrderStatus.PLACED: [OrderStatus.CANCELLED],  # PLACED→APPROVED goes via /approve
    OrderStatus.APPROVED: [OrderStatus.ALLOCATED, OrderStatus.CANCELLED],
    OrderStatus.ALLOCATED: [OrderStatus.PICKED, OrderStatus.CANCELLED],
    OrderStatus.PICKED: [OrderStatus.PACKED],
    OrderStatus.PACKED: [OrderStatus.CANCELLED],  # PACKED→DISPATCHED goes via /dispatch
    OrderStatus.DISPATCHED: [OrderStatus.DELIVERED],
    OrderStatus.DELIVERED: [OrderStatus.COMPLETED],
    OrderStatus.COMPLETED: [],
    OrderStatus.CANCELLED: [],
}

# States from which an order can be cancelled (used by cancel service).
CANCELLABLE_STATUSES = {
    OrderStatus.DRAFT,
    OrderStatus.PLACED,
    OrderStatus.APPROVED,
    OrderStatus.ALLOCATED,
    OrderStatus.PICKED,
    OrderStatus.PACKED,
}

# States where stock has been reserved and must be released on cancel.
RESERVED_STATUSES = {
    OrderStatus.APPROVED,
    OrderStatus.ALLOCATED,
    OrderStatus.PICKED,
    OrderStatus.PACKED,
}


class CustomerOrder(TenantedEntity):
    __tablename__ = "customer_orders"

    order_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    customer_id: Mapped[UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    sales_rep_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    order_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[OrderStatus] = mapped_column(
        Enum(
            OrderStatus,
            name="order_status",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=OrderStatus.DRAFT,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=12, scale=2), nullable=False, default=Decimal("0.00")
    )

    customer: Mapped[Customer] = relationship("Customer", lazy="selectin")
    sales_rep: Mapped[User | None] = relationship("User", lazy="selectin")
    items: Mapped[list[OrderItem]] = relationship(
        "OrderItem",
        back_populates="order",
        lazy="selectin",
        order_by="OrderItem.created_at",
    )


class OrderItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Line item — no soft delete; lives and dies with parent order."""

    __tablename__ = "order_items"

    order_id: Mapped[UUID] = mapped_column(
        ForeignKey("customer_orders.id", ondelete="CASCADE"), nullable=False, index=True
    )
    medicine_id: Mapped[UUID] = mapped_column(
        ForeignKey("medicines.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(precision=12, scale=2), nullable=False)
    discount: Mapped[Decimal] = mapped_column(
        Numeric(precision=12, scale=2), nullable=False, default=Decimal("0.00")
    )
    tax_amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=12, scale=2), nullable=False, default=Decimal("0.00")
    )
    line_total: Mapped[Decimal] = mapped_column(
        Numeric(precision=12, scale=2), nullable=False, default=Decimal("0.00")
    )

    order: Mapped[CustomerOrder] = relationship(
        "CustomerOrder", back_populates="items", lazy="selectin"
    )
    medicine: Mapped[Medicine] = relationship("Medicine", lazy="selectin")
    allocations: Mapped[list[OrderItemAllocation]] = relationship(
        "OrderItemAllocation", back_populates="order_item", lazy="select"
    )


class OrderItemAllocation(UUIDPrimaryKeyMixin, Base):
    """Tracks which batch+qty was reserved for an order item.

    Created at approval (FEFO allocation). Deleted when released (cancel) or
    consumed (dispatch). Not soft-deleted — operational tracking, not audit.
    The audit trail lives in InventoryTransaction (ALLOCATION/RELEASE/STOCK_OUT).
    """

    __tablename__ = "order_item_allocations"

    order_item_id: Mapped[UUID] = mapped_column(
        ForeignKey("order_items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    batch_id: Mapped[UUID] = mapped_column(
        ForeignKey("inventory_batches.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)

    order_item: Mapped[OrderItem] = relationship(
        "OrderItem", back_populates="allocations", lazy="selectin"
    )
    batch: Mapped[InventoryBatch] = relationship("InventoryBatch", lazy="selectin")
