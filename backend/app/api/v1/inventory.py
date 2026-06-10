from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.db import AsyncSession, get_db
from app.core.deps import CurrentUser, require_roles
from app.core.responses import success_envelope
from app.models.user import UserRole
from app.schemas.fefo import FEFOAllocationRequest, FEFOReleaseRequest
from app.schemas.inventory_batch import (
    AdjustRequest,
    AllocateRequest,
    BatchCreate,
    BatchRead,
    DamageRequest,
    ReleaseRequest,
    StockInRequest,
    StockOutRequest,
)
from app.schemas.inventory_transaction import TransactionRead
from app.services.fefo import FEFOService
from app.services.inventory_batch import InventoryBatchService

router = APIRouter(prefix="/inventory", tags=["inventory"])

_WRITE_ROLES = (UserRole.ADMIN, UserRole.INVENTORY_MANAGER)
_READ_ROLES = (
    UserRole.ADMIN,
    UserRole.INVENTORY_MANAGER,
    UserRole.WAREHOUSE_STAFF,
    UserRole.SALES_REPRESENTATIVE,
)
_WAREHOUSE_OPS_ROLES = (
    UserRole.ADMIN,
    UserRole.INVENTORY_MANAGER,
    UserRole.WAREHOUSE_STAFF,
)


def _svc(session: AsyncSession = Depends(get_db)) -> InventoryBatchService:
    return InventoryBatchService(session)


def _fefo_svc(session: AsyncSession = Depends(get_db)) -> FEFOService:
    return FEFOService(session)


# ── batch CRUD ────────────────────────────────────────────────────────────────


@router.post(
    "/batches",
    response_model=None,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(*_WRITE_ROLES))],
)
async def create_batch(
    body: BatchCreate,
    current_user: CurrentUser,
    svc: InventoryBatchService = Depends(_svc),
) -> dict[str, object]:
    try:
        batch = await svc.create_batch(
            body,
            tenant_id=current_user.tenant_id,
            created_by=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return success_envelope(BatchRead.model_validate(batch).model_dump())


@router.get(
    "/batches",
    response_model=None,
    dependencies=[Depends(require_roles(*_READ_ROLES))],
)
async def list_batches(
    active_only: bool = Query(default=False),
    medicine_id: UUID | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    svc: InventoryBatchService = Depends(_svc),
) -> dict[str, object]:
    if medicine_id is not None:
        batches = await svc.list_by_medicine(medicine_id, limit=limit, offset=offset)
    elif active_only:
        batches = await svc.list_active(limit=limit, offset=offset)
    else:
        batches = await svc.list_batches(limit=limit, offset=offset)
    return success_envelope([BatchRead.model_validate(b).model_dump() for b in batches])


@router.get(
    "/batches/{batch_id}",
    response_model=None,
    dependencies=[Depends(require_roles(*_READ_ROLES))],
)
async def get_batch(
    batch_id: UUID,
    svc: InventoryBatchService = Depends(_svc),
) -> dict[str, object]:
    try:
        batch = await svc.get(batch_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return success_envelope(BatchRead.model_validate(batch).model_dump())


# ── stock mutations ───────────────────────────────────────────────────────────


@router.post(
    "/batches/{batch_id}/stock-in",
    response_model=None,
    dependencies=[Depends(require_roles(*_WRITE_ROLES))],
)
async def stock_in(
    batch_id: UUID,
    body: StockInRequest,
    current_user: CurrentUser,
    svc: InventoryBatchService = Depends(_svc),
) -> dict[str, object]:
    try:
        batch = await svc.stock_in(batch_id, body, created_by=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return success_envelope(BatchRead.model_validate(batch).model_dump())


@router.post(
    "/batches/{batch_id}/adjust",
    response_model=None,
    dependencies=[Depends(require_roles(*_WRITE_ROLES))],
)
async def adjust(
    batch_id: UUID,
    body: AdjustRequest,
    current_user: CurrentUser,
    svc: InventoryBatchService = Depends(_svc),
) -> dict[str, object]:
    try:
        batch = await svc.adjust(batch_id, body, created_by=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return success_envelope(BatchRead.model_validate(batch).model_dump())


@router.post(
    "/batches/{batch_id}/damage",
    response_model=None,
    dependencies=[Depends(require_roles(*_WAREHOUSE_OPS_ROLES))],
)
async def damage(
    batch_id: UUID,
    body: DamageRequest,
    current_user: CurrentUser,
    svc: InventoryBatchService = Depends(_svc),
) -> dict[str, object]:
    try:
        batch = await svc.damage(batch_id, body, created_by=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return success_envelope(BatchRead.model_validate(batch).model_dump())


@router.post(
    "/batches/{batch_id}/allocate",
    response_model=None,
    dependencies=[Depends(require_roles(*_WRITE_ROLES))],
)
async def allocate(
    batch_id: UUID,
    body: AllocateRequest,
    current_user: CurrentUser,
    svc: InventoryBatchService = Depends(_svc),
) -> dict[str, object]:
    try:
        batch = await svc.allocate(batch_id, body, created_by=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return success_envelope(BatchRead.model_validate(batch).model_dump())


@router.post(
    "/batches/{batch_id}/release",
    response_model=None,
    dependencies=[Depends(require_roles(*_WRITE_ROLES))],
)
async def release(
    batch_id: UUID,
    body: ReleaseRequest,
    current_user: CurrentUser,
    svc: InventoryBatchService = Depends(_svc),
) -> dict[str, object]:
    try:
        batch = await svc.release(batch_id, body, created_by=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return success_envelope(BatchRead.model_validate(batch).model_dump())


@router.post(
    "/batches/{batch_id}/stock-out",
    response_model=None,
    dependencies=[Depends(require_roles(*_WAREHOUSE_OPS_ROLES))],
)
async def stock_out(
    batch_id: UUID,
    body: StockOutRequest,
    current_user: CurrentUser,
    svc: InventoryBatchService = Depends(_svc),
) -> dict[str, object]:
    try:
        batch = await svc.stock_out(batch_id, body, created_by=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return success_envelope(BatchRead.model_validate(batch).model_dump())


# ── transaction audit log ─────────────────────────────────────────────────────


@router.get(
    "/batches/{batch_id}/transactions",
    response_model=None,
    dependencies=[Depends(require_roles(*_READ_ROLES))],
)
async def get_batch_transactions(
    batch_id: UUID,
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    svc: InventoryBatchService = Depends(_svc),
) -> dict[str, object]:
    try:
        txns = await svc.get_transactions(batch_id, limit=limit, offset=offset)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return success_envelope([TransactionRead.model_validate(t).model_dump() for t in txns])


@router.get(
    "/transactions",
    response_model=None,
    dependencies=[Depends(require_roles(UserRole.ADMIN, UserRole.INVENTORY_MANAGER))],
)
async def list_all_transactions(
    limit: int = Query(default=200, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    svc: InventoryBatchService = Depends(_svc),
) -> dict[str, object]:
    txns = await svc.list_all_transactions(limit=limit, offset=offset)
    return success_envelope([TransactionRead.model_validate(t).model_dump() for t in txns])


# ── FEFO endpoints ────────────────────────────────────────────────────────────


@router.post(
    "/fefo/allocate",
    response_model=None,
    dependencies=[Depends(require_roles(*_WRITE_ROLES))],
)
async def fefo_allocate(
    body: FEFOAllocationRequest,
    current_user: CurrentUser,
    svc: FEFOService = Depends(_fefo_svc),
) -> dict[str, object]:
    try:
        result = await svc.allocate(body, created_by=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return success_envelope(result.model_dump())


@router.post(
    "/fefo/release",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_roles(*_WRITE_ROLES))],
)
async def fefo_release(
    body: FEFOReleaseRequest,
    current_user: CurrentUser,
    svc: FEFOService = Depends(_fefo_svc),
) -> None:
    try:
        await svc.release_allocation(body, created_by=current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
