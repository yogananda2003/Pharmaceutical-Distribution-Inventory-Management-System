from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, field_validator

from app.models.medicine import DosageForm, MedicineStatus


class MedicineCreate(BaseModel):
    code: str
    name: str
    generic_name: str
    manufacturer: str
    dosage: str
    strength: str
    dosage_form: DosageForm
    unit_type: str
    description: str | None = None
    status: MedicineStatus = MedicineStatus.ACTIVE

    @field_validator("code")
    @classmethod
    def code_uppercase(cls, v: str) -> str:
        v = v.strip().upper()
        if not v:
            raise ValueError("code cannot be blank")
        return v

    @field_validator("name", "generic_name", "manufacturer", "dosage", "strength", "unit_type")
    @classmethod
    def no_blank_strings(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("field cannot be blank")
        return v.strip()


class MedicineUpdate(BaseModel):
    name: str | None = None
    generic_name: str | None = None
    manufacturer: str | None = None
    dosage: str | None = None
    strength: str | None = None
    dosage_form: DosageForm | None = None
    unit_type: str | None = None
    description: str | None = None
    status: MedicineStatus | None = None


class MedicineRead(BaseModel):
    id: UUID
    code: str
    name: str
    generic_name: str
    manufacturer: str
    dosage: str
    strength: str
    dosage_form: DosageForm
    unit_type: str
    description: str | None
    status: MedicineStatus
    tenant_id: UUID | None = None

    model_config = {"from_attributes": True}
