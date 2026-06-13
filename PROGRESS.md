# Build Progress

## Stage 1 — Database foundations & base model
- Date: 2026-06-09
- Built: `app/models/base.py` — `UUIDPrimaryKeyMixin` (Python-side `uuid.uuid4()` default, wrapped
  for SQLAlchemy's context-sensitive callable protocol), `TimestampMixin` (created_at/updated_at
  with server_default+onupdate), `SoftDeleteMixin` (deleted_at nullable), `TenantMixin`
  (tenant_id nullable+indexed, unenforced), `BaseEntity` (abstract, combines all), `TenantedEntity`
  (abstract, adds TenantMixin). `app/repositories/base.py` — generic `BaseRepository[ModelT]`
  with `get_by_id`, `list` (excludes soft-deleted, ordered by created_at), `add`, `delete`,
  `soft_delete`. `alembic/versions/0001_base_foundation.py` — empty migration (no domain tables
  yet; abstract mixins produce no tables).
- Test gate:
  - Lint/format/type: `ruff check`, `ruff format --check`, `mypy app` — all green.
  - Unit tests (no DB): 7/7 passing — UUID PK config, unique ID generation (each call returns
    different UUID via Python-side default), audit timestamp column config, soft-delete column,
    TenantMixin inheritance chain, tenant_id column presence/nullability verified via mapper
    inspection.
  - Integration tests: 7/7 passing — add, get_by_id hit/miss, list excludes soft-deleted,
    soft_delete sets deleted_at, timestamps set on insert, UUID uniqueness across 10 entities.
  - Migration: `alembic upgrade head` ✅ · downgrade -1 → upgrade head round-trip ✅



Source of truth for which stage is complete. Append an entry only after that stage's full test gate is green.

## Stage 12 — Invoice Generation
- Date: 2026-06-11
- Built:
  - `app/models/invoice.py` — Invoice (TenantedEntity), InvoiceLine (UUIDPrimaryKeyMixin+TimestampMixin+Base, no soft delete), InvoiceStatus StrEnum (draft/issued/paid/cancelled/void), INVOICE_STATUS_TRANSITIONS dict
  - `app/schemas/invoice.py` — GenerateInvoiceRequest, UpdateInvoiceStatusRequest, InvoiceLineRead, InvoiceRead (from_attributes)
  - `app/repositories/invoice.py` — InvoiceRepository: get_by_id_not_deleted, get_by_order_id, list_all_not_deleted, list_by_customer, list_by_status
  - `app/services/invoice.py` — InvoiceService: generate_invoice (sequential INV-YYYY-NNNN number via PostgreSQL sequence, computes subtotal/tax/discount/total from order items, creates InvoiceLine per OrderItem), get_invoice, get_by_order, list_invoices, update_status (validates INVOICE_STATUS_TRANSITIONS), delete_invoice (DRAFT only)
  - `app/api/v1/invoices.py` — POST /invoices (201, MANAGE roles), GET /invoices (VIEW roles, customer_id/status filter), GET /invoices/order/{id}, GET /invoices/{id}, PATCH /invoices/{id}/status (ADMIN roles), DELETE /invoices/{id} 204 (ADMIN roles)
  - `app/api/v1/router.py` — registered invoices router
  - `app/models/__init__.py` — added Invoice, InvoiceLine exports
  - `alembic/versions/d4e5f6a1b2c3_invoice_tables.py` — creates invoices table, invoice_lines table, invoice_number_seq PostgreSQL sequence
  - `conftest.py` — creates/drops invoice_number_seq around test session (Base.metadata.create_all doesn't create sequences)
- Test gate:
  - Lint/format/type: ruff clean, mypy 0 errors in 80 source files
  - Invoice tests: 27/27 — generate from DISPATCHED/DELIVERED/COMPLETED, number format INV-YYYY-NNNN, sequential numbers (N+1), amounts reconcile (subtotal/tax/discount/total), line items match order items, cannot generate for DRAFT/PLACED/APPROVED (400), duplicate → 409, order not found → 404, GET by id, GET by order, list, list by customer filter, draft→issued, issued→paid, invalid transition (400), status not found (404), delete DRAFT (204), cannot delete ISSUED (400), sales_rep can generate, warehouse_staff view-only, warehouse_staff cannot generate (403), unauthenticated (401)
  - Full suite: 293/293 passing
- Notes:
  - Invoice number uses `SELECT nextval('invoice_number_seq')` — non-transactional PostgreSQL sequence, concurrent-safe, sequence advances even on rollback
  - Eligible statuses for invoice generation: DISPATCHED, DELIVERED, COMPLETED
  - Invoice status transitions: draft→issued/cancelled, issued→paid/void; paid/cancelled/void are terminal
  - Line items copied from OrderItem (unit_price, quantity, discount, tax_amount, line_total) + medicine description
  - `_to_dict` in API layer adds `order_number` and `customer_name` from selectin-loaded relationships
  - Re-queries invoice after commit (instead of session.refresh) to ensure all selectin relationships (order, customer, lines) are loaded fresh

## Stage 15 — Frontend Portals
- Date: 2026-06-12
- Built:
  - `frontend/src/lib/auth.ts` — localStorage helpers: getToken/getRole/getUserId/getRefreshToken, setAuth, clearAuth; keys prefixed `pharma_`
  - `frontend/src/api/client.ts` — Axios instance with Bearer token request interceptor
  - `frontend/src/api/auth.ts` — loginApi (POST /auth/login), logoutApi (POST /auth/logout)
  - `frontend/src/api/medicines.ts` — searchMedicines (GET /medicines?q=), listMedicines
  - `frontend/src/api/orders.ts` — createOrder, listOrders (status/customer_id filter), getOrder, updateOrderStatus, approveOrder, dispatchOrder, cancelOrder; OrderItemRead includes optional medicine_name
  - `frontend/src/api/customers.ts` — listCustomers
  - `frontend/src/api/invoices.ts` — listInvoices, getInvoiceByOrder, generateInvoice
  - `frontend/src/contexts/AuthContext.tsx` — AuthProvider + useAuth hook; AuthContext exported for test injection; login/logout with localStorage sync
  - `frontend/src/components/AuthGuard.tsx` — redirects unauthenticated to /login; role mismatch redirects to correct portal
  - `frontend/src/components/OrderStatusBadge.tsx` — Tailwind status-to-colour mapping for all 10 order statuses
  - `frontend/src/pages/LoginPage.tsx` — React Hook Form + Zod; role-based redirect after login
  - `frontend/src/pages/customer/ProductSearch.tsx` — medicine search with debounce, cart management (add/qty/price/remove)
  - `frontend/src/pages/customer/PlaceOrder.tsx` — checkout form: cart summary, customer dropdown, order date, submits createOrder, navigates to order detail
  - `frontend/src/pages/customer/OrderHistory.tsx` — paginated order list with status badges
  - `frontend/src/pages/customer/OrderDetail.tsx` — order items table, 8-step progress timeline, invoice section (getInvoiceByOrder)
  - `frontend/src/pages/sales/SalesDashboard.tsx` — summary cards (total customers, pending orders, dispatched), recent orders table
  - `frontend/src/pages/sales/CustomerList.tsx` — customer table with credit limit and status badge
  - `frontend/src/pages/sales/OrderManagement.tsx` — filterable order list with inline Approve/Dispatch/Cancel actions
  - `frontend/src/App.tsx` — BrowserRouter + AuthProvider + all routes; PortalLayout wrapper; customer portal at /customer/*, sales portal at /sales/* (role-guarded)
- Test gate:
  - TypeScript: `tsc --noEmit` 0 errors
  - Frontend tests: 26/26 — LoginPage (renders fields, email validation, password validation, login called with correct args, API error shown), PlaceOrder (cart items shown, empty cart message, customer validation, successful submit+navigate), OrderHistory (heading, order rows, status badges, new order link, empty state), OrderDetail (order number, status badge, items, invoice number, no-invoice fallback), SalesDashboard (heading, customer count, pending orders, recent orders, nav links)
  - ESLint: 0 errors, 0 warnings
- Notes:
  - `&` in project path breaks `.cmd` shims on Windows — tsc/vitest invoked via `node .\node_modules\<pkg>\bin\...` to bypass the broken batch file
  - AuthContext exported (not just AuthProvider+useAuth) to allow direct Provider injection in tests; eslint-disable comments added for react-refresh rule on non-component exports
  - TanStack Query v5 passes `(variables, context)` to mutationFn — test assertions use `toHaveBeenCalledTimes(1)` rather than `toHaveBeenCalledWith` to avoid TanStack internals
  - Customer portal (/customer/*) accessible to any authenticated user; sales portal (/sales/*) requires role=sales_representative

## Stage 14 — Reporting Module
- Date: 2026-06-12
- Built:
  - `app/schemas/reports.py` — 8 report schemas: MedicineInventorySummary, BatchInventoryRow, StockMovementRow, PurchaseSummaryRow, SalesSummaryRow, CustomerSummaryRow, FulfillmentByStatus, OrderFulfillmentReport; expiry report reuses BatchExpiryInfo from Stage 13
  - `app/repositories/reports.py` — ReportsRepository with 8 read-only query methods: current_inventory (GROUP BY medicine, SUM quantities), batch_inventory (filtered list), stock_movements (flat JOIN: transaction+batch+medicine+warehouse), purchase_summary (PurchaseOrder ORM with selectin), sales_summary (CustomerOrder OUTER JOIN Invoice), customer_summary (GROUP BY customer with FILTER aggregate for completed_orders), order_fulfillment (GROUP BY status); all use SQLAlchemy 2.0 async
  - `app/services/reports.py` — ReportsService: orchestrates repository + ORM→schema conversion; expiry_report delegates to ExpiryAlertService.get_expired_batches()+get_near_expiry_batches(90) and combines results
  - `app/api/v1/reports.py` — 8 GET endpoints at /reports prefix; inventory reports (current/batches/expiry/transactions) accessible to ADMIN, INVENTORY_MANAGER, WAREHOUSE_STAFF; business reports (purchases/sales/customers/orders/fulfillment) accessible to ADMIN, INVENTORY_MANAGER, SALES_REPRESENTATIVE
  - `app/api/v1/router.py` — registered reports router
- Test gate:
  - Lint/format/type: ruff clean, mypy 0 errors across all Stage 14 files
  - Report tests: 25/25 — current inventory (shows medicine, aggregates across warehouses, warehouse_id filter), batch inventory (medicine filter, expiry_before filter), expiry report (expired+near-expiry with alert_level), stock movements (medicine filter, type filter), purchase report (shows PO with totals, date filter in/out), sales report (dispatched order, invoice shown when generated, customer filter), customer report (all customers, order totals, customer_id filter), order fulfillment (structure/as_of, dispatched order counted, future date range returns 0), role checks (inventory manager all 8 OK, warehouse staff 4 inventory OK/4 business 403, sales rep 4 business OK/4 inventory 403, unauth 401)
  - Full suite: 340/340 passing
- Notes:
  - No new models or migration needed — Stage 14 is purely read-only (SELECT only)
  - current_inventory uses `func.coalesce(func.sum(...), 0)` + `func.count(distinct(...))` for robust aggregation even when filtered by warehouse_id
  - stock_movements uses a flat JOIN query (not ORM selectin) to get medicine+warehouse names from a single SQL statement — more efficient for the tabular report use case
  - customer_summary uses `func.count(id).filter(status == COMPLETED)` — PostgreSQL FILTER clause, cleaner than CASE WHEN
  - sales_summary outerjoin: `(Invoice.order_id == CustomerOrder.id) & (Invoice.deleted_at.is_(None))` in join condition keeps soft-deleted invoices out without excluding the parent order
  - `dict[str, Any]` used for aggregation row dicts (mixed types); `list[ORM_model]` used for filtered list queries (selectin relationships already loaded)

## Stage 13 — Expiry Management & Alerts
- Date: 2026-06-12
- Built:
  - `app/repositories/inventory_batch.py` — added `list_near_expiry(today, cutoff)`: ACTIVE batches where today <= expiry_date <= cutoff; complements existing `list_expiring_before(cutoff)` (expiry_date < cutoff, non-EXHAUSTED)
  - `app/schemas/expiry_alert.py` — BatchExpiryInfo (batch_id, batch_number, medicine/warehouse ids+names, expiry_date, days_to_expiry, quantity_available/reserved, alert_level), ExpiryDashboard (as_of, expired_count, expiring_within_30d/60d/90d)
  - `app/services/expiry_alert.py` — ExpiryAlertService: get_expiry_dashboard (two queries: expired + near-90d; counts 30d/60d/90d windows in Python), get_expired_batches, get_near_expiry_batches(threshold_days in 30|60|90); alert levels: expired(<0d), critical(0-30d), warning(31-60d), caution(61-90d)
  - `app/workers/__init__.py` — empty package marker
  - `app/workers/celery_app.py` — Celery app ("pharma_workers") with Redis broker/backend, includes expiry_alerts task module
  - `app/workers/expiry_alerts.py` — `scan_expiry_alerts` Celery task (name="expiry_alerts.scan"): uses asyncio.run() to call ExpiryAlertService.get_expiry_dashboard() from a sync Celery task context
  - `app/api/v1/expiry_alerts.py` — GET /expiry/dashboard, GET /expiry/expired, GET /expiry/near-expiry?days=30|60|90; VIEW roles: ADMIN, INVENTORY_MANAGER, WAREHOUSE_STAFF
  - `app/api/v1/router.py` — registered expiry_alerts router
- Test gate:
  - Lint/format/type: ruff clean, mypy 0 errors in all Stage 13 files
  - Expiry alert tests: 22/22 — expired batch in list, future batch excluded, today-expiring in near-expiry critical (not expired), 30d boundary inclusive, 31d excluded from 30d window, 60d includes 45d batch (not in 30d), 90d includes 75d batch, EXHAUSTED excluded from near-expiry, expired excluded from near-expiry, alert levels (critical/warning/caution), negative days_to_expiry on expired batches, dashboard counts (>=), dashboard 90d>=60d>=30d, invalid days 400 (45 and 7), WAREHOUSE_STAFF view access, SALES_REP denied 403, unauthenticated 401, Celery task registered
  - Full suite: 315/315 passing
- Notes:
  - Alert level boundary: expiry_date < today → "expired"; expiry_date >= today → near-expiry (critical if 0-30d). A batch expiring exactly today has days_to_expiry=0 → alert_level="critical".
  - list_expiring_before excludes EXHAUSTED batches (non-ACTIVE still tracked but ignored); list_near_expiry uses ACTIVE status filter
  - Celery task imports asyncio.run to bridge sync Celery worker context with async SQLAlchemy code; safe for single-use per task invocation
  - Test for Celery registration must import app.workers.expiry_alerts explicitly (Celery include= only activates when worker process starts)

## Stage 11 — Warehouse Operations
- Date: 2026-06-11
- Built:
  - `app/schemas/warehouse_ops.py` — StockTransferRequest/Response, BatchPickInfo, PickListItemInfo, PickListResponse, PendingOrderSummary
  - `app/repositories/customer_order.py` — added `list_by_statuses(statuses: list[OrderStatus])` to CustomerOrderRepository
  - `app/services/warehouse_ops.py` — WarehouseOpsService: transfer_stock (SELECT FOR UPDATE both batches in deterministic order, 2 TRANSFER txns, single commit), get_pending_orders (APPROVED/ALLOCATED/PICKED/PACKED), get_pick_list (assembles pick list from OrderItemAllocations with batch+warehouse details)
  - `app/api/v1/warehouse_ops.py` — POST /warehouse/transfer, GET /warehouse/pending, GET /warehouse/orders/{id}/pick-list (ADMIN/INVENTORY_MANAGER/WAREHOUSE_STAFF)
  - `app/api/v1/router.py` — registered warehouse_ops router
- Test gate:
  - Lint/format/type: all green (75 source files checked by mypy, ruff clean)
  - Warehouse ops tests: 24/24 — transfer (reduces source, adds to dest, creates 2 TRANSFER txns, cross-warehouse, same-batch 400, insufficient 400, zero qty 422, source not found 404, dest not found 404, exhausts source, revives exhausted dest, warehouse_staff allowed, sales_rep 403, unauth 401), pending orders (includes APPROVED, excludes DRAFT/PLACED, warehouse_staff 200, sales_rep 403, unauth 401), pick list (approved order with batch+warehouse info, multi-batch FEFO split, draft 400, not found 404, warehouse_staff 200, unauth 401)
  - Full suite: 266/266 passing
- Notes:
  - `TRANSFER` transaction type (defined in Stage 6) is now exercised: one txn on the source batch (transfer out) and one on the destination batch (transfer in), both with the same reference_number
  - Deadlock prevention: both batches locked in `sorted([src_id, dst_id], key=str)` order — always acquires the lexicographically smaller UUID first
  - EXHAUSTED destination batch is revived to ACTIVE when stock is transferred in; ACTIVE source batch becomes EXHAUSTED when all available stock is transferred out (only if reserved=0)
  - Pick list assembled from `OrderItemAllocation.batch` (selectin) + `InventoryBatch.warehouse` (selectin) — all loaded eagerly, no sync lazy access
  - No new migration: no new models or tables (uses existing inventory_transactions and customer_order tables)

## Stage 10 — Order Management & Lifecycle
- Date: 2026-06-11
- Built:
  - `app/models/customer_order.py` — CustomerOrder (TenantedEntity), OrderItem (UUIDPrimaryKeyMixin+TimestampMixin+Base, no soft delete), OrderItemAllocation (UUIDPrimaryKeyMixin+Base, no timestamps, hard-deleted), OrderStatus StrEnum (10 states), ORDER_STATUS_TRANSITIONS dict, CANCELLABLE_STATUSES set, RESERVED_STATUSES set
  - `app/schemas/customer_order.py` — OrderItemCreate (qty>0, price/discount/tax ≥0), OrderCreate (items non-empty), OrderRead/OrderItemRead (from_attributes), OrderStatusUpdate
  - `app/repositories/customer_order.py` — CustomerOrderRepository (BaseRepository), OrderItemRepository (standalone, list_by_order), OrderItemAllocationRepository (standalone, list_by_order, delete_by_order via subquery hard DELETE)
  - `app/services/customer_order.py` — create (total_amount computed from input items, refresh after commit), get/list_all (customer_id+status filters), transition_status (ORDER_STATUS_TRANSITIONS enforcement), delete (DRAFT only)
  - `app/services/order_fulfillment.py` — OrderFulfillmentService: approve_order (PLACED→APPROVED: FEFO reserve, ALLOCATION txns, FOR UPDATE per batch, all-or-nothing), dispatch_order (PACKED→DISPATCHED: STOCK_OUT txns, delete allocations), cancel_order (any CANCELLABLE status→CANCELLED: RELEASE txns + delete allocations if was RESERVED)
  - `app/api/v1/orders.py` — 8 endpoints: POST/GET/GET{id}/PATCH-status/POST-approve/POST-dispatch/POST-cancel/DELETE; ADMIN+INVENTORY_MANAGER approve; ADMIN+INVENTORY_MANAGER+WAREHOUSE_STAFF dispatch
  - `app/api/v1/router.py` — registered orders router
  - `alembic/versions/c3d4e5f6a1b2_customer_order_tables.py` — creates customer_orders, order_items, order_item_allocations; downgrade drops order_status type
- Test gate:
  - Lint/format/type: all green (75 source files)
  - Order tests: 26/26 — create (auto-number, totals with discount/tax, duplicate 409, empty items 422), allocation rule (create doesn't touch stock), transitions (draft→placed, invalid → 400, cannot PATCH to approved), approve reserves stock (ALLOCATION txns, available↓ reserved↑), approve insufficient stock 400 (no stock moved), approve requires PLACED, full lifecycle (approve→allocated→picked→packed→dispatch creates STOCK_OUT), dispatch requires PACKED, cancel draft/placed (no stock ops), cancel approved releases stock (RELEASE txns, restores quantities), cannot cancel dispatched, delete draft/cannot delete placed, list/get/404, warehouse_staff cannot create but can dispatch, sales_rep cannot approve (403), unauth 401, concurrent approval (only one wins)
  - Full suite: 242/242 passing
- Notes:
  - Allocation rule: create does NOT touch stock; approve RESERVES (ALLOCATION txns); dispatch REDUCES (STOCK_OUT txns); cancel RELEASES (RELEASE txns)
  - `ORDER_STATUS_TRANSITIONS` separates "step" transitions (no stock ops, via PATCH /status) from stock-touching transitions (via dedicated /approve, /dispatch, /cancel endpoints)
  - `line_total = unit_price × quantity − discount + tax_amount`; computed from input data (not ORM relationship) after flush to avoid MissingGreenlet
  - All-or-nothing approve: pre-check all items (no locks), then allocate per-item per-batch (SELECT FOR UPDATE); ValueError before commit → auto-rollback
  - `get_by_id_for_update` requires `execution_options={"populate_existing": True}` — without it, SQLAlchemy returns the stale identity-map object (loaded earlier by `list_allocatable_fefo`) instead of the post-lock DB values, causing both concurrent approvals to see `available=10` and both succeed
  - `OrderItemAllocation` is hard-deleted (not soft-deleted) — operational reservation tracking; audit trail lives in InventoryTransaction

## Stage 9 — Customer Management
- Date: 2026-06-10
- Built:
  - `app/models/customer.py` — Customer (TenantedEntity), CustomerStatus StrEnum (active/inactive/blacklisted), credit_limit Numeric(12,2)
  - `app/schemas/customer.py` — CustomerCreate (code uppercased, blank name rejected, credit_limit >= 0), CustomerUpdate (all fields optional, same validations), CustomerRead (from_attributes)
  - `app/repositories/customer.py` — get_by_id_not_deleted, get_by_code, list_active, list_all_not_deleted
  - `app/services/customer.py` — create (unique code check), get, list_customers (active_only filter), update (refresh after commit), delete (soft)
  - `app/api/v1/customers.py` — POST/GET/PUT/DELETE /customers; ADMIN+INVENTORY_MANAGER+SALES_REPRESENTATIVE write; all four roles read
  - `app/api/v1/router.py` — registered customers router
  - `alembic/versions/b2c3d4e5f6a1_customer_table.py` — creates customers table; downgrade drops customer_status type
- Test gate:
  - Lint/format/type: all green (66 source files)
  - Customer tests: 26/26 — create (inv_manager, sales_rep, code uppercased, all fields, dup 409, blank name 422, negative credit 422, zero credit allowed, blacklisted on create), list (all + active_only filter excludes inactive), get/404, update (credit_limit, status to blacklisted, negative credit 422, 404), soft delete then 404, delete excluded from list, role checks (wh_staff 403 on create/update, 200 on read; sales_rep can delete), unauth 401 (create + list)
  - Migration round-trip: downgrade -1 → upgrade head ✅
  - Full suite: 216/216 passing
- Notes:
  - Sales representatives can write customers (they manage customer relationships) — distinct from suppliers/warehouses which are ADMIN+INVENTORY_MANAGER only
  - `refresh` after `commit` required in update service method to avoid MissingGreenlet on `updated_at` timestamp (same pattern as purchase_order service)
  - `select` import not needed in `test_customers.py` — removed by ruff; `get_session_local` import kept (used in `_set_role`)

## Stage 8 — Purchase Management
- Date: 2026-06-10
- Built:
  - `app/models/purchase_order.py` — PurchaseOrder (TenantedEntity), PurchaseOrderItem (UUIDPrimaryKeyMixin+TimestampMixin+Base, no soft delete), PurchaseStatus StrEnum (draft/sent/confirmed/partially_received/received/cancelled), PURCHASE_STATUS_TRANSITIONS dict
  - `app/schemas/purchase_order.py` — PurchaseOrderCreate/Read, PurchaseOrderItemCreate/Read, PurchaseStatusUpdate, GoodsReceiptRequest/Response, GoodsReceiptItemRequest/Result; Decimal/Numeric(12,2) for money fields
  - `app/repositories/purchase_order.py` — PurchaseOrderRepository (BaseRepository), PurchaseOrderItemRepository (standalone — PurchaseOrderItem not BaseEntity)
  - `app/services/purchase_order.py` — create (auto/custom PO number, total_amount computed from input items), get/list_all (optional supplier_id/status filters), transition_status (validates PURCHASE_STATUS_TRANSITIONS), cancel, delete (DRAFT/CANCELLED only)
  - `app/services/purchase_receipt.py` — PurchaseReceiptService.receive: validates PO in CONFIRMED/PARTIALLY_RECEIVED state, find-or-create batch, adds STOCK_IN quantity, creates InventoryTransaction, updates item.quantity_received, re-computes PO status — all in a single session.commit(); bypasses InventoryBatchService to avoid mid-transaction commits
  - `app/api/v1/purchases.py` — POST /purchases, GET /purchases, GET /purchases/{id}, PATCH /purchases/{id}/status, POST /purchases/{id}/receive, DELETE /purchases/{id}
  - `app/api/v1/router.py` — registered purchases router
  - `alembic/versions/a1b2c3d4e5f6_purchase_order_tables.py` — creates purchase_orders + purchase_order_items tables; downgrade drops purchase_status type
- Test gate:
  - Lint/format/type: all green (61 source files)
  - Purchase tests: 23/23 — create (auto-number, custom number, duplicate 409), list/get/404, status transitions (draft→sent→confirmed, invalid → 400, terminal states locked), goods receipt (creates batch + STOCK_IN txn, partially_received, received, second receipt adds qty to same batch), receive non-confirmed → 400, wrong item id → 400, role checks (sales 403 create, sales 200 read, warehouse_staff can receive), unauth 401 (create + list), delete (draft OK then 404, confirmed → 400, unknown 404)
  - Full suite: 190/190 passing
- Notes:
  - PurchaseOrderItem extends only UUIDPrimaryKeyMixin+TimestampMixin+Base — no soft delete (items cascade-delete with parent PO); requires standalone repo, not BaseRepository
  - total_amount computed from PurchaseOrderCreate.items data (not po.items relationship) to avoid lazy-load MissingGreenlet error after flush in async context
  - PurchaseReceiptService uses _find_or_create_batch — if same medicine/warehouse/batch_number already exists (split shipments), it reuses the existing batch and adds quantity
  - PURCHASE_STATUS_TRANSITIONS enforced in service layer; RECEIVED and CANCELLED are terminal states

## Stage 7 — FEFO Allocation Engine
- Date: 2026-06-10
- Built:
  - `app/repositories/inventory_batch.py` — added `list_allocatable_fefo` (active, not-expired, qty>0, ordered by expiry_date ASC, optional warehouse filter; no lock — callers lock per-row)
  - `app/schemas/fefo.py` — FEFOAllocationRequest, BatchAllocationDetail, FEFOAllocationResponse, FEFOReleaseItem, FEFOReleaseRequest
  - `app/services/fefo.py` — FEFOService: allocate (3-step: optimistic pre-check → per-batch FOR UPDATE + re-validate → all-or-nothing commit), release_allocation
  - `app/api/v1/inventory.py` — POST /inventory/fefo/allocate, POST /inventory/fefo/release (204)
- Test gate:
  - Lint/format/type: all green (55 source files)
  - FEFO tests: 19/19 — single batch, earliest expiry first, 2-batch spill, 3-batch spill, expired batches skipped, all-expired → 400, insufficient stock → 400 + no stock reserved, no batches → 400, quantity correctness (available↓ reserved↑), one ALLOCATION txn per batch, warehouse filter, warehouse filter insufficient, release restores quantities, release creates RELEASE txns, release-over-reserved → 400, concurrent allocation (only one wins), role checks (sales 403, unauth 401, qty=0 422)
  - Full suite: 167/167 passing
- Notes:
  - FEFO is all-or-nothing: if pre-check passes but concurrent writes reduce stock below requested, ValueError raised before commit → session auto-rollbacks partial allocations
  - `list_allocatable_fefo` does NOT lock; locking happens per-row in the allocation loop via `get_by_id_for_update`; state re-validated after each lock
  - `FEFOReleaseRequest` accepts a list of `{batch_id, quantity}` — the caller (future order system, Stage 10) tracks which batches were allocated

## Stage 6 — Inventory: Batches & Transactions
- Date: 2026-06-10
- Built:
  - `app/models/inventory_batch.py` — InventoryBatch (TenantedEntity, BatchStatus: active/quarantine/exhausted/expired, unique constraint on medicine_id+warehouse_id+batch_number, FK to medicines+warehouses)
  - `app/models/inventory_transaction.py` — InventoryTransaction (immutable ledger: UUIDPrimaryKeyMixin+Base only, no updated_at, no deleted_at, TransactionType: 8 types, FK to inventory_batches+users)
  - `app/schemas/inventory_batch.py` — BatchCreate (batch_number uppercased, initial_quantity≥0), BatchRead, StockInRequest, AdjustRequest (signed delta), DamageRequest, AllocateRequest, ReleaseRequest, StockOutRequest
  - `app/schemas/inventory_transaction.py` — TransactionRead
  - `app/repositories/inventory_batch.py` — get_by_id_not_deleted, get_by_id_for_update (SELECT FOR UPDATE), get_by_batch_number, list_active, list_by_medicine, list_all
  - `app/repositories/inventory_transaction.py` — create, list_by_batch, list_all
  - `app/services/inventory_batch.py` — create_batch, stock_in, adjust, damage, allocate (with expiry check + FOR UPDATE), release, stock_out (auto-exhausts batch), get, list_batches, list_active, get_transactions, list_all_transactions
  - `app/api/v1/inventory.py` — POST /inventory/batches; GET list/get; POST stock-in/adjust/damage/allocate/release/stock-out; GET /transactions (batch-scoped + global); no DELETE endpoint
  - `alembic/versions/3e51bcf30e06_inventory_batch_transaction_tables.py` — creates both tables; downgrade drops transaction_type and batch_status types
- Five inventory rules — each has an explicit passing test:
  1. **No negative quantity** — adjust/damage/allocate/stock-out/release all reject if would go below zero
  2. **No expired stock sold** — allocate rejects if expiry_date < today; boundary: expiry_date==today is allowed; stock-in on expired batch is allowed (receiving returns)
  3. **Every movement creates a transaction** — tested for all 6 mutation endpoints
  4. **DB-transaction atomicity** — concurrent allocation test: two simultaneous requests for the last unit, only one succeeds; `SELECT ... FOR UPDATE` in `get_by_id_for_update`
  5. **Transactions never deleted** — no DELETE endpoint; DELETE to /inventory/transactions/{id} → 404/405
- Test gate:
  - Lint/format/type: all green (53 source files)
  - API tests: 38/38 new inventory tests pass
  - Migration round-trip: downgrade -1 → upgrade head ✅
  - Full suite: 148/148 passing
- Notes:
  - `InventoryTransaction` extends only `UUIDPrimaryKeyMixin + Base` (not TenantedEntity/BaseEntity) — no soft delete, no updated_at; this is enforced by design
  - Expiry boundary: `expiry_date < date.today()` = expired; `expiry_date >= date.today()` = valid
  - `freezegun` used in expiry boundary tests to pin `date.today()` to a known date
  - `SELECT ... FOR UPDATE` lock is in `InventoryBatchRepository.get_by_id_for_update`, called by every service mutation

## Stage 5 — Supplier & Warehouse Management
- Date: 2026-06-10
- Built:
  - `app/models/supplier.py` — Supplier (TenantedEntity, SupplierStatus StrEnum: active/inactive/blacklisted, supplier_code unique+indexed)
  - `app/models/warehouse.py` — Warehouse (TenantedEntity, warehouse_code unique+indexed, is_active bool)
  - `app/schemas/supplier.py` — SupplierCreate (code uppercased), SupplierUpdate, SupplierRead
  - `app/schemas/warehouse.py` — WarehouseCreate (code uppercased), WarehouseUpdate, WarehouseRead
  - `app/repositories/supplier.py` — get_by_id_not_deleted, get_by_code, list_active
  - `app/repositories/warehouse.py` — get_by_id_not_deleted, get_by_code, list_active
  - `app/services/supplier.py` — create (unique code check), get/update/delete (soft-delete aware), list_suppliers
  - `app/services/warehouse.py` — create (unique code check), get/update/delete (soft-delete aware), list_warehouses, list_active
  - `app/api/v1/suppliers.py` — full CRUD; ADMIN+INVENTORY_MANAGER write; ADMIN/INVENTORY_MANAGER/SALES_REP/WAREHOUSE_STAFF read
  - `app/api/v1/warehouses.py` — full CRUD + active_only filter; same role split as suppliers
  - `alembic/versions/243cb5a43ba6_supplier_warehouse_tables.py` — creates suppliers+warehouses; downgrade drops tables and supplier_status type
- Test gate:
  - Lint/format/type: all green (45 source files, alembic/versions excluded from ruff)
  - API tests: 38/38 — suppliers (create by inv_manager/admin, code uppercased, dup code 409, customer/sales blocked, unauthed 401, list all roles, get by id, 404, update, update 404, sales can't update, soft delete then 404, delete 404), warehouses (same set + active_only filter, warehouse_staff read/write split)
  - Migration round-trip: downgrade -1 → upgrade head ✅
  - Full suite: 110/110 passing

## Stage 4 — Medicine Management
- Date: 2026-06-10
- Built:
  - `app/models/medicine.py` — Medicine (TenantedEntity, DosageForm StrEnum 10 values, MedicineStatus StrEnum, code unique+indexed)
  - `app/schemas/medicine.py` — MedicineCreate (code uppercased, blank-string validation), MedicineUpdate (all fields optional), MedicineRead
  - `app/repositories/medicine.py` — get_by_id_not_deleted (soft-delete aware), get_by_code, search (ilike on name/generic_name/code), list_active
  - `app/services/medicine.py` — create (unique code check), get/update/delete (all soft-delete aware), list_medicines, list_active, search
  - `app/api/v1/medicines.py` — POST/GET/PUT/DELETE /medicines; GET /medicines/search; active_only query param; ADMIN+INVENTORY_MANAGER write, all roles read
  - `alembic/versions/ddd492b27acf_medicine_table.py` — creates medicines table with lowercase enum values; downgrade drops dosage_form and medicine_status types
- Test gate:
  - Lint/format/type: all green (35 files)
  - API tests: 18/18 — create (inv_manager, admin, dup code rejected, code uppercased, bad dosage_form rejected, blank name rejected, customer/sales blocked), list (all roles), get by id, 404, search, active_only filter, update, update 404, soft delete (then 404), warehouse staff read-OK/write-403
  - Migration round-trip: downgrade -1 → upgrade head ✅
  - Full suite: 72/72 passing
- Notes:
  - `values_callable=lambda x: [e.value for e in x]` is required on all `Enum(StrEnum, ...)` columns — without it SQLAlchemy autogenerate uses member NAMES (uppercase) for the PostgreSQL CREATE TYPE, but the ORM stores lowercase VALUES, causing insert failures in the dev DB (tests use create_all which is always lowercase)
  - `BaseRepository.get_by_id` uses `session.get()` which ignores deleted_at — always use `get_by_id_not_deleted` for domain queries that should respect soft delete

## Stage 3 — User Management & RBAC
- Date: 2026-06-10
- Built:
  - `app/schemas/user.py` — UserRead, UserUpdate (admin), UserUpdateMe (self)
  - `app/services/user.py` — get_me, update_me (duplicate-email check), list_users, get_user, update_user, delete_user (soft)
  - `app/api/v1/users.py` — GET/PUT /users/me (any authed user); GET /users, GET /users/{id}, PUT /users/{id}, DELETE /users/{id} (admin-only via require_roles)
- Test gate:
  - Lint/format/type: all green (30 files)
  - API tests: 13/13 — get_me (profile correct, auth required), update_me (email change, dup email rejected), list_users (admin OK, non-admin 403), get_user (admin OK, 404 for unknown), role change, deactivate, soft delete, non-admin delete blocked, all 4 non-admin roles get 403 on admin endpoints
  - Full suite: 54/54 passing
- Notes:
  - HTTPBearer returns 401 (no credentials), not 403 — 403 is role-insufficient only
  - Role is baked into the JWT at login time; after a DB role change the user must re-login to get a token reflecting the new role

## Stage 2 — Authentication (JWT + refresh tokens)
- Date: 2026-06-10
- Built:
  - `app/models/user.py` — User (TenantedEntity, UserRole StrEnum, bcrypt password_hash, is_active/is_verified)
  - `app/models/refresh_token.py` — RefreshToken (SHA-256 hash of raw JWT, expires_at, revoked_at)
  - `alembic/versions/c5e7141603fd_auth_tables.py` — creates users + refresh_tokens; downgrade drops user_role enum explicitly
  - `app/core/security.py` — bcrypt hash/verify, SHA-256 token hashing, JWT access/refresh create/decode; refresh tokens include jti=uuid4() to prevent hash collisions within the same second
  - `app/schemas/auth.py` — LoginRequest, RegisterRequest (>=8 char password validator), RefreshRequest, LogoutRequest, LoginResponse
  - `app/repositories/user.py` — get_by_email, get_by_id_active, create, update_password, set_verified
  - `app/repositories/refresh_token.py` — create, get_by_hash (non-revoked + non-expired filter), revoke, revoke_all_for_user
  - `app/services/auth.py` — login, logout, refresh (token rotation), register, logout_all
  - `app/core/deps.py` — get_current_user dependency, CurrentUser Annotated alias, require_roles factory
  - `app/api/v1/auth.py` — POST /login, /refresh, /logout, /register
- Test gate:
  - Lint/format/type: ruff check, ruff format --check, mypy app — all green (27 files)
  - Unit: 13/13 — bcrypt hash/verify, token hashing determinism, JWT create/decode, tamper/type/expiry rejection
  - API integration: 12/12 — register (success, dup email, short password), login (success, wrong pw, unknown email), hashed password stored as bcrypt, refresh rotation, replay attack rejected, logout invalidates token
  - Migration round-trip: downgrade -1 → upgrade head ✅
  - Full suite: 41/41 passing
- Notes:
  - jti=str(uuid.uuid4()) in refresh JWT is required: python-jose encodes iat/exp as integer seconds, so same-user tokens issued within the same second are byte-identical → same SHA-256 hash → unique constraint violation
  - conftest._prepare_database must do drop_all before create_all (stale data from a crashed run breaks unique constraints) and must import app.models first so Base.metadata knows about all tables
  - enum.StrEnum (Python 3.11+) replaces the str+enum.Enum pattern

## Stage 0 — Project skeleton & tooling
- Date: 2026-06-08
- Built: `backend/` (FastAPI app factory, structured JSON logging with request-id/user-id context,
  centralized exception handlers, standard `{success, data}` / `{success, message}` envelope,
  Pydantic v2 settings, async SQLAlchemy 2.0 engine/session, Alembic wired for async autogenerate,
  health endpoint). `frontend/` (React 19 + TS + Vite + Tailwind v4 + TanStack Query + React Hook
  Form + Zod + React Router + axios, vitest + RTL). `docker-compose.yml` (Postgres 16, Redis 7),
  `.vscode/` (settings, launch, extensions), `.pre-commit-config.yaml`, `pyproject.toml` with
  ruff/mypy/pytest config.
- Test gate:
  - Backend lint/format/type: `ruff check`, `ruff format --check`, `mypy app` — all green.
  - Frontend lint/type: `eslint .`, `tsc -b` — all green.
  - Frontend tests: `vitest run` — 2/2 passing (Dashboard renders title + shows health status).
  - App boots: `uvicorn app.main:app` serves `/api/v1/health` → `{"success":true,"data":{"status":"ok"}}`
    with `X-Request-ID` header; `npm run dev` serves on :5173.
  - Migrations: pending — see TODO below (no models yet, so nothing to autogenerate).
  - Backend API/integration tests against Postgres: pending — see TODO.
- Gate fully passed on 2026-06-09 after DB credentials were provided.
- Coverage: 94% across 16 tests (2 API + 7 integration + 7 unit).
- Notes:
  - `@` in password URL-encoded as `%40` in DATABASE_URL; alembic `set_main_option` needs
    `%.replace("%", "%%")` escape to avoid configparser interpolation errors.
  - asyncpg on Windows IocpProactor requires all async fixtures AND tests to use the same
    session-scoped event loop; solved via `loop_scope="session"` on all `@pytest_asyncio.fixture`
    decorators + `pytestmark = pytest.mark.asyncio(loop_scope="session")` in test modules.
  - Engine + sessionmaker are lazy (`@lru_cache` factory functions) so tests can inject the
    test DATABASE_URL via `pytest_configure` before the first connection is established.
- Deferred: Redis/Celery wiring to Stage 13 (no Docker locally; docker-compose for CI/future).
