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
    from app.models.medicine import Medicine
    from app.models.supplier import Supplier


class PurchaseStatus(enum.StrEnum):
    DRAFT = "draft"
    SENT = "sent"
    CONFIRMED = "confirmed"
    PARTIALLY_RECEIVED = "partially_received"
    RECEIVED = "received"
    CANCELLED = "cancelled"


# Valid status transitions (source → allowed targets)
PURCHASE_STATUS_TRANSITIONS: dict[PurchaseStatus, list[PurchaseStatus]] = {
    PurchaseStatus.DRAFT: [PurchaseStatus.SENT, PurchaseStatus.CANCELLED],
    PurchaseStatus.SENT: [PurchaseStatus.CONFIRMED, PurchaseStatus.CANCELLED],
    PurchaseStatus.CONFIRMED: [
        PurchaseStatus.PARTIALLY_RECEIVED,
        PurchaseStatus.RECEIVED,
        PurchaseStatus.CANCELLED,
    ],
    PurchaseStatus.PARTIALLY_RECEIVED: [
        PurchaseStatus.RECEIVED,
        PurchaseStatus.CANCELLED,
    ],
    PurchaseStatus.RECEIVED: [],
    PurchaseStatus.CANCELLED: [],
}


class PurchaseOrder(TenantedEntity):
    __tablename__ = "purchase_orders"

    po_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    supplier_id: Mapped[UUID] = mapped_column(
        ForeignKey("suppliers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    order_date: Mapped[date] = mapped_column(Date, nullable=False)
    expected_delivery_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[PurchaseStatus] = mapped_column(
        Enum(
            PurchaseStatus,
            name="purchase_status",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=PurchaseStatus.DRAFT,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=12, scale=2), nullable=False, default=Decimal("0.00")
    )

    supplier: Mapped[Supplier] = relationship("Supplier", lazy="selectin")
    items: Mapped[list[PurchaseOrderItem]] = relationship(
        "PurchaseOrderItem",
        back_populates="purchase_order",
        lazy="selectin",
        order_by="PurchaseOrderItem.created_at",
    )


class PurchaseOrderItem(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Line item on a purchase order.

    Not soft-deleted independently — lives and dies with its parent PO.
    """

    __tablename__ = "purchase_order_items"

    purchase_order_id: Mapped[UUID] = mapped_column(
        ForeignKey("purchase_orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    medicine_id: Mapped[UUID] = mapped_column(
        ForeignKey("medicines.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    quantity_ordered: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_received: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(precision=12, scale=2), nullable=False)

    purchase_order: Mapped[PurchaseOrder] = relationship(
        "PurchaseOrder", back_populates="items", lazy="selectin"
    )
    medicine: Mapped[Medicine] = relationship("Medicine", lazy="selectin")
