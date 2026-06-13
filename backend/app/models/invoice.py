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
    from app.models.customer_order import CustomerOrder
    from app.models.medicine import Medicine


class InvoiceStatus(enum.StrEnum):
    DRAFT = "draft"
    ISSUED = "issued"
    PAID = "paid"
    CANCELLED = "cancelled"
    VOID = "void"


INVOICE_STATUS_TRANSITIONS: dict[InvoiceStatus, list[InvoiceStatus]] = {
    InvoiceStatus.DRAFT: [InvoiceStatus.ISSUED, InvoiceStatus.CANCELLED],
    InvoiceStatus.ISSUED: [InvoiceStatus.PAID, InvoiceStatus.VOID],
    InvoiceStatus.PAID: [],
    InvoiceStatus.CANCELLED: [],
    InvoiceStatus.VOID: [],
}


class Invoice(TenantedEntity):
    __tablename__ = "invoices"

    invoice_number: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    order_id: Mapped[UUID] = mapped_column(
        ForeignKey("customer_orders.id", ondelete="RESTRICT"),
        unique=True,
        nullable=False,
        index=True,
    )
    customer_id: Mapped[UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    invoice_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[InvoiceStatus] = mapped_column(
        Enum(
            InvoiceStatus,
            name="invoice_status",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=InvoiceStatus.DRAFT,
    )
    subtotal: Mapped[Decimal] = mapped_column(
        Numeric(precision=12, scale=2), nullable=False, default=Decimal("0.00")
    )
    tax_amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=12, scale=2), nullable=False, default=Decimal("0.00")
    )
    discount_amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=12, scale=2), nullable=False, default=Decimal("0.00")
    )
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=12, scale=2), nullable=False, default=Decimal("0.00")
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    order: Mapped[CustomerOrder] = relationship("CustomerOrder", lazy="selectin")
    customer: Mapped[Customer] = relationship("Customer", lazy="selectin")
    lines: Mapped[list[InvoiceLine]] = relationship(
        "InvoiceLine",
        back_populates="invoice",
        lazy="selectin",
        order_by="InvoiceLine.created_at",
    )


class InvoiceLine(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Line item — no soft delete; lives and dies with parent invoice."""

    __tablename__ = "invoice_lines"

    invoice_id: Mapped[UUID] = mapped_column(
        ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False, index=True
    )
    medicine_id: Mapped[UUID] = mapped_column(
        ForeignKey("medicines.id", ondelete="RESTRICT"), nullable=False
    )
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(precision=12, scale=2), nullable=False)
    discount: Mapped[Decimal] = mapped_column(
        Numeric(precision=12, scale=2), nullable=False, default=Decimal("0.00")
    )
    tax_amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=12, scale=2), nullable=False, default=Decimal("0.00")
    )
    line_total: Mapped[Decimal] = mapped_column(Numeric(precision=12, scale=2), nullable=False)

    invoice: Mapped[Invoice] = relationship("Invoice", back_populates="lines", lazy="selectin")
    medicine: Mapped[Medicine] = relationship("Medicine", lazy="selectin")
