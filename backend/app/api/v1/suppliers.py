from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.db import AsyncSession, get_db
from app.core.deps import CurrentUser, require_roles
from app.core.responses import success_envelope
from app.models.user import UserRole
from app.schemas.supplier import SupplierCreate, SupplierRead, SupplierUpdate
from app.services.supplier import SupplierService

router = APIRouter(prefix="/suppliers", tags=["suppliers"])

_WRITE_ROLES = (UserRole.ADMIN, UserRole.INVENTORY_MANAGER)
_READ_ROLES = (
    UserRole.ADMIN,
    UserRole.INVENTORY_MANAGER,
    UserRole.SALES_REPRESENTATIVE,
    UserRole.WAREHOUSE_STAFF,
)


def _svc(session: AsyncSession = Depends(get_db)) -> SupplierService:
    return SupplierService(session)


@router.post(
    "",
    response_model=None,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(*_WRITE_ROLES))],
)
async def create_supplier(
    body: SupplierCreate,
    current_user: CurrentUser,
    svc: SupplierService = Depends(_svc),
) -> dict[str, object]:
    try:
        supplier = await svc.create(body, tenant_id=current_user.tenant_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return success_envelope(SupplierRead.model_validate(supplier).model_dump())


@router.get(
    "",
    response_model=None,
    dependencies=[Depends(require_roles(*_READ_ROLES))],
)
async def list_suppliers(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    svc: SupplierService = Depends(_svc),
) -> dict[str, object]:
    suppliers = await svc.list_suppliers(limit=limit, offset=offset)
    return success_envelope([SupplierRead.model_validate(s).model_dump() for s in suppliers])


@router.get(
    "/{supplier_id}",
    response_model=None,
    dependencies=[Depends(require_roles(*_READ_ROLES))],
)
async def get_supplier(
    supplier_id: UUID,
    svc: SupplierService = Depends(_svc),
) -> dict[str, object]:
    try:
        supplier = await svc.get(supplier_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return success_envelope(SupplierRead.model_validate(supplier).model_dump())


@router.put(
    "/{supplier_id}",
    response_model=None,
    dependencies=[Depends(require_roles(*_WRITE_ROLES))],
)
async def update_supplier(
    supplier_id: UUID,
    body: SupplierUpdate,
    svc: SupplierService = Depends(_svc),
) -> dict[str, object]:
    try:
        supplier = await svc.update(supplier_id, body)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return success_envelope(SupplierRead.model_validate(supplier).model_dump())


@router.delete(
    "/{supplier_id}",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_roles(*_WRITE_ROLES))],
)
async def delete_supplier(
    supplier_id: UUID,
    svc: SupplierService = Depends(_svc),
) -> None:
    try:
        await svc.delete(supplier_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
