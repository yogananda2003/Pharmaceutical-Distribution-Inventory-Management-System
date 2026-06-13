from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator


class StockTransferRequest(BaseModel):
    source_batch_id: UUID
    destination_batch_id: UUID
    quantity: int
    reference_number: str | None = None
    remarks: str | None = None

    @field_validator("quantity")
    @classmethod
    def qty_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("quantity must be greater than 0")
        return v


class StockTransferResponse(BaseModel):
    source_batch_id: UUID
    destination_batch_id: UUID
    quantity: int
    reference_number: str | None
    source_quantity_available: int
    destination_quantity_available: int


class BatchPickInfo(BaseModel):
    batch_id: UUID
    batch_number: str
    warehouse_id: UUID
    warehouse_name: str
    expiry_date: date
    quantity_to_pick: int


class PickListItemInfo(BaseModel):
    order_item_id: UUID
    medicine_id: UUID
    medicine_code: str
    medicine_name: str
    total_quantity: int
    batches: list[BatchPickInfo]


class PickListResponse(BaseModel):
    order_id: UUID
    order_number: str
    customer_name: str
    order_status: str
    items: list[PickListItemInfo]


class PendingOrderSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_number: str
    status: str
    total_amount: Decimal
    order_date: date
    customer_name: str
    item_count: int
