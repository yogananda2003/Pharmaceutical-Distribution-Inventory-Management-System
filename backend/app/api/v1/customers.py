from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.db import AsyncSession, get_db
from app.core.deps import CurrentUser, require_roles
from app.core.responses import success_envelope
from app.models.user import UserRole
from app.schemas.customer import CustomerCreate, CustomerRead, CustomerUpdate
from app.services.customer import CustomerService

router = APIRouter(prefix="/customers", tags=["customers"])

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


def _svc(session: AsyncSession = Depends(get_db)) -> CustomerService:
    return CustomerService(session)


@router.post(
    "",
    response_model=None,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(*_WRITE_ROLES))],
)
async def create_customer(
    body: CustomerCreate,
    current_user: CurrentUser,
    svc: CustomerService = Depends(_svc),
) -> dict[str, object]:
    try:
        customer = await svc.create(body, tenant_id=current_user.tenant_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return success_envelope(CustomerRead.model_validate(customer).model_dump(mode="json"))


@router.get(
    "",
    response_model=None,
    dependencies=[Depends(require_roles(*_READ_ROLES))],
)
async def list_customers(
    active_only: bool = Query(False),
    svc: CustomerService = Depends(_svc),
) -> dict[str, object]:
    customers = await svc.list_customers(active_only=active_only)
    return success_envelope(
        [CustomerRead.model_validate(c).model_dump(mode="json") for c in customers]
    )


@router.get(
    "/{customer_id}",
    response_model=None,
    dependencies=[Depends(require_roles(*_READ_ROLES))],
)
async def get_customer(
    customer_id: UUID,
    svc: CustomerService = Depends(_svc),
) -> dict[str, object]:
    try:
        customer = await svc.get(customer_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return success_envelope(CustomerRead.model_validate(customer).model_dump(mode="json"))


@router.put(
    "/{customer_id}",
    response_model=None,
    dependencies=[Depends(require_roles(*_WRITE_ROLES))],
)
async def update_customer(
    customer_id: UUID,
    body: CustomerUpdate,
    svc: CustomerService = Depends(_svc),
) -> dict[str, object]:
    try:
        customer = await svc.update(customer_id, body)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return success_envelope(CustomerRead.model_validate(customer).model_dump(mode="json"))


@router.delete(
    "/{customer_id}",
    response_model=None,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_roles(*_WRITE_ROLES))],
)
async def delete_customer(
    customer_id: UUID,
    svc: CustomerService = Depends(_svc),
) -> dict[str, object]:
    try:
        await svc.delete(customer_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return success_envelope({"deleted": True})
