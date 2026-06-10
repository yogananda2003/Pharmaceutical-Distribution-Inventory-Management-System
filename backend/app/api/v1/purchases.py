from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.db import AsyncSession, get_db
from app.core.deps import CurrentUser, require_roles
from app.core.responses import success_envelope
from app.models.purchase_order import PurchaseStatus
from app.models.user import UserRole
from app.schemas.purchase_order import (
    GoodsReceiptRequest,
    PurchaseOrderCreate,
    PurchaseOrderRead,
    PurchaseStatusUpdate,
)
from app.services.purchase_order import PurchaseOrderService
from app.services.purchase_receipt import PurchaseReceiptService

router = APIRouter(prefix="/purchases", tags=["purchases"])

_WRITE_ROLES = (UserRole.ADMIN, UserRole.INVENTORY_MANAGER)
_READ_ROLES = (
    UserRole.ADMIN,
    UserRole.INVENTORY_MANAGER,
    UserRole.WAREHOUSE_STAFF,
    UserRole.SALES_REPRESENTATIVE,
)
_RECEIPT_ROLES = (
    UserRole.ADMIN,
    UserRole.INVENTORY_MANAGER,
    UserRole.WAREHOUSE_STAFF,
)


def _svc(session: AsyncSession = Depends(get_db)) -> PurchaseOrderService:
    return PurchaseOrderService(session)


def _receipt_svc(session: AsyncSession = Depends(get_db)) -> PurchaseReceiptService:
    return PurchaseReceiptService(session)


# ── create ─────────────────────────────────────────────────────────────────────


@router.post(
    "",
    response_model=None,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(*_WRITE_ROLES))],
)
async def create_purchase_order(
    body: PurchaseOrderCreate,
    current_user: CurrentUser,
    svc: PurchaseOrderService = Depends(_svc),
) -> dict[str, object]:
    try:
        po = await svc.create(body, tenant_id=current_user.tenant_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return success_envelope(PurchaseOrderRead.model_validate(po).model_dump(mode="json"))


# ── list ───────────────────────────────────────────────────────────────────────


@router.get(
    "",
    response_model=None,
    dependencies=[Depends(require_roles(*_READ_ROLES))],
)
async def list_purchase_orders(
    supplier_id: UUID | None = Query(None),
    status_filter: PurchaseStatus | None = Query(None, alias="status"),
    svc: PurchaseOrderService = Depends(_svc),
) -> dict[str, object]:
    pos = await svc.list_all(supplier_id=supplier_id, status=status_filter)
    return success_envelope(
        [PurchaseOrderRead.model_validate(p).model_dump(mode="json") for p in pos]
    )


# ── get by id ──────────────────────────────────────────────────────────────────


@router.get(
    "/{po_id}",
    response_model=None,
    dependencies=[Depends(require_roles(*_READ_ROLES))],
)
async def get_purchase_order(
    po_id: UUID,
    svc: PurchaseOrderService = Depends(_svc),
) -> dict[str, object]:
    try:
        po = await svc.get(po_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return success_envelope(PurchaseOrderRead.model_validate(po).model_dump(mode="json"))


# ── status transition ──────────────────────────────────────────────────────────


@router.patch(
    "/{po_id}/status",
    response_model=None,
    dependencies=[Depends(require_roles(*_WRITE_ROLES))],
)
async def update_purchase_order_status(
    po_id: UUID,
    body: PurchaseStatusUpdate,
    svc: PurchaseOrderService = Depends(_svc),
) -> dict[str, object]:
    try:
        po = await svc.transition_status(po_id, body.status)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return success_envelope(PurchaseOrderRead.model_validate(po).model_dump(mode="json"))


# ── goods receipt ──────────────────────────────────────────────────────────────


@router.post(
    "/{po_id}/receive",
    response_model=None,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_roles(*_RECEIPT_ROLES))],
)
async def receive_goods(
    po_id: UUID,
    body: GoodsReceiptRequest,
    current_user: CurrentUser,
    svc: PurchaseReceiptService = Depends(_receipt_svc),
) -> dict[str, object]:
    try:
        result = await svc.receive(po_id, body, created_by=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return success_envelope(result.model_dump(mode="json"))


# ── delete (DRAFT/CANCELLED only) ─────────────────────────────────────────────


@router.delete(
    "/{po_id}",
    response_model=None,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_roles(*_WRITE_ROLES))],
)
async def delete_purchase_order(
    po_id: UUID,
    svc: PurchaseOrderService = Depends(_svc),
) -> dict[str, object]:
    try:
        await svc.delete(po_id)
    except ValueError as exc:
        detail = str(exc)
        http_status = (
            status.HTTP_404_NOT_FOUND if "not found" in detail else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=http_status, detail=detail) from exc
    return success_envelope({"deleted": True})
