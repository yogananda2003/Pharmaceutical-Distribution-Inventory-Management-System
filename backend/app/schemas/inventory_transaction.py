from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.models.inventory_transaction import TransactionType


class TransactionRead(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    batch_id: UUID
    transaction_type: TransactionType
    quantity: int
    reference_number: str | None
    remarks: str | None
    created_by: UUID | None
    created_at: datetime
