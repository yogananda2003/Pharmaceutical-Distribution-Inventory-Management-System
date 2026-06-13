"""Expiry Alert Service.

Three responsibilities:

get_expiry_dashboard  Return counts of expired/near-expiry batches at the
    30/60/90-day thresholds, using two DB queries (expired + near-90d).

get_expired_batches  List non-exhausted ACTIVE/QUARANTINE batches whose
    expiry_date is strictly before today.

get_near_expiry_batches(threshold_days)  List ACTIVE batches expiring within
    the next N days (today inclusive, exclusive of already-expired batches).

Alert levels (in BatchExpiryInfo.alert_level):
  expired   — days_to_expiry < 0
  critical  — 0 <= days_to_expiry <= 30
  warning   — 31–60
  caution   — 61–90
"""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory_batch import InventoryBatch
from app.repositories.inventory_batch import InventoryBatchRepository
from app.schemas.expiry_alert import BatchExpiryInfo, ExpiryDashboard


def _alert_level(days: int) -> str:
    if days < 0:
        return "expired"
    if days <= 30:
        return "critical"
    if days <= 60:
        return "warning"
    return "caution"


def _to_info(batch: InventoryBatch, today: date) -> BatchExpiryInfo:
    days = (batch.expiry_date - today).days
    return BatchExpiryInfo(
        batch_id=batch.id,
        batch_number=batch.batch_number,
        medicine_id=batch.medicine_id,
        medicine_code=batch.medicine.code,
        medicine_name=batch.medicine.name,
        warehouse_id=batch.warehouse_id,
        warehouse_name=batch.warehouse.warehouse_name,
        expiry_date=batch.expiry_date,
        days_to_expiry=days,
        quantity_available=batch.quantity_available,
        quantity_reserved=batch.quantity_reserved,
        alert_level=_alert_level(days),
    )


class ExpiryAlertService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = InventoryBatchRepository(session)

    async def get_expiry_dashboard(self) -> ExpiryDashboard:
        today = date.today()
        d90 = today + timedelta(days=90)

        expired = await self._repo.list_expiring_before(today)
        near = await self._repo.list_near_expiry(today, d90)

        count_30 = sum(1 for b in near if b.expiry_date <= today + timedelta(days=30))
        count_60 = sum(1 for b in near if b.expiry_date <= today + timedelta(days=60))

        return ExpiryDashboard(
            as_of=today,
            expired_count=len(expired),
            expiring_within_30d=count_30,
            expiring_within_60d=count_60,
            expiring_within_90d=len(near),
        )

    async def get_expired_batches(self) -> list[BatchExpiryInfo]:
        today = date.today()
        batches = await self._repo.list_expiring_before(today)
        return [_to_info(b, today) for b in batches]

    async def get_near_expiry_batches(self, threshold_days: int) -> list[BatchExpiryInfo]:
        if threshold_days not in (30, 60, 90):
            raise ValueError("threshold_days must be 30, 60, or 90")
        today = date.today()
        cutoff = today + timedelta(days=threshold_days)
        batches = await self._repo.list_near_expiry(today, cutoff)
        return [_to_info(b, today) for b in batches]
