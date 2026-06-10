from __future__ import annotations

from datetime import date
from uuid import UUID

from pydantic import BaseModel, field_validator


class FEFOAllocationRequest(BaseModel):
    medicine_id: UUID
    quantity: int
    warehouse_id: UUID | None = None
    reference_number: str | None = None
    remarks: str | None = None

    @field_validator("quantity")
    @classmethod
    def quantity_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("quantity must be > 0")
        return v


class BatchAllocationDetail(BaseModel):
    batch_id: UUID
    batch_number: str
    expiry_date: date
    quantity_allocated: int


class FEFOAllocationResponse(BaseModel):
    medicine_id: UUID
    total_quantity_requested: int
    total_quantity_allocated: int
    allocations: list[BatchAllocationDetail]


class FEFOReleaseItem(BaseModel):
    batch_id: UUID
    quantity: int

    @field_validator("quantity")
    @classmethod
    def quantity_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("quantity must be > 0")
        return v


class FEFOReleaseRequest(BaseModel):
    allocations: list[FEFOReleaseItem]
    reference_number: str | None = None
    remarks: str | None = None

    @field_validator("allocations")
    @classmethod
    def allocations_not_empty(cls, v: list[FEFOReleaseItem]) -> list[FEFOReleaseItem]:
        if not v:
            raise ValueError("allocations list cannot be empty")
        return v
