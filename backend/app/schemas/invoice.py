from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class GenerateInvoiceRequest(BaseModel):
    order_id: UUID
    invoice_date: date | None = None
    due_date: date | None = None
    notes: str | None = None


class UpdateInvoiceStatusRequest(BaseModel):
    status: str


class InvoiceLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    medicine_id: UUID
    description: str
    quantity: int
    unit_price: Decimal
    discount: Decimal
    tax_amount: Decimal
    line_total: Decimal
    created_at: datetime


class InvoiceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    invoice_number: str
    order_id: UUID
    customer_id: UUID
    invoice_date: date
    due_date: date | None
    status: str
    subtotal: Decimal
    tax_amount: Decimal
    discount_amount: Decimal
    total_amount: Decimal
    notes: str | None
    lines: list[InvoiceLineRead]
    created_at: datetime
    updated_at: datetime
