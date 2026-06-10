from __future__ import annotations

import enum
from decimal import Decimal

from sqlalchemy import Enum, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TenantedEntity


class CustomerStatus(enum.StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    BLACKLISTED = "blacklisted"


class Customer(TenantedEntity):
    __tablename__ = "customers"

    customer_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    business_name: Mapped[str] = mapped_column(String(200), nullable=False)
    contact_person: Mapped[str | None] = mapped_column(String(150), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    gst_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    drug_license_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    credit_limit: Mapped[Decimal] = mapped_column(
        Numeric(precision=12, scale=2), nullable=False, default=Decimal("0.00")
    )
    status: Mapped[CustomerStatus] = mapped_column(
        Enum(
            CustomerStatus,
            name="customer_status",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=CustomerStatus.ACTIVE,
    )
