from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.db import AsyncSession, get_db
from app.core.deps import CurrentUser, require_roles
from app.core.responses import success_envelope
from app.models.user import UserRole
from app.schemas.medicine import MedicineCreate, MedicineRead, MedicineUpdate
from app.services.medicine import MedicineService

router = APIRouter(prefix="/medicines", tags=["medicines"])

_WRITE_ROLES = (UserRole.ADMIN, UserRole.INVENTORY_MANAGER)
_READ_ROLES = (
    UserRole.ADMIN,
    UserRole.INVENTORY_MANAGER,
    UserRole.SALES_REPRESENTATIVE,
    UserRole.CUSTOMER,
    UserRole.WAREHOUSE_STAFF,
)


def _svc(session: AsyncSession = Depends(get_db)) -> MedicineService:
    return MedicineService(session)


@router.post(
    "",
    response_model=None,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(*_WRITE_ROLES))],
)
async def create_medicine(
    body: MedicineCreate,
    current_user: CurrentUser,
    svc: MedicineService = Depends(_svc),
) -> dict[str, object]:
    try:
        medicine = await svc.create(body, tenant_id=current_user.tenant_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return success_envelope(MedicineRead.model_validate(medicine).model_dump())


@router.get(
    "",
    response_model=None,
    dependencies=[Depends(require_roles(*_READ_ROLES))],
)
async def list_medicines(
    active_only: bool = Query(default=False),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    svc: MedicineService = Depends(_svc),
) -> dict[str, object]:
    if active_only:
        medicines = await svc.list_active(limit=limit, offset=offset)
    else:
        medicines = await svc.list_medicines(limit=limit, offset=offset)
    return success_envelope([MedicineRead.model_validate(m).model_dump() for m in medicines])


@router.get(
    "/search",
    response_model=None,
    dependencies=[Depends(require_roles(*_READ_ROLES))],
)
async def search_medicines(
    q: str = Query(min_length=2),
    svc: MedicineService = Depends(_svc),
) -> dict[str, object]:
    medicines = await svc.search(q)
    return success_envelope([MedicineRead.model_validate(m).model_dump() for m in medicines])


@router.get(
    "/{medicine_id}",
    response_model=None,
    dependencies=[Depends(require_roles(*_READ_ROLES))],
)
async def get_medicine(
    medicine_id: UUID,
    svc: MedicineService = Depends(_svc),
) -> dict[str, object]:
    try:
        medicine = await svc.get(medicine_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return success_envelope(MedicineRead.model_validate(medicine).model_dump())


@router.put(
    "/{medicine_id}",
    response_model=None,
    dependencies=[Depends(require_roles(*_WRITE_ROLES))],
)
async def update_medicine(
    medicine_id: UUID,
    body: MedicineUpdate,
    svc: MedicineService = Depends(_svc),
) -> dict[str, object]:
    try:
        medicine = await svc.update(medicine_id, body)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return success_envelope(MedicineRead.model_validate(medicine).model_dump())


@router.delete(
    "/{medicine_id}",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_roles(*_WRITE_ROLES))],
)
async def delete_medicine(
    medicine_id: UUID,
    svc: MedicineService = Depends(_svc),
) -> None:
    try:
        await svc.delete(medicine_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
