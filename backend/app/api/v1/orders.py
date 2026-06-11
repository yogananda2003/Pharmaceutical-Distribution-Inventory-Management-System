from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.db import AsyncSession, get_db
from app.core.deps import CurrentUser, require_roles
from app.core.responses import success_envelope
from app.models.customer_order import OrderStatus
from app.models.user import UserRole
from app.schemas.customer_order import OrderCreate, OrderRead, OrderStatusUpdate
from app.services.customer_order import CustomerOrderService
from app.services.order_fulfillment import OrderFulfillmentService

router = APIRouter(prefix="/orders", tags=["orders"])

_WRITE_ROLES = (
    UserRole.ADMIN,
    UserRole.INVENTORY_MANAGER,
    UserRole.SALES_REPRESENTATIVE,
)
_READ_ROLES = (
    UserRole.ADMIN,
    UserRole.INVENTORY_MANAGER,
    UserRole.SALES_REPRESENTATIVE,
    UserRole.WAREHOUSE_STAFF,
)
_APPROVE_ROLES = (UserRole.ADMIN, UserRole.INVENTORY_MANAGER)
_WAREHOUSE_ROLES = (UserRole.ADMIN, UserRole.INVENTORY_MANAGER, UserRole.WAREHOUSE_STAFF)


def _svc(session: AsyncSession = Depends(get_db)) -> CustomerOrderService:
    return CustomerOrderService(session)


def _fulfillment_svc(session: AsyncSession = Depends(get_db)) -> OrderFulfillmentService:
    return OrderFulfillmentService(session)


# ── create ─────────────────────────────────────────────────────────────────────


@router.post(
    "",
    response_model=None,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(*_WRITE_ROLES))],
)
async def create_order(
    body: OrderCreate,
    current_user: CurrentUser,
    svc: CustomerOrderService = Depends(_svc),
) -> dict[str, object]:
    try:
        order = await svc.create(body, tenant_id=current_user.tenant_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return success_envelope(OrderRead.model_validate(order).model_dump(mode="json"))


# ── list ───────────────────────────────────────────────────────────────────────


@router.get(
    "",
    response_model=None,
    dependencies=[Depends(require_roles(*_READ_ROLES))],
)
async def list_orders(
    customer_id: UUID | None = Query(None),
    status_filter: OrderStatus | None = Query(None, alias="status"),
    svc: CustomerOrderService = Depends(_svc),
) -> dict[str, object]:
    orders = await svc.list_all(customer_id=customer_id, status=status_filter)
    return success_envelope([OrderRead.model_validate(o).model_dump(mode="json") for o in orders])


# ── get by id ──────────────────────────────────────────────────────────────────


@router.get(
    "/{order_id}",
    response_model=None,
    dependencies=[Depends(require_roles(*_READ_ROLES))],
)
async def get_order(
    order_id: UUID,
    svc: CustomerOrderService = Depends(_svc),
) -> dict[str, object]:
    try:
        order = await svc.get(order_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return success_envelope(OrderRead.model_validate(order).model_dump(mode="json"))


# ── generic status transition ──────────────────────────────────────────────────


@router.patch(
    "/{order_id}/status",
    response_model=None,
    dependencies=[Depends(require_roles(*_WRITE_ROLES))],
)
async def update_order_status(
    order_id: UUID,
    body: OrderStatusUpdate,
    svc: CustomerOrderService = Depends(_svc),
) -> dict[str, object]:
    try:
        order = await svc.transition_status(order_id, body.status)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return success_envelope(OrderRead.model_validate(order).model_dump(mode="json"))


# ── approve (PLACED → APPROVED + FEFO reserve) ────────────────────────────────


@router.post(
    "/{order_id}/approve",
    response_model=None,
    dependencies=[Depends(require_roles(*_APPROVE_ROLES))],
)
async def approve_order(
    order_id: UUID,
    current_user: CurrentUser,
    svc: OrderFulfillmentService = Depends(_fulfillment_svc),
) -> dict[str, object]:
    try:
        order = await svc.approve_order(order_id, created_by=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return success_envelope(OrderRead.model_validate(order).model_dump(mode="json"))


# ── dispatch (PACKED → DISPATCHED + STOCK_OUT) ────────────────────────────────


@router.post(
    "/{order_id}/dispatch",
    response_model=None,
    dependencies=[Depends(require_roles(*_WAREHOUSE_ROLES))],
)
async def dispatch_order(
    order_id: UUID,
    current_user: CurrentUser,
    svc: OrderFulfillmentService = Depends(_fulfillment_svc),
) -> dict[str, object]:
    try:
        order = await svc.dispatch_order(order_id, created_by=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return success_envelope(OrderRead.model_validate(order).model_dump(mode="json"))


# ── cancel (any cancellable → CANCELLED + release) ────────────────────────────


@router.post(
    "/{order_id}/cancel",
    response_model=None,
    dependencies=[Depends(require_roles(*_WRITE_ROLES))],
)
async def cancel_order(
    order_id: UUID,
    current_user: CurrentUser,
    svc: OrderFulfillmentService = Depends(_fulfillment_svc),
) -> dict[str, object]:
    try:
        order = await svc.cancel_order(order_id, created_by=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return success_envelope(OrderRead.model_validate(order).model_dump(mode="json"))


# ── delete (DRAFT only) ────────────────────────────────────────────────────────


@router.delete(
    "/{order_id}",
    response_model=None,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_roles(*_WRITE_ROLES))],
)
async def delete_order(
    order_id: UUID,
    svc: CustomerOrderService = Depends(_svc),
) -> dict[str, object]:
    try:
        await svc.delete(order_id)
    except ValueError as exc:
        detail = str(exc)
        http_status = (
            status.HTTP_404_NOT_FOUND if "not found" in detail else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=http_status, detail=detail) from exc
    return success_envelope({"deleted": True})
