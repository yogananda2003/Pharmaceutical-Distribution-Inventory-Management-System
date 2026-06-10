from __future__ import annotations

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import TenantedEntity


class Warehouse(TenantedEntity):
    __tablename__ = "warehouses"

    warehouse_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    warehouse_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    contact_details: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
