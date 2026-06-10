from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, EmailStr, field_validator

from app.models.supplier import SupplierStatus


class SupplierCreate(BaseModel):
    supplier_code: str
    supplier_name: str
    gst_number: str | None = None
    drug_license_number: str | None = None
    address: str | None = None
    contact_person: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    status: SupplierStatus = SupplierStatus.ACTIVE

    @field_validator("supplier_code")
    @classmethod
    def code_uppercase(cls, v: str) -> str:
        v = v.strip().upper()
        if not v:
            raise ValueError("supplier_code cannot be blank")
        return v

    @field_validator("supplier_name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("supplier_name cannot be blank")
        return v.strip()


class SupplierUpdate(BaseModel):
    supplier_name: str | None = None
    gst_number: str | None = None
    drug_license_number: str | None = None
    address: str | None = None
    contact_person: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    status: SupplierStatus | None = None


class SupplierRead(BaseModel):
    id: UUID
    supplier_code: str
    supplier_name: str
    gst_number: str | None
    drug_license_number: str | None
    address: str | None
    contact_person: str | None
    email: str | None
    phone: str | None
    status: SupplierStatus
    tenant_id: UUID | None = None

    model_config = {"from_attributes": True}
