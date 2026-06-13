"""Read-only repository for reporting queries.

Keeps all aggregation SQL in one place.  No data is mutated here.
"""

from __future__ import annotations

import datetime as dt
from typing import Any
from uuid import UUID

from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer import Customer
from app.models.customer_order import CustomerOrder, OrderStatus
from app.models.inventory_batch import BatchStatus, InventoryBatch
from app.models.inventory_transaction import InventoryTransaction, TransactionType
from app.models.invoice import Invoice
from app.models.medicine import Medicine
from app.models.purchase_order import PurchaseOrder
from app.models.warehouse import Warehouse


class ReportsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ── 1. Current inventory (aggregate per medicine) ──────────────────────────

    async def current_inventory(
        self,
        *,
        warehouse_id: UUID | None = None,
        medicine_id: UUID | None = None,
    ) -> list[dict[str, Any]]:
        stmt = (
            select(
                Medicine.id.label("medicine_id"),
                Medicine.code.label("medicine_code"),
                Medicine.name.label("medicine_name"),
                func.coalesce(func.sum(InventoryBatch.quantity_available), 0).label(
                    "total_available"
                ),
                func.coalesce(func.sum(InventoryBatch.quantity_reserved), 0).label(
                    "total_reserved"
                ),
                func.count(InventoryBatch.id).label("active_batch_count"),
                func.count(distinct(InventoryBatch.warehouse_id)).label("warehouse_count"),
            )
            .join(InventoryBatch, InventoryBatch.medicine_id == Medicine.id)
            .where(
                InventoryBatch.deleted_at.is_(None),
                InventoryBatch.status.not_in([BatchStatus.EXHAUSTED]),
                Medicine.deleted_at.is_(None),
            )
            .group_by(Medicine.id, Medicine.code, Medicine.name)
            .order_by(Medicine.name)
        )
        if warehouse_id is not None:
            stmt = stmt.where(InventoryBatch.warehouse_id == warehouse_id)
        if medicine_id is not None:
            stmt = stmt.where(Medicine.id == medicine_id)
        rows = (await self.session.execute(stmt)).mappings().all()
        return [dict(r) for r in rows]

    # ── 2. Batch inventory (filtered list) ────────────────────────────────────

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
    ) -> list[InventoryBatch]:
        stmt = (
            select(InventoryBatch)
            .where(InventoryBatch.deleted_at.is_(None))
            .order_by(InventoryBatch.expiry_date)
            .limit(limit)
            .offset(offset)
        )
        if warehouse_id is not None:
            stmt = stmt.where(InventoryBatch.warehouse_id == warehouse_id)
        if medicine_id is not None:
            stmt = stmt.where(InventoryBatch.medicine_id == medicine_id)
        if status is not None:
            stmt = stmt.where(InventoryBatch.status == status)
        if expiry_before is not None:
            stmt = stmt.where(InventoryBatch.expiry_date < expiry_before)
        if expiry_after is not None:
            stmt = stmt.where(InventoryBatch.expiry_date >= expiry_after)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # ── 4. Stock movements (flat JOIN, most-recent-first) ──────────────────────

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
    ) -> list[dict[str, Any]]:
        stmt = (
            select(
                InventoryTransaction.id.label("transaction_id"),
                InventoryTransaction.created_at,
                InventoryTransaction.transaction_type,
                InventoryTransaction.quantity,
                InventoryTransaction.reference_number,
                InventoryTransaction.remarks,
                InventoryBatch.id.label("batch_id"),
                InventoryBatch.batch_number,
                Medicine.id.label("medicine_id"),
                Medicine.code.label("medicine_code"),
                Medicine.name.label("medicine_name"),
                Warehouse.id.label("warehouse_id"),
                Warehouse.warehouse_name,
            )
            .join(InventoryBatch, InventoryBatch.id == InventoryTransaction.batch_id)
            .join(Medicine, Medicine.id == InventoryBatch.medicine_id)
            .join(Warehouse, Warehouse.id == InventoryBatch.warehouse_id)
            .order_by(InventoryTransaction.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if date_from is not None:
            start = dt.datetime.combine(date_from, dt.time.min).replace(tzinfo=dt.UTC)
            stmt = stmt.where(InventoryTransaction.created_at >= start)
        if date_to is not None:
            end = dt.datetime.combine(date_to, dt.time.max).replace(tzinfo=dt.UTC)
            stmt = stmt.where(InventoryTransaction.created_at <= end)
        if transaction_type is not None:
            stmt = stmt.where(InventoryTransaction.transaction_type == transaction_type)
        if medicine_id is not None:
            stmt = stmt.where(InventoryBatch.medicine_id == medicine_id)
        if warehouse_id is not None:
            stmt = stmt.where(InventoryBatch.warehouse_id == warehouse_id)
        rows = (await self.session.execute(stmt)).mappings().all()
        return [dict(r) for r in rows]

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
    ) -> list[PurchaseOrder]:
        stmt = (
            select(PurchaseOrder)
            .where(PurchaseOrder.deleted_at.is_(None))
            .order_by(PurchaseOrder.order_date.desc())
            .limit(limit)
            .offset(offset)
        )
        if date_from is not None:
            stmt = stmt.where(PurchaseOrder.order_date >= date_from)
        if date_to is not None:
            stmt = stmt.where(PurchaseOrder.order_date <= date_to)
        if status is not None:
            stmt = stmt.where(PurchaseOrder.status == status)
        if supplier_id is not None:
            stmt = stmt.where(PurchaseOrder.supplier_id == supplier_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

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
    ) -> list[tuple[CustomerOrder, Invoice | None]]:
        stmt = (
            select(CustomerOrder, Invoice)
            .outerjoin(
                Invoice,
                (Invoice.order_id == CustomerOrder.id) & (Invoice.deleted_at.is_(None)),
            )
            .where(CustomerOrder.deleted_at.is_(None))
            .order_by(CustomerOrder.order_date.desc())
            .limit(limit)
            .offset(offset)
        )
        if date_from is not None:
            stmt = stmt.where(CustomerOrder.order_date >= date_from)
        if date_to is not None:
            stmt = stmt.where(CustomerOrder.order_date <= date_to)
        if status is not None:
            stmt = stmt.where(CustomerOrder.status == status)
        if customer_id is not None:
            stmt = stmt.where(CustomerOrder.customer_id == customer_id)
        result = await self.session.execute(stmt)
        return [(row.CustomerOrder, row.Invoice) for row in result]

    # ── 7. Customer summary (aggregate per customer) ───────────────────────────

    async def customer_summary(
        self,
        *,
        customer_id: UUID | None = None,
    ) -> list[dict[str, Any]]:
        stmt = (
            select(
                Customer.id.label("customer_id"),
                Customer.customer_code,
                Customer.business_name,
                Customer.credit_limit,
                func.count(CustomerOrder.id).label("total_orders"),
                func.coalesce(func.sum(CustomerOrder.total_amount), 0).label("total_order_value"),
                func.count(CustomerOrder.id)
                .filter(CustomerOrder.status == OrderStatus.COMPLETED)
                .label("completed_orders"),
            )
            .outerjoin(
                CustomerOrder,
                (CustomerOrder.customer_id == Customer.id) & (CustomerOrder.deleted_at.is_(None)),
            )
            .where(Customer.deleted_at.is_(None))
            .group_by(
                Customer.id,
                Customer.customer_code,
                Customer.business_name,
                Customer.credit_limit,
            )
            .order_by(Customer.business_name)
        )
        if customer_id is not None:
            stmt = stmt.where(Customer.id == customer_id)
        rows = (await self.session.execute(stmt)).mappings().all()
        return [dict(r) for r in rows]

    # ── 8. Order fulfillment (aggregate by status) ─────────────────────────────

    async def order_fulfillment(
        self,
        *,
        date_from: dt.date | None = None,
        date_to: dt.date | None = None,
    ) -> list[dict[str, Any]]:
        stmt = (
            select(
                CustomerOrder.status,
                func.count(CustomerOrder.id).label("order_count"),
                func.coalesce(func.sum(CustomerOrder.total_amount), 0).label("total_value"),
            )
            .where(CustomerOrder.deleted_at.is_(None))
            .group_by(CustomerOrder.status)
            .order_by(CustomerOrder.status)
        )
        if date_from is not None:
            stmt = stmt.where(CustomerOrder.order_date >= date_from)
        if date_to is not None:
            stmt = stmt.where(CustomerOrder.order_date <= date_to)
        rows = (await self.session.execute(stmt)).mappings().all()
        return [dict(r) for r in rows]
