"""Celery task: scan all active batches for 30/60/90-day expiry thresholds."""

from __future__ import annotations

import asyncio

from app.core.logging import get_logger
from app.workers.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(name="expiry_alerts.scan", bind=True, max_retries=3)  # type: ignore[untyped-decorator]
def scan_expiry_alerts(self: object) -> dict[str, object]:
    """Scan inventory batches and log expiry alert summary.

    Runs the ExpiryAlertService synchronously via asyncio.run so it can be
    dispatched by Celery without an async worker.  Safe to call as
    scan_expiry_alerts.apply() in unit tests (no broker required).
    """

    async def _run() -> dict[str, object]:
        from app.core.db import get_session_local
        from app.services.expiry_alert import ExpiryAlertService

        async with get_session_local()() as session:
            svc = ExpiryAlertService(session)
            dashboard = await svc.get_expiry_dashboard()

        logger.info(
            "expiry_scan_complete",
            expired=dashboard.expired_count,
            within_30d=dashboard.expiring_within_30d,
            within_60d=dashboard.expiring_within_60d,
            within_90d=dashboard.expiring_within_90d,
        )
        return dashboard.model_dump(mode="json")

    return asyncio.run(_run())
