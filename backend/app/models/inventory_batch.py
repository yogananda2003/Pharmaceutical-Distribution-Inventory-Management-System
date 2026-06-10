from __future__ import annotations

import enum
from datetime import date
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Date, Enum, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import TenantedEntity

if TYPE_CHECKING:
    from app.models.inventory_transaction import InventoryTransaction
    from app.models.medicine import Medicine
    from app.models.warehouse import Warehouse


class BatchStatus(enum.StrEnum):
    ACTIVE = "active"
    QUARANTINE = "quarantine"
    EXHAUSTED = "exhausted"
    EXPIRED = "expired"


class InventoryBatch(TenantedEntity):
    __tablename__ = "inventory_batches"
    __table_args__ = (
        UniqueConstraint(
            "medicine_id", "warehouse_id", "batch_number",
            name="uq_batch_medicine_warehouse_number",
        ),
    )

    medicine_id: Mapped[UUID] = mapped_column(
        ForeignKey("medicines.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    warehouse_id: Mapped[UUID] = mapped_column(
        ForeignKey("warehouses.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    batch_number: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    manufacturing_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    quantity_available: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    quantity_reserved: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    quantity_damaged: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[BatchStatus] = mapped_column(
        Enum(
            BatchStatus,
            name="batch_status",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=BatchStatus.ACTIVE,
    )

    medicine: Mapped[Medicine] = relationship("Medicine", lazy="selectin")
    warehouse: Mapped[Warehouse] = relationship("Warehouse", lazy="selectin")
    transactions: Mapped[list[InventoryTransaction]] = relationship(
        "InventoryTransaction",
        back_populates="batch",
        lazy="select",
        order_by="InventoryTransaction.created_at",
    )
