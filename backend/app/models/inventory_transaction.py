from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.base import UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.inventory_batch import InventoryBatch


class TransactionType(enum.StrEnum):
    STOCK_IN = "stock_in"
    STOCK_OUT = "stock_out"
    ADJUSTMENT = "adjustment"
    RETURN = "return"
    DAMAGE = "damage"
    TRANSFER = "transfer"
    ALLOCATION = "allocation"
    RELEASE = "release"


class InventoryTransaction(UUIDPrimaryKeyMixin, Base):
    """Immutable ledger — never soft-deleted, no updated_at.

    Every inventory movement creates exactly one row here; no rows are ever removed.
    """

    __tablename__ = "inventory_transactions"

    batch_id: Mapped[UUID] = mapped_column(
        ForeignKey("inventory_batches.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    transaction_type: Mapped[TransactionType] = mapped_column(
        Enum(
            TransactionType,
            name="transaction_type",
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        index=True,
    )
    # Positive for all types except ADJUSTMENT (which can be negative for corrections).
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    reference_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    batch: Mapped[InventoryBatch] = relationship(
        "InventoryBatch", back_populates="transactions", lazy="selectin"
    )
