from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, field_validator

from app.models.inventory_batch import BatchStatus


class BatchCreate(BaseModel):
    medicine_id: UUID
    warehouse_id: UUID
    batch_number: str
    manufacturing_date: date | None = None
    expiry_date: date
    initial_quantity: int = 0  # creates a STOCK_IN transaction when > 0
    reference_number: str | None = None
    remarks: str | None = None

    @field_validator("batch_number")
    @classmethod
    def batch_number_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("batch_number cannot be blank")
        return v.upper()

    @field_validator("initial_quantity")
    @classmethod
    def initial_quantity_non_negative(cls, v: int) -> int:
        if v < 0:
            raise ValueError("initial_quantity must be >= 0")
        return v


class BatchRead(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    medicine_id: UUID
    warehouse_id: UUID
    batch_number: str
    manufacturing_date: date | None
    expiry_date: date
    quantity_available: int
    quantity_reserved: int
    quantity_damaged: int
    status: BatchStatus
    tenant_id: UUID | None
    created_at: datetime
    updated_at: datetime


class StockInRequest(BaseModel):
    quantity: int
    reference_number: str | None = None
    remarks: str | None = None

    @field_validator("quantity")
    @classmethod
    def quantity_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("quantity must be > 0")
        return v


class AdjustRequest(BaseModel):
    """Positive delta increases available; negative delta decreases it."""

    quantity_delta: int
    reference_number: str | None = None
    remarks: str | None = None

    @field_validator("quantity_delta")
    @classmethod
    def delta_not_zero(cls, v: int) -> int:
        if v == 0:
            raise ValueError("quantity_delta must not be zero")
        return v


class DamageRequest(BaseModel):
    quantity: int
    reference_number: str | None = None
    remarks: str | None = None

    @field_validator("quantity")
    @classmethod
    def quantity_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("quantity must be > 0")
        return v


class AllocateRequest(BaseModel):
    quantity: int
    reference_number: str | None = None
    remarks: str | None = None

    @field_validator("quantity")
    @classmethod
    def quantity_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("quantity must be > 0")
        return v


class ReleaseRequest(BaseModel):
    quantity: int
    reference_number: str | None = None
    remarks: str | None = None

    @field_validator("quantity")
    @classmethod
    def quantity_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("quantity must be > 0")
        return v


class StockOutRequest(BaseModel):
    quantity: int
    reference_number: str | None = None
    remarks: str | None = None

    @field_validator("quantity")
    @classmethod
    def quantity_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("quantity must be > 0")
        return v
