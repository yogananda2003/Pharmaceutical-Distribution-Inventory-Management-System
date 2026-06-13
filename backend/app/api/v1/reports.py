"""Stage 14 — Reporting module.

Eight read-only report endpoints.  All return the standard success envelope.

Roles:
  Inventory reports (current, batches, expiry, movements):
    ADMIN, INVENTORY_MANAGER, WAREHOUSE_STAFF
  Business reports (purchases, sales, customers, fulfillment):
    ADMIN, INVENTORY_MANAGER, SALES_REPRESENTATIVE
"""

from __future__ import annotations

import datetime as dt
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.core.db import AsyncSession, get_db
from app.core.deps import require_roles
from app.core.responses import success_envelope
from app.models.inventory_batch import BatchStatus
from app.models.inventory_transaction import TransactionType
from app.models.user import UserRole
from app.services.reports import ReportsService

router = APIRouter(prefix="/reports", tags=["reports"])

_ADMIN = UserRole.ADMIN
_INV = UserRole.INVENTORY_MANAGER
_SALES = UserRole.SALES_REPRESENTATIVE
_WH = UserRole.WAREHOUSE_STAFF

_INVENTORY_ROLES = (_ADMIN, _INV, _WH)
_BUSINESS_ROLES = (_ADMIN, _INV, _SALES)


def _svc(session: AsyncSession = Depends(get_db)) -> ReportsService:
    return ReportsService(session)


# ── 1. Current inventory ───────────────────────────────────────────────────────


@router.get(
    "/inventory/current",
    dependencies=[Depends(require_roles(*_INVENTORY_ROLES))],
)
async def report_current_inventory(
    warehouse_id: UUID | None = Query(None),
    medicine_id: UUID | None = Query(None),
    svc: ReportsService = Depends(_svc),
) -> dict[str, object]:
    """Per-medicine aggregated stock (available + reserved) across active batches."""
    data = await svc.current_inventory(warehouse_id=warehouse_id, medicine_id=medicine_id)
    return success_envelope([r.model_dump(mode="json") for r in data])


# ── 2. Batch inventory ─────────────────────────────────────────────────────────


@router.get(
    "/inventory/batches",
    dependencies=[Depends(require_roles(*_INVENTORY_ROLES))],
)
async def report_batch_inventory(
    warehouse_id: UUID | None = Query(None),
    medicine_id: UUID | None = Query(None),
    status: BatchStatus | None = Query(None),
    expiry_before: dt.date | None = Query(None),
    expiry_after: dt.date | None = Query(None),
    limit: int = Query(500, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    svc: ReportsService = Depends(_svc),
) -> dict[str, object]:
    """Per-batch detail with expiry days and optional warehouse/medicine/status filters."""
    data = await svc.batch_inventory(
        warehouse_id=warehouse_id,
        medicine_id=medicine_id,
        status=status,
        expiry_before=expiry_before,
        expiry_after=expiry_after,
        limit=limit,
        offset=offset,
    )
    return success_envelope([r.model_dump(mode="json") for r in data])


# ── 3. Expiry report ───────────────────────────────────────────────────────────


@router.get(
    "/inventory/expiry",
    dependencies=[Depends(require_roles(*_INVENTORY_ROLES))],
)
async def report_expiry(
    svc: ReportsService = Depends(_svc),
) -> dict[str, object]:
    """All expired batches followed by batches expiring within 90 days, with alert_level."""
    data = await svc.expiry_report()
    return success_envelope([r.model_dump(mode="json") for r in data])


# ── 4. Stock movements ─────────────────────────────────────────────────────────


@router.get(
    "/transactions",
    dependencies=[Depends(require_roles(*_INVENTORY_ROLES))],
)
async def report_stock_movements(
    date_from: dt.date | None = Query(None),
    date_to: dt.date | None = Query(None),
    transaction_type: TransactionType | None = Query(None),
    medicine_id: UUID | None = Query(None),
    warehouse_id: UUID | None = Query(None),
    limit: int = Query(500, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    svc: ReportsService = Depends(_svc),
) -> dict[str, object]:
    """Inventory transaction ledger with date, type, medicine, and warehouse filters."""
    data = await svc.stock_movements(
        date_from=date_from,
        date_to=date_to,
        transaction_type=transaction_type,
        medicine_id=medicine_id,
        warehouse_id=warehouse_id,
        limit=limit,
        offset=offset,
    )
    return success_envelope([r.model_dump(mode="json") for r in data])


# ── 5. Purchase report ─────────────────────────────────────────────────────────


@router.get(
    "/purchases",
    dependencies=[Depends(require_roles(*_BUSINESS_ROLES))],
)
async def report_purchases(
    date_from: dt.date | None = Query(None),
    date_to: dt.date | None = Query(None),
    status: str | None = Query(None),
    supplier_id: UUID | None = Query(None),
    limit: int = Query(500, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    svc: ReportsService = Depends(_svc),
) -> dict[str, object]:
    """Purchase order summary with supplier, quantity totals, and status."""
    data = await svc.purchase_summary(
        date_from=date_from,
        date_to=date_to,
        status=status,
        supplier_id=supplier_id,
        limit=limit,
        offset=offset,
    )
    return success_envelope([r.model_dump(mode="json") for r in data])


# ── 6. Sales report ────────────────────────────────────────────────────────────


@router.get(
    "/sales",
    dependencies=[Depends(require_roles(*_BUSINESS_ROLES))],
)
async def report_sales(
    date_from: dt.date | None = Query(None),
    date_to: dt.date | None = Query(None),
    status: str | None = Query(None),
    customer_id: UUID | None = Query(None),
    limit: int = Query(500, ge=1, le=2000),
    offset: int = Query(0, ge=0),
    svc: ReportsService = Depends(_svc),
) -> dict[str, object]:
    """Customer order summary with linked invoice status."""
    data = await svc.sales_summary(
        date_from=date_from,
        date_to=date_to,
        status=status,
        customer_id=customer_id,
        limit=limit,
        offset=offset,
    )
    return success_envelope([r.model_dump(mode="json") for r in data])


# ── 7. Customer report ─────────────────────────────────────────────────────────


@router.get(
    "/customers",
    dependencies=[Depends(require_roles(*_BUSINESS_ROLES))],
)
async def report_customers(
    customer_id: UUID | None = Query(None),
    svc: ReportsService = Depends(_svc),
) -> dict[str, object]:
    """Customer account summary: order count, total value, completed orders."""
    data = await svc.customer_summary(customer_id=customer_id)
    return success_envelope([r.model_dump(mode="json") for r in data])


# ── 8. Order fulfillment ───────────────────────────────────────────────────────


@router.get(
    "/orders/fulfillment",
    dependencies=[Depends(require_roles(*_BUSINESS_ROLES))],
)
async def report_order_fulfillment(
    date_from: dt.date | None = Query(None),
    date_to: dt.date | None = Query(None),
    svc: ReportsService = Depends(_svc),
) -> dict[str, object]:
    """Order counts and values grouped by lifecycle status."""
    data = await svc.order_fulfillment(date_from=date_from, date_to=date_to)
    return success_envelope(data.model_dump(mode="json"))
