from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.db import AsyncSession, get_db
from app.core.deps import CurrentUser, require_roles
from app.core.responses import success_envelope
from app.models.user import UserRole
from app.schemas.warehouse import WarehouseCreate, WarehouseRead, WarehouseUpdate
from app.services.warehouse import WarehouseService

router = APIRouter(prefix="/warehouses", tags=["warehouses"])

_WRITE_ROLES = (UserRole.ADMIN, UserRole.INVENTORY_MANAGER)
_READ_ROLES = (
    UserRole.ADMIN,
    UserRole.INVENTORY_MANAGER,
    UserRole.SALES_REPRESENTATIVE,
    UserRole.WAREHOUSE_STAFF,
)


def _svc(session: AsyncSession = Depends(get_db)) -> WarehouseService:
    return WarehouseService(session)


@router.post(
    "",
    response_model=None,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(*_WRITE_ROLES))],
)
async def create_warehouse(
    body: WarehouseCreate,
    current_user: CurrentUser,
    svc: WarehouseService = Depends(_svc),
) -> dict[str, object]:
    try:
        warehouse = await svc.create(body, tenant_id=current_user.tenant_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return success_envelope(WarehouseRead.model_validate(warehouse).model_dump())


@router.get(
    "",
    response_model=None,
    dependencies=[Depends(require_roles(*_READ_ROLES))],
)
async def list_warehouses(
    active_only: bool = Query(default=False),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    svc: WarehouseService = Depends(_svc),
) -> dict[str, object]:
    if active_only:
        warehouses = await svc.list_active(limit=limit, offset=offset)
    else:
        warehouses = await svc.list_warehouses(limit=limit, offset=offset)
    return success_envelope([WarehouseRead.model_validate(w).model_dump() for w in warehouses])


@router.get(
    "/{warehouse_id}",
    response_model=None,
    dependencies=[Depends(require_roles(*_READ_ROLES))],
)
async def get_warehouse(
    warehouse_id: UUID,
    svc: WarehouseService = Depends(_svc),
) -> dict[str, object]:
    try:
        warehouse = await svc.get(warehouse_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return success_envelope(WarehouseRead.model_validate(warehouse).model_dump())


@router.put(
    "/{warehouse_id}",
    response_model=None,
    dependencies=[Depends(require_roles(*_WRITE_ROLES))],
)
async def update_warehouse(
    warehouse_id: UUID,
    body: WarehouseUpdate,
    svc: WarehouseService = Depends(_svc),
) -> dict[str, object]:
    try:
        warehouse = await svc.update(warehouse_id, body)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return success_envelope(WarehouseRead.model_validate(warehouse).model_dump())


@router.delete(
    "/{warehouse_id}",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_roles(*_WRITE_ROLES))],
)
async def delete_warehouse(
    warehouse_id: UUID,
    svc: WarehouseService = Depends(_svc),
) -> None:
    try:
        await svc.delete(warehouse_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
