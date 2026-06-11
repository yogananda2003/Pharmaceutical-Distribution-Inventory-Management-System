from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

from app.models.customer_order import OrderStatus


class OrderItemCreate(BaseModel):
    medicine_id: UUID
    quantity: int
    unit_price: Decimal
    discount: Decimal = Decimal("0.00")
    tax_amount: Decimal = Decimal("0.00")

    @field_validator("quantity")
    @classmethod
    def qty_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("quantity must be > 0")
        return v

    @field_validator("unit_price")
    @classmethod
    def price_non_negative(cls, v: Decimal) -> Decimal:
        if v < Decimal("0"):
            raise ValueError("unit_price must be >= 0")
        return v.quantize(Decimal("0.01"))

    @field_validator("discount")
    @classmethod
    def discount_non_negative(cls, v: Decimal) -> Decimal:
        if v < Decimal("0"):
            raise ValueError("discount must be >= 0")
        return v.quantize(Decimal("0.01"))

    @field_validator("tax_amount")
    @classmethod
    def tax_non_negative(cls, v: Decimal) -> Decimal:
        if v < Decimal("0"):
            raise ValueError("tax_amount must be >= 0")
        return v.quantize(Decimal("0.01"))


class OrderCreate(BaseModel):
    order_number: str | None = None
    customer_id: UUID
    sales_rep_id: UUID | None = None
    order_date: date
    notes: str | None = None
    items: list[OrderItemCreate] = []

    @field_validator("items")
    @classmethod
    def items_not_empty(cls, v: list[OrderItemCreate]) -> list[OrderItemCreate]:
        if not v:
            raise ValueError("items list cannot be empty")
        return v


class OrderItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    medicine_id: UUID
    quantity: int
    unit_price: Decimal
    discount: Decimal
    tax_amount: Decimal
    line_total: Decimal
    created_at: datetime


class OrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_number: str
    customer_id: UUID
    sales_rep_id: UUID | None
    order_date: date
    status: OrderStatus
    notes: str | None
    total_amount: Decimal
    tenant_id: UUID | None
    items: list[OrderItemRead]
    created_at: datetime
    updated_at: datetime


class OrderStatusUpdate(BaseModel):
    status: OrderStatus
