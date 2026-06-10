from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, field_validator


class WarehouseCreate(BaseModel):
    warehouse_code: str
    warehouse_name: str
    address: str | None = None
    contact_details: str | None = None
    is_active: bool = True

    @field_validator("warehouse_code")
    @classmethod
    def code_uppercase(cls, v: str) -> str:
        v = v.strip().upper()
        if not v:
            raise ValueError("warehouse_code cannot be blank")
        return v

    @field_validator("warehouse_name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("warehouse_name cannot be blank")
        return v.strip()


class WarehouseUpdate(BaseModel):
    warehouse_name: str | None = None
    address: str | None = None
    contact_details: str | None = None
    is_active: bool | None = None


class WarehouseRead(BaseModel):
    id: UUID
    warehouse_code: str
    warehouse_name: str
    address: str | None
    contact_details: str | None
    is_active: bool
    tenant_id: UUID | None = None

    model_config = {"from_attributes": True}
