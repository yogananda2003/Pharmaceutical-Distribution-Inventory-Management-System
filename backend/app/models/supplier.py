from __future__ import annotations

import enum

from sqlalchemy import Enum, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TenantedEntity


class SupplierStatus(enum.StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    BLACKLISTED = "blacklisted"


class Supplier(TenantedEntity):
    __tablename__ = "suppliers"

    supplier_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    supplier_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    gst_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    drug_license_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    contact_person: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    status: Mapped[SupplierStatus] = mapped_column(
        Enum(
            SupplierStatus,
            name="supplier_status",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=SupplierStatus.ACTIVE,
    )
