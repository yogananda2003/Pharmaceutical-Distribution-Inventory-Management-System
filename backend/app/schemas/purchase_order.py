from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator

from app.models.purchase_order import PurchaseStatus


class PurchaseOrderItemCreate(BaseModel):
    medicine_id: UUID
    quantity_ordered: int
    unit_price: Decimal

    @field_validator("quantity_ordered")
    @classmethod
    def qty_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("quantity_ordered must be > 0")
        return v

    @field_validator("unit_price")
    @classmethod
    def price_non_negative(cls, v: Decimal) -> Decimal:
        if v < Decimal("0"):
            raise ValueError("unit_price must be >= 0")
        return v.quantize(Decimal("0.01"))


class PurchaseOrderCreate(BaseModel):
    po_number: str | None = None
    supplier_id: UUID
    order_date: date
    expected_delivery_date: date | None = None
    notes: str | None = None
    items: list[PurchaseOrderItemCreate] = []


class PurchaseOrderItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    medicine_id: UUID
    quantity_ordered: int
    quantity_received: int
    unit_price: Decimal
    created_at: datetime


class PurchaseOrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    po_number: str
    supplier_id: UUID
    order_date: date
    expected_delivery_date: date | None
    status: PurchaseStatus
    notes: str | None
    total_amount: Decimal
    tenant_id: UUID | None
    items: list[PurchaseOrderItemRead]
    created_at: datetime
    updated_at: datetime


class PurchaseStatusUpdate(BaseModel):
    status: PurchaseStatus


# ── goods receipt ──────────────────────────────────────────────────────────────


class GoodsReceiptItemRequest(BaseModel):
    purchase_order_item_id: UUID
    batch_number: str
    manufacturing_date: date | None = None
    expiry_date: date
    warehouse_id: UUID
    quantity: int

    @field_validator("quantity")
    @classmethod
    def qty_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("quantity must be > 0")
        return v

    @field_validator("batch_number")
    @classmethod
    def batch_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("batch_number cannot be blank")
        return v.upper()


class GoodsReceiptRequest(BaseModel):
    items: list[GoodsReceiptItemRequest]
    reference_number: str | None = None
    remarks: str | None = None

    @field_validator("items")
    @classmethod
    def items_not_empty(cls, v: list[GoodsReceiptItemRequest]) -> list[GoodsReceiptItemRequest]:
        if not v:
            raise ValueError("items list cannot be empty")
        return v


class GoodsReceiptItemResult(BaseModel):
    purchase_order_item_id: UUID
    batch_id: UUID
    batch_number: str
    quantity_received: int


class GoodsReceiptResponse(BaseModel):
    purchase_order_id: UUID
    po_number: str
    new_status: PurchaseStatus
    items_received: list[GoodsReceiptItemResult]
