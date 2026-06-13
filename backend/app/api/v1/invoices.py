from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.db import AsyncSession, get_db
from app.core.deps import require_roles
from app.core.responses import success_envelope
from app.models.invoice import Invoice
from app.models.user import UserRole
from app.schemas.invoice import (
    GenerateInvoiceRequest,
    InvoiceRead,
    UpdateInvoiceStatusRequest,
)
from app.services.invoice import InvoiceService

router = APIRouter(prefix="/invoices", tags=["invoices"])

_VIEW_ROLES = (
    UserRole.ADMIN,
    UserRole.INVENTORY_MANAGER,
    UserRole.SALES_REPRESENTATIVE,
    UserRole.WAREHOUSE_STAFF,
)
_MANAGE_ROLES = (UserRole.ADMIN, UserRole.INVENTORY_MANAGER, UserRole.SALES_REPRESENTATIVE)
_ADMIN_ROLES = (UserRole.ADMIN, UserRole.INVENTORY_MANAGER)


def _to_dict(invoice: Invoice) -> dict[str, object]:
    data = InvoiceRead.model_validate(invoice).model_dump(mode="json")
    data["order_number"] = invoice.order.order_number
    data["customer_name"] = invoice.customer.business_name
    return data


def _svc(session: AsyncSession = Depends(get_db)) -> InvoiceService:
    return InvoiceService(session)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_roles(*_MANAGE_ROLES))],
)
async def generate_invoice(
    body: GenerateInvoiceRequest,
    svc: InvoiceService = Depends(_svc),
) -> dict[str, object]:
    try:
        invoice = await svc.generate_invoice(
            body.order_id,
            invoice_date=body.invoice_date,
            due_date=body.due_date,
            notes=body.notes,
        )
    except ValueError as exc:
        msg = str(exc)
        if "not found" in msg:
            code = status.HTTP_404_NOT_FOUND
        elif "already exists" in msg:
            code = status.HTTP_409_CONFLICT
        else:
            code = status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=code, detail=msg) from None
    return success_envelope(_to_dict(invoice))


@router.get("", dependencies=[Depends(require_roles(*_VIEW_ROLES))])
async def list_invoices(
    customer_id: UUID | None = Query(None),
    invoice_status: str | None = Query(None, alias="status"),
    svc: InvoiceService = Depends(_svc),
) -> dict[str, object]:
    try:
        invoices = await svc.list_invoices(customer_id=customer_id, status=invoice_status)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from None
    return success_envelope([_to_dict(inv) for inv in invoices])


@router.get("/order/{order_id}", dependencies=[Depends(require_roles(*_VIEW_ROLES))])
async def get_invoice_by_order(
    order_id: UUID,
    svc: InvoiceService = Depends(_svc),
) -> dict[str, object]:
    invoice = await svc.get_by_order(order_id)
    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invoice not found for this order",
        )
    return success_envelope(_to_dict(invoice))


@router.get("/{invoice_id}", dependencies=[Depends(require_roles(*_VIEW_ROLES))])
async def get_invoice(
    invoice_id: UUID,
    svc: InvoiceService = Depends(_svc),
) -> dict[str, object]:
    invoice = await svc.get_invoice(invoice_id)
    if not invoice:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invoice not found")
    return success_envelope(_to_dict(invoice))


@router.patch("/{invoice_id}/status", dependencies=[Depends(require_roles(*_ADMIN_ROLES))])
async def update_invoice_status(
    invoice_id: UUID,
    body: UpdateInvoiceStatusRequest,
    svc: InvoiceService = Depends(_svc),
) -> dict[str, object]:
    try:
        invoice = await svc.update_status(invoice_id, body.status)
    except ValueError as exc:
        msg = str(exc)
        code = status.HTTP_404_NOT_FOUND if "not found" in msg else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=code, detail=msg) from None
    return success_envelope(_to_dict(invoice))


@router.delete(
    "/{invoice_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_roles(*_ADMIN_ROLES))],
)
async def delete_invoice(
    invoice_id: UUID,
    svc: InvoiceService = Depends(_svc),
) -> None:
    try:
        await svc.delete_invoice(invoice_id)
    except ValueError as exc:
        msg = str(exc)
        code = status.HTTP_404_NOT_FOUND if "not found" in msg else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=code, detail=msg) from None
