from __future__ import annotations

from datetime import date
from uuid import UUID

from pydantic import BaseModel


class BatchExpiryInfo(BaseModel):
    batch_id: UUID
    batch_number: str
    medicine_id: UUID
    medicine_code: str
    medicine_name: str
    warehouse_id: UUID
    warehouse_name: str
    expiry_date: date
    days_to_expiry: int
    quantity_available: int
    quantity_reserved: int
    alert_level: str


class ExpiryDashboard(BaseModel):
    as_of: date
    expired_count: int
    expiring_within_30d: int
    expiring_within_60d: int
    expiring_within_90d: int
