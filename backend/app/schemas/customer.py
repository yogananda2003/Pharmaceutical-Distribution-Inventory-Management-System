from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator

from app.models.customer import CustomerStatus


class CustomerCreate(BaseModel):
    customer_code: str
    business_name: str
    contact_person: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    gst_number: str | None = None
    drug_license_number: str | None = None
    address: str | None = None
    credit_limit: Decimal = Decimal("0.00")
    status: CustomerStatus = CustomerStatus.ACTIVE

    @field_validator("customer_code")
    @classmethod
    def code_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("customer_code cannot be blank")
        return v.upper()

    @field_validator("business_name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("business_name cannot be blank")
        return v

    @field_validator("credit_limit")
    @classmethod
    def limit_non_negative(cls, v: Decimal) -> Decimal:
        if v < Decimal("0"):
            raise ValueError("credit_limit must be >= 0")
        return v.quantize(Decimal("0.01"))


class CustomerUpdate(BaseModel):
    business_name: str | None = None
    contact_person: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    gst_number: str | None = None
    drug_license_number: str | None = None
    address: str | None = None
    credit_limit: Decimal | None = None
    status: CustomerStatus | None = None

    @field_validator("credit_limit")
    @classmethod
    def limit_non_negative(cls, v: Decimal | None) -> Decimal | None:
        if v is not None and v < Decimal("0"):
            raise ValueError("credit_limit must be >= 0")
        if v is not None:
            return v.quantize(Decimal("0.01"))
        return v

    @field_validator("business_name")
    @classmethod
    def name_not_blank(cls, v: str | None) -> str | None:
        if v is not None:
            v = v.strip()
            if not v:
                raise ValueError("business_name cannot be blank")
        return v


class CustomerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    customer_code: str
    business_name: str
    contact_person: str | None
    email: str | None
    phone: str | None
    gst_number: str | None
    drug_license_number: str | None
    address: str | None
    credit_limit: Decimal
    status: CustomerStatus
    tenant_id: UUID | None
    created_at: datetime
    updated_at: datetime
