from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.db import AsyncSession, get_db
from app.core.deps import CurrentUser, require_roles
from app.core.responses import success_envelope
from app.models.user import UserRole
from app.schemas.warehouse_ops import StockTransferRequest
from app.services.warehouse_ops import WarehouseOpsService

router = APIRouter(prefix="/warehouse", tags=["warehouse"])

_WAREHOUSE_ROLES = (
    UserRole.ADMIN,
    UserRole.INVENTORY_MANAGER,
    UserRole.WAREHOUSE_STAFF,
)


def _svc(session: AsyncSession = Depends(get_db)) -> WarehouseOpsService:
    return WarehouseOpsService(session)


@router.get(
    "/pending",
    response_model=None,
    dependencies=[Depends(require_roles(*_WAREHOUSE_ROLES))],
)
async def list_pending_orders(
    svc: WarehouseOpsService = Depends(_svc),
) -> dict[str, object]:
    summaries = await svc.get_pending_orders()
    return success_envelope([s.model_dump(mode="json") for s in summaries])


@router.get(
    "/orders/{order_id}/pick-list",
    response_model=None,
    dependencies=[Depends(require_roles(*_WAREHOUSE_ROLES))],
)
async def get_pick_list(
    order_id: UUID,
    svc: WarehouseOpsService = Depends(_svc),
) -> dict[str, object]:
    try:
        pick_list = await svc.get_pick_list(order_id)
    except ValueError as exc:
        detail = str(exc)
        http_status = (
            status.HTTP_404_NOT_FOUND if "not found" in detail else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=http_status, detail=detail) from exc
    return success_envelope(pick_list.model_dump(mode="json"))


@router.post(
    "/transfer",
    response_model=None,
    dependencies=[Depends(require_roles(*_WAREHOUSE_ROLES))],
)
async def transfer_stock(
    body: StockTransferRequest,
    current_user: CurrentUser,
    svc: WarehouseOpsService = Depends(_svc),
) -> dict[str, object]:
    try:
        result = await svc.transfer_stock(
            body.source_batch_id,
            body.destination_batch_id,
            body.quantity,
            created_by=current_user.id,
            reference_number=body.reference_number,
            remarks=body.remarks,
        )
    except ValueError as exc:
        detail = str(exc)
        http_status = (
            status.HTTP_404_NOT_FOUND if "not found" in detail else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=http_status, detail=detail) from exc
    return success_envelope(result.model_dump(mode="json"))
