from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.db import AsyncSession, get_db
from app.core.deps import require_roles
from app.core.responses import success_envelope
from app.models.user import UserRole
from app.services.expiry_alert import ExpiryAlertService

router = APIRouter(prefix="/expiry", tags=["expiry-alerts"])

_VIEW_ROLES = (
    UserRole.ADMIN,
    UserRole.INVENTORY_MANAGER,
    UserRole.WAREHOUSE_STAFF,
)


def _svc(session: AsyncSession = Depends(get_db)) -> ExpiryAlertService:
    return ExpiryAlertService(session)


@router.get("/dashboard", dependencies=[Depends(require_roles(*_VIEW_ROLES))])
async def get_expiry_dashboard(
    svc: ExpiryAlertService = Depends(_svc),
) -> dict[str, object]:
    """Summary counts at 30/60/90-day thresholds and total expired."""
    dashboard = await svc.get_expiry_dashboard()
    return success_envelope(dashboard.model_dump(mode="json"))


@router.get("/expired", dependencies=[Depends(require_roles(*_VIEW_ROLES))])
async def list_expired_batches(
    svc: ExpiryAlertService = Depends(_svc),
) -> dict[str, object]:
    """All non-exhausted batches whose expiry_date is before today."""
    batches = await svc.get_expired_batches()
    return success_envelope([b.model_dump(mode="json") for b in batches])


@router.get("/near-expiry", dependencies=[Depends(require_roles(*_VIEW_ROLES))])
async def list_near_expiry_batches(
    days: int = Query(30, description="Threshold window: 30, 60, or 90"),
    svc: ExpiryAlertService = Depends(_svc),
) -> dict[str, object]:
    """ACTIVE batches expiring within the next N days (30, 60, or 90)."""
    try:
        batches = await svc.get_near_expiry_batches(days)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from None
    return success_envelope([b.model_dump(mode="json") for b in batches])
