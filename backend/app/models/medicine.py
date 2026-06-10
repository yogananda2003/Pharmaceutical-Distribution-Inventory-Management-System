from __future__ import annotations

import enum

from sqlalchemy import Enum, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TenantedEntity


class DosageForm(enum.StrEnum):
    TABLET = "tablet"
    CAPSULE = "capsule"
    INJECTION = "injection"
    SYRUP = "syrup"
    OINTMENT = "ointment"
    DROPS = "drops"
    POWDER = "powder"
    CREAM = "cream"
    GEL = "gel"
    INHALER = "inhaler"


class MedicineStatus(enum.StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    DISCONTINUED = "discontinued"


class Medicine(TenantedEntity):
    __tablename__ = "medicines"

    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    generic_name: Mapped[str] = mapped_column(String(255), nullable=False)
    manufacturer: Mapped[str] = mapped_column(String(255), nullable=False)
    dosage: Mapped[str] = mapped_column(String(100), nullable=False)
    strength: Mapped[str] = mapped_column(String(100), nullable=False)
    dosage_form: Mapped[DosageForm] = mapped_column(
        Enum(DosageForm, name="dosage_form", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )
    unit_type: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[MedicineStatus] = mapped_column(
        Enum(
            MedicineStatus,
            name="medicine_status",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=MedicineStatus.ACTIVE,
    )
