"""Report service — thin orchestration layer between API and ReportsRepository.

Converts raw DB rows / ORM objects into typed report schemas.
No business rules live here; all SQL lives in ReportsRepository.
"""

from __future__ import annotations

import datetime as dt
from decimal import Decimal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory_batch import BatchStatus
from app.models.inventory_transaction import TransactionType
from app.repositories.reports import ReportsRepository
from app.schemas.expiry_alert import BatchExpiryInfo
from app.schemas.reports import (
    BatchInventoryRow,
    CustomerSummaryRow,
    FulfillmentByStatus,
    MedicineInventorySummary,
    OrderFulfillmentReport,
    PurchaseSummaryRow,
    SalesSummaryRow,
    StockMovementRow,
)
from app.services.expiry_alert import ExpiryAlertService


class ReportsService:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = ReportsRepository(session)
        self._expiry_svc = ExpiryAlertService(session)

    # ── 1. Current inventory ───────────────────────────────────────────────────

    async def current_inventory(
        self,
        *,
        warehouse_id: UUID | None = None,
        medicine_id: UUID | None = None,
    ) -> list[MedicineInventorySummary]:
        rows = await self._repo.current_inventory(
            warehouse_id=warehouse_id, medicine_id=medicine_id
        )
        return [
            MedicineInventorySummary(
                medicine_id=r["medicine_id"],
                medicine_code=r["medicine_code"],
                medicine_name=r["medicine_name"],
                total_available=int(r["total_available"]),
                total_reserved=int(r["total_reserved"]),
                total_on_hand=int(r["total_available"]) + int(r["total_reserved"]),
                active_batch_count=int(r["active_batch_count"]),
                warehouse_count=int(r["warehouse_count"]),
            )
            for r in rows
        ]

    # ── 2. Batch inventory ─────────────────────────────────────────────────────

    async def batch_inventory(
        self,
        *,
        warehouse_id: UUID | None = None,
        medicine_id: UUID | None = None,
        status: BatchStatus | None = None,
        expiry_before: dt.date | None = None,
        expiry_after: dt.date | None = None,
        limit: int = 500,
        offset: int = 0,
    ) -> list[BatchInventoryRow]:
        today = dt.date.today()
        batches = await self._repo.batch_inventory(
            warehouse_id=warehouse_id,
            medicine_id=medicine_id,
            status=status,
            expiry_before=expiry_before,
            expiry_after=expiry_after,
            limit=limit,
            offset=offset,
        )
        return [
            BatchInventoryRow(
                batch_id=b.id,
                batch_number=b.batch_number,
                medicine_id=b.medicine_id,
                medicine_code=b.medicine.code,
                medicine_name=b.medicine.name,
                warehouse_id=b.warehouse_id,
                warehouse_name=b.warehouse.warehouse_name,
                expiry_date=b.expiry_date,
                days_to_expiry=(b.expiry_date - today).days,
                status=b.status,
                quantity_available=b.quantity_available,
                quantity_reserved=b.quantity_reserved,
                quantity_damaged=b.quantity_damaged,
            )
            for b in batches
        ]

    # ── 3. Expiry report ───────────────────────────────────────────────────────

    async def expiry_report(self) -> list[BatchExpiryInfo]:
        """All expired batches followed by all batches expiring within 90 days."""
        expired = await self._expiry_svc.get_expired_batches()
        near = await self._expiry_svc.get_near_expiry_batches(90)
        return expired + near

    # ── 4. Stock movements ─────────────────────────────────────────────────────

    async def stock_movements(
        self,
        *,
        date_from: dt.date | None = None,
        date_to: dt.date | None = None,
        transaction_type: TransactionType | None = None,
        medicine_id: UUID | None = None,
        warehouse_id: UUID | None = None,
        limit: int = 500,
        offset: int = 0,
    ) -> list[StockMovementRow]:
        rows = await self._repo.stock_movements(
            date_from=date_from,
            date_to=date_to,
            transaction_type=transaction_type,
            medicine_id=medicine_id,
            warehouse_id=warehouse_id,
            limit=limit,
            offset=offset,
        )
        return [
            StockMovementRow(
                transaction_id=r["transaction_id"],
                created_at=r["created_at"],
                transaction_type=r["transaction_type"],
                quantity=r["quantity"],
                batch_id=r["batch_id"],
                batch_number=r["batch_number"],
                medicine_id=r["medicine_id"],
                medicine_code=r["medicine_code"],
                medicine_name=r["medicine_name"],
                warehouse_id=r["warehouse_id"],
                warehouse_name=r["warehouse_name"],
                reference_number=r.get("reference_number"),
                remarks=r.get("remarks"),
            )
            for r in rows
        ]

    # ── 5. Purchase summary ────────────────────────────────────────────────────

    async def purchase_summary(
        self,
        *,
        date_from: dt.date | None = None,
        date_to: dt.date | None = None,
        status: str | None = None,
        supplier_id: UUID | None = None,
        limit: int = 500,
        offset: int = 0,
    ) -> list[PurchaseSummaryRow]:
        orders = await self._repo.purchase_summary(
            date_from=date_from,
            date_to=date_to,
            status=status,
            supplier_id=supplier_id,
            limit=limit,
            offset=offset,
        )
        return [
            PurchaseSummaryRow(
                po_id=po.id,
                po_number=po.po_number,
                supplier_id=po.supplier_id,
                supplier_name=po.supplier.supplier_name,
                order_date=po.order_date,
                status=po.status,
                item_count=len(po.items),
                total_ordered_qty=sum(item.quantity_ordered for item in po.items),
                total_received_qty=sum(item.quantity_received for item in po.items),
                total_amount=po.total_amount,
            )
            for po in orders
        ]

    # ── 6. Sales summary ───────────────────────────────────────────────────────

    async def sales_summary(
        self,
        *,
        date_from: dt.date | None = None,
        date_to: dt.date | None = None,
        status: str | None = None,
        customer_id: UUID | None = None,
        limit: int = 500,
        offset: int = 0,
    ) -> list[SalesSummaryRow]:
        pairs = await self._repo.sales_summary(
            date_from=date_from,
            date_to=date_to,
            status=status,
            customer_id=customer_id,
            limit=limit,
            offset=offset,
        )
        return [
            SalesSummaryRow(
                order_id=order.id,
                order_number=order.order_number,
                customer_id=order.customer_id,
                customer_name=order.customer.business_name,
                order_date=order.order_date,
                status=order.status,
                item_count=len(order.items),
                total_amount=order.total_amount,
                invoice_number=inv.invoice_number if inv else None,
                invoice_status=inv.status if inv else None,
            )
            for order, inv in pairs
        ]

    # ── 7. Customer summary ────────────────────────────────────────────────────

    async def customer_summary(
        self,
        *,
        customer_id: UUID | None = None,
    ) -> list[CustomerSummaryRow]:
        rows = await self._repo.customer_summary(customer_id=customer_id)
        return [
            CustomerSummaryRow(
                customer_id=r["customer_id"],
                customer_code=r["customer_code"],
                business_name=r["business_name"],
                credit_limit=Decimal(str(r["credit_limit"])),
                total_orders=int(r["total_orders"]),
                total_order_value=Decimal(str(r["total_order_value"])),
                completed_orders=int(r["completed_orders"]),
            )
            for r in rows
        ]

    # ── 8. Order fulfillment ───────────────────────────────────────────────────

    async def order_fulfillment(
        self,
        *,
        date_from: dt.date | None = None,
        date_to: dt.date | None = None,
    ) -> OrderFulfillmentReport:
        rows = await self._repo.order_fulfillment(date_from=date_from, date_to=date_to)
        by_status = [
            FulfillmentByStatus(
                status=r["status"],
                order_count=int(r["order_count"]),
                total_value=Decimal(str(r["total_value"])),
            )
            for r in rows
        ]
        total_orders = sum(s.order_count for s in by_status)
        total_value = sum((s.total_value for s in by_status), Decimal("0"))
        return OrderFulfillmentReport(
            as_of=dt.date.today(),
            date_from=date_from,
            date_to=date_to,
            total_orders=total_orders,
            total_value=total_value,
            by_status=by_status,
        )
