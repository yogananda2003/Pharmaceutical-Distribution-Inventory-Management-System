"""Invoice Generation Service.

generate_invoice  Produce an invoice from a DISPATCHED/DELIVERED/COMPLETED order.
    Pulls line items from OrderItem, computes subtotal/tax/discount/total,
    assigns a sequential invoice number from a PostgreSQL sequence, and stores
    InvoiceLine rows matching the order items. All-or-nothing: single commit.

list_invoices / get_invoice / get_by_order  Read-path helpers.

update_status  Validate and apply invoice status transitions.

delete_invoice  Soft-delete DRAFT invoices only.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.customer_order import OrderStatus
from app.models.invoice import (
    INVOICE_STATUS_TRANSITIONS,
    Invoice,
    InvoiceLine,
    InvoiceStatus,
)
from app.repositories.customer_order import CustomerOrderRepository, OrderItemRepository
from app.repositories.invoice import InvoiceRepository

logger = get_logger(__name__)

_ELIGIBLE_STATUSES: set[OrderStatus] = {
    OrderStatus.DISPATCHED,
    OrderStatus.DELIVERED,
    OrderStatus.COMPLETED,
}


class InvoiceService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._invoice_repo = InvoiceRepository(session)
        self._order_repo = CustomerOrderRepository(session)
        self._item_repo = OrderItemRepository(session)

    async def generate_invoice(
        self,
        order_id: UUID,
        *,
        invoice_date: date | None = None,
        due_date: date | None = None,
        notes: str | None = None,
        tenant_id: UUID | None = None,
    ) -> Invoice:
        order = await self._order_repo.get_by_id_not_deleted(order_id)
        if not order:
            raise ValueError("order not found")

        if order.status not in _ELIGIBLE_STATUSES:
            raise ValueError(
                f"Invoice can only be generated for DISPATCHED/DELIVERED/COMPLETED orders; "
                f"current status: '{order.status}'"
            )

        existing = await self._invoice_repo.get_by_order_id(order_id)
        if existing:
            raise ValueError(f"Invoice already exists for order {order.order_number}")

        items = await self._item_repo.list_by_order(order_id)

        # Atomic, concurrent-safe sequential number via PostgreSQL sequence.
        result = await self._session.execute(text("SELECT nextval('invoice_number_seq')"))
        seq_num: int = result.scalar_one()
        effective_date = invoice_date or date.today()
        invoice_number = f"INV-{effective_date.year}-{seq_num:04d}"

        subtotal = sum(
            (item.unit_price * Decimal(item.quantity) for item in items),
            Decimal("0.00"),
        )
        total_discount = sum((item.discount for item in items), Decimal("0.00"))
        total_tax = sum((item.tax_amount for item in items), Decimal("0.00"))
        total_amount = subtotal - total_discount + total_tax

        invoice = Invoice(
            invoice_number=invoice_number,
            order_id=order_id,
            customer_id=order.customer_id,
            invoice_date=effective_date,
            due_date=due_date,
            status=InvoiceStatus.DRAFT,
            subtotal=subtotal,
            tax_amount=total_tax,
            discount_amount=total_discount,
            total_amount=total_amount,
            notes=notes,
            tenant_id=tenant_id,
        )
        self._session.add(invoice)
        await self._session.flush()

        for item in items:
            line = InvoiceLine(
                invoice_id=invoice.id,
                medicine_id=item.medicine_id,
                description=f"{item.medicine.code} — {item.medicine.name}",
                quantity=item.quantity,
                unit_price=item.unit_price,
                discount=item.discount,
                tax_amount=item.tax_amount,
                line_total=item.line_total,
            )
            self._session.add(line)

        await self._session.commit()
        # Re-query to load selectin relationships (order, customer, lines).
        loaded = await self._invoice_repo.get_by_id_not_deleted(invoice.id)
        return loaded  # type: ignore[return-value]

    async def get_invoice(self, invoice_id: UUID) -> Invoice | None:
        return await self._invoice_repo.get_by_id_not_deleted(invoice_id)

    async def get_by_order(self, order_id: UUID) -> Invoice | None:
        return await self._invoice_repo.get_by_order_id(order_id)

    async def list_invoices(
        self,
        customer_id: UUID | None = None,
        status: str | None = None,
    ) -> list[Invoice]:
        if customer_id:
            return await self._invoice_repo.list_by_customer(customer_id)
        if status:
            try:
                inv_status = InvoiceStatus(status)
            except ValueError:
                raise ValueError(f"Invalid invoice status: '{status}'") from None
            return await self._invoice_repo.list_by_status(inv_status)
        return await self._invoice_repo.list_all_not_deleted()

    async def update_status(self, invoice_id: UUID, new_status_str: str) -> Invoice:
        invoice = await self._invoice_repo.get_by_id_not_deleted(invoice_id)
        if not invoice:
            raise ValueError("invoice not found")

        try:
            new_status = InvoiceStatus(new_status_str)
        except ValueError:
            raise ValueError(f"Invalid invoice status: '{new_status_str}'") from None

        allowed = INVOICE_STATUS_TRANSITIONS.get(invoice.status, [])
        if new_status not in allowed:
            raise ValueError(f"Cannot transition from '{invoice.status}' to '{new_status}'")

        invoice.status = new_status
        await self._session.commit()
        await self._session.refresh(invoice)
        return invoice

    async def delete_invoice(self, invoice_id: UUID) -> None:
        invoice = await self._invoice_repo.get_by_id_not_deleted(invoice_id)
        if not invoice:
            raise ValueError("invoice not found")
        if invoice.status != InvoiceStatus.DRAFT:
            raise ValueError(
                f"Only DRAFT invoices can be deleted; current status: '{invoice.status}'"
            )
        invoice.deleted_at = datetime.now(UTC)
        await self._session.commit()

        logger.info("invoice_deleted", invoice_id=str(invoice_id))
