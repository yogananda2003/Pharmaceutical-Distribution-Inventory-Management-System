"""Report response schemas for Stage 14.

Eight report types:
  1. current_inventory  — per-medicine aggregated stock across active batches
  2. batch_inventory    — per-batch detail with expiry info and optional filters
  3. expiry             — all expired + near-expiry batches (reuses BatchExpiryInfo)
  4. stock_movements    — inventory transaction ledger with date/type/medicine filters
  5. purchases          — purchase order summary with supplier and quantity totals
  6. sales              — customer order summary with linked invoice info
  7. customers          — customer account summary with order totals
  8. order_fulfillment  — order counts and values grouped by lifecycle status
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel

# ── 1. Current Inventory ───────────────────────────────────────────────────────


class MedicineInventorySummary(BaseModel):
    medicine_id: UUID
    medicine_code: str
    medicine_name: str
    total_available: int
    total_reserved: int
    total_on_hand: int
    active_batch_count: int
    warehouse_count: int


# ── 2. Batch Inventory ─────────────────────────────────────────────────────────


class BatchInventoryRow(BaseModel):
    batch_id: UUID
    batch_number: str
    medicine_id: UUID
    medicine_code: str
    medicine_name: str
    warehouse_id: UUID
    warehouse_name: str
    expiry_date: date
    days_to_expiry: int
    status: str
    quantity_available: int
    quantity_reserved: int
    quantity_damaged: int


# ── 4. Stock Movement ──────────────────────────────────────────────────────────


class StockMovementRow(BaseModel):
    transaction_id: UUID
    created_at: datetime
    transaction_type: str
    quantity: int
    batch_id: UUID
    batch_number: str
    medicine_id: UUID
    medicine_code: str
    medicine_name: str
    warehouse_id: UUID
    warehouse_name: str
    reference_number: str | None
    remarks: str | None


# ── 5. Purchase Report ─────────────────────────────────────────────────────────


class PurchaseSummaryRow(BaseModel):
    po_id: UUID
    po_number: str
    supplier_id: UUID
    supplier_name: str
    order_date: date
    status: str
    item_count: int
    total_ordered_qty: int
    total_received_qty: int
    total_amount: Decimal


# ── 6. Sales Report ────────────────────────────────────────────────────────────


class SalesSummaryRow(BaseModel):
    order_id: UUID
    order_number: str
    customer_id: UUID
    customer_name: str
    order_date: date
    status: str
    item_count: int
    total_amount: Decimal
    invoice_number: str | None
    invoice_status: str | None


# ── 7. Customer Report ─────────────────────────────────────────────────────────


class CustomerSummaryRow(BaseModel):
    customer_id: UUID
    customer_code: str
    business_name: str
    credit_limit: Decimal
    total_orders: int
    total_order_value: Decimal
    completed_orders: int


# ── 8. Order Fulfillment ───────────────────────────────────────────────────────


class FulfillmentByStatus(BaseModel):
    status: str
    order_count: int
    total_value: Decimal


class OrderFulfillmentReport(BaseModel):
    as_of: date
    date_from: date | None
    date_to: date | None
    total_orders: int
    total_value: Decimal
    by_status: list[FulfillmentByStatus]
