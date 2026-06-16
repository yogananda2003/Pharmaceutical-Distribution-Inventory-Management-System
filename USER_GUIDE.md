# Pharma Distribution & Inventory Management — User Guide

> **Complete workflow: from adding stock to delivering to the customer.**

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Starting the Application](#2-starting-the-application)
3. [User Roles & Access](#3-user-roles--access)
4. [Step-by-Step Workflow](#4-step-by-step-workflow)
   - [Phase 1 — One-Time Setup (Admin)](#phase-1--one-time-setup-admin)
   - [Phase 2 — Adding Stock (Purchase Order)](#phase-2--adding-stock-purchase-order)
   - [Phase 3 — Receiving Goods into Warehouse](#phase-3--receiving-goods-into-warehouse)
   - [Phase 4 — Customer Places an Order](#phase-4--customer-places-an-order)
   - [Phase 5 — Order Approval & Stock Reservation](#phase-5--order-approval--stock-reservation)
   - [Phase 6 — Warehouse Picks & Packs](#phase-6--warehouse-picks--packs)
   - [Phase 7 — Dispatch & Delivery](#phase-7--dispatch--delivery)
   - [Phase 8 — Invoice & Payment](#phase-8--invoice--payment)
5. [Expiry Management](#5-expiry-management)
6. [Reports](#6-reports)
7. [API Quick Reference (Swagger)](#7-api-quick-reference-swagger)
8. [Default Login Credentials](#8-default-login-credentials)

---

## 1. System Overview

```
Supplier → Purchase Order → Receive Stock → Warehouse Batch
                                                   ↓
Customer → Sales Order → Approve (Reserve) → Pick/Pack → Dispatch → Invoice
```

The system tracks medicines by **batch** (batch number + expiry date + warehouse). When stock is reserved for an order, it uses **FEFO** (First Expire First Out) — oldest expiry date is used first.

---

## 2. Starting the Application

**Terminal 1 — Backend API:**
```powershell
cd "d:\OneDrive - MindsprintDigital\Desktop\yogananda\yogananda\medical-inventory&sales-mangement\backend"
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000
```

**Terminal 2 — Frontend:**
```powershell
cd "d:\OneDrive - MindsprintDigital\Desktop\yogananda\yogananda\medical-inventory&sales-mangement\frontend"
node .\node_modules\vite\bin\vite.js
```

| URL | Purpose |
|-----|---------|
| http://localhost:5173 | Frontend (Login page) |
| http://localhost:8000/docs | Swagger API (interactive) |
| http://localhost:8000/api/v1/health | Health check |

---

## 3. User Roles & Access

| Role | What they do |
|------|-------------|
| `admin` | Full access — manage users, all master data, all operations |
| `inventory_manager` | Add/edit medicines, suppliers, warehouses, purchase orders, batches |
| `sales_representative` | Create customers, create & manage sales orders, generate invoices |
| `warehouse_staff` | View pick lists, transfer stock between batches |
| `customer` | Place orders, view order history (frontend portal) |

---

## 4. Step-by-Step Workflow

---

### Phase 1 — One-Time Setup (Admin)

> Do this once before any buying or selling.

#### 1a. Create a Medicine (Product)

**Who:** Admin or Inventory Manager  
**Swagger:** `POST /api/v1/medicines`  
**Frontend:** Not yet (use Swagger)

```json
{
  "code": "MED001",
  "name": "Paracetamol 500mg",
  "generic_name": "Acetaminophen",
  "manufacturer": "ABC Pharma",
  "dosage_form": "Tablet",
  "strength": "500mg",
  "unit_type": "Strip",
  "reorder_level": 100,
  "max_stock_level": 5000
}
```

#### 1b. Create a Warehouse

**Swagger:** `POST /api/v1/warehouses`

```json
{
  "warehouse_code": "WH001",
  "warehouse_name": "Main Warehouse",
  "address": "123 Storage Road, Hyderabad",
  "capacity": 10000,
  "is_active": true
}
```

#### 1c. Create a Supplier

**Swagger:** `POST /api/v1/suppliers`

```json
{
  "supplier_code": "SUP001",
  "name": "MedSupply Corp",
  "email": "orders@medsupply.com",
  "phone": "9876543210",
  "address": "456 Supply Lane, Mumbai"
}
```

#### 1d. Create a Customer

**Who:** Admin, Inventory Manager, or Sales Representative  
**Swagger:** `POST /api/v1/customers`

```json
{
  "customer_code": "CUST001",
  "business_name": "City Medical Store",
  "email": "city@medical.com",
  "phone": "9988776655",
  "address": "789 Shop Street, Bangalore",
  "credit_limit": "500000.00"
}
```

---

### Phase 2 — Adding Stock (Purchase Order)

> You can't add stock directly — stock only enters through a Purchase Order.

#### 2a. Create a Purchase Order

**Who:** Inventory Manager / Admin  
**Swagger:** `POST /api/v1/purchases`

```json
{
  "supplier_id": "<supplier-uuid>",
  "order_date": "2026-06-16",
  "expected_delivery_date": "2026-06-20",
  "items": [
    {
      "medicine_id": "<medicine-uuid>",
      "quantity_ordered": 1000,
      "unit_price": "5.50"
    }
  ]
}
```

The PO is created in **DRAFT** status.

#### 2b. Confirm the Purchase Order

**Swagger:** `PATCH /api/v1/purchases/{po_id}/status`

```json
{ "status": "confirmed" }
```

Status flow:
```
DRAFT → CONFIRMED → PARTIALLY_RECEIVED → RECEIVED → CANCELLED
```

---

### Phase 3 — Receiving Goods into Warehouse

> This creates the actual inventory batch with expiry date.

#### 3a. Receive goods against the PO

**Who:** Inventory Manager / Admin  
**Swagger:** `POST /api/v1/purchases/{po_id}/receive`

```json
{
  "received_date": "2026-06-20",
  "items": [
    {
      "medicine_id": "<medicine-uuid>",
      "quantity_received": 1000,
      "batch_number": "BATCH-2026-001",
      "expiry_date": "2028-12-31",
      "warehouse_id": "<warehouse-uuid>",
      "unit_cost": "5.50"
    }
  ]
}
```

This automatically:
- Creates an **InventoryBatch** (batch number + expiry date + warehouse)
- Records a **STOCK_IN** transaction in the audit log
- Updates the PO status to `RECEIVED`

**Verify stock was added:** `GET /api/v1/inventory/batches`

---

### Phase 4 — Customer Places an Order

#### Option A: Via Frontend (Sales Rep logs in)

1. Log in at **http://localhost:5173** as `sales@pharma.com` / `Sales@1234!`
2. Click **+ New Order**
3. Search for medicines → Add to cart → set quantities & prices
4. Click **Place Order →**
5. Select the customer, confirm date → **Place Order**

The order is created in **PLACED** status.

#### Option B: Via Swagger

**Swagger:** `POST /api/v1/orders`

```json
{
  "customer_id": "<customer-uuid>",
  "order_date": "2026-06-16",
  "items": [
    {
      "medicine_id": "<medicine-uuid>",
      "quantity": 50,
      "unit_price": "12.00",
      "discount": "0.00",
      "tax_amount": "0.00"
    }
  ]
}
```

---

### Phase 5 — Order Approval & Stock Reservation

> Approval automatically reserves stock using FEFO.

**Who:** Admin or Inventory Manager  
**Swagger:** `POST /api/v1/orders/{order_id}/approve`  
**Frontend:** Sales portal → Order Management → click **Approve**

No request body needed. The system:
1. Checks that enough stock is available
2. Runs **FEFO** allocation — picks the batch expiring soonest
3. Moves quantity from `available` → `reserved` on the batch
4. Records an **ALLOCATION** transaction
5. Moves order to **APPROVED** status

Status flow:
```
PLACED → APPROVED → ALLOCATED → PICKED → PACKED → DISPATCHED → DELIVERED → COMPLETED
```

If insufficient stock: returns `422` error — you need to receive more stock first (Phase 2–3).

---

### Phase 6 — Warehouse Picks & Packs

> These steps are handled by warehouse staff.

#### 6a. Get the Pick List

**Swagger:** `GET /api/v1/warehouse/orders/{order_id}/pick-list`

Returns a list of which batches to pick from (batch number, shelf location, quantity).

#### 6b. Advance through statuses

```
APPROVED → ALLOCATED → PICKED → PACKED
```

Use `PATCH /api/v1/orders/{order_id}/status` to advance each step:

```json
{ "status": "allocated" }
```
Then:
```json
{ "status": "picked" }
```
Then:
```json
{ "status": "packed" }
```

---

### Phase 7 — Dispatch & Delivery

#### 7a. Dispatch the order

**Who:** Admin or Sales Representative  
**Swagger:** `POST /api/v1/orders/{order_id}/dispatch`  
**Frontend:** Sales portal → Order Management → click **Dispatch** (appears when status = packed)

No request body needed. This:
- Records a **STOCK_OUT** transaction
- Removes quantity from the reserved batch
- Moves order to **DISPATCHED** status

#### 7b. Mark as Delivered

**Swagger:** `PATCH /api/v1/orders/{order_id}/status`

```json
{ "status": "delivered" }
```

#### 7c. Mark as Completed

```json
{ "status": "completed" }
```

---

### Phase 8 — Invoice & Payment

#### 8a. Generate Invoice

**Who:** Admin, Inventory Manager, or Sales Representative  
**Swagger:** `POST /api/v1/invoices`

```json
{
  "order_id": "<order-uuid>",
  "invoice_date": "2026-06-16",
  "due_date": "2026-07-16",
  "notes": "Payment due in 30 days"
}
```

This creates an invoice with status **PENDING**.

**Frontend:** Customer portal → Order Detail page shows the invoice automatically.

#### 8b. Mark Invoice as Paid

**Who:** Admin or Inventory Manager  
**Swagger:** `PATCH /api/v1/invoices/{invoice_id}/status`

```json
{ "status": "paid" }
```

Invoice statuses: `PENDING → PAID` or `PENDING → OVERDUE → PAID`

---

## 5. Expiry Management

The system tracks medicine expiry dates per batch and sends alerts.

| Endpoint | What it shows |
|----------|--------------|
| `GET /api/v1/expiry/dashboard` | Count summary: expired, expiring in 30/60/90 days |
| `GET /api/v1/expiry/expired` | All batches already past expiry date |
| `GET /api/v1/expiry/near-expiry?days=30` | Batches expiring within 30 days (or 60/90) |

**Action on expired stock:**
1. Use `GET /api/v1/expiry/expired` to find batches
2. Use `POST /api/v1/inventory/batches/{batch_id}/damage` to write them off:
   ```json
   { "quantity": 500, "reason": "Expired" }
   ```

**FEFO ensures** that stock nearing expiry is always picked first when approving orders.

---

## 6. Reports

All reports are read-only. Access via `GET /api/v1/reports/...`

| Report | URL | Shows |
|--------|-----|-------|
| Current Inventory | `/reports/inventory/current` | Available + reserved stock per medicine |
| Batch Detail | `/reports/inventory/batches` | Per-batch breakdown with expiry & warehouse |
| Expiry Report | `/reports/inventory/expiry` | Expired + near-expiry batches |
| Transaction Ledger | `/reports/transactions` | Every stock movement with date filter |
| Purchase Summary | `/reports/purchases` | PO history by supplier, quantity received |
| Sales Summary | `/reports/sales` | Order history with invoice status |
| Customer Summary | `/reports/customers` | Per-customer: total orders, value, completed |
| Fulfillment Report | `/reports/orders/fulfillment` | Orders grouped by status with values |

**Example — filter transactions by date:**
```
GET /api/v1/reports/transactions?date_from=2026-06-01&date_to=2026-06-30
```

---

## 7. API Quick Reference (Swagger)

Open **http://localhost:8000/docs** with the backend running.

To authenticate in Swagger:
1. Expand `POST /api/v1/auth/login`
2. Click **Try it out** → enter email/password → **Execute**
3. Copy the `access_token` from the response
4. Click the **Authorize** button (top right, 🔓)
5. Enter: `Bearer <your-token>` → **Authorize**

All locked endpoints will now work.

---

## 8. Default Login Credentials

| Email | Password | Role |
|-------|----------|------|
| `admin@pharma.com` | `Admin@1234!` | Admin — full access |
| `sales@pharma.com` | `Sales@1234!` | Sales Representative |
| `inventory@pharma.com` | `Inventory@1` | Inventory Manager |
| `warehouse@pharma.com` | `Warehouse@1` | Warehouse Staff |
| `customer@pharma.com` | `Customer@1` | Customer |

> These were created by running `python scripts/seed_users.py` from the backend directory.  
> Run it again at any time — it skips users that already exist.

---

## Full Workflow Summary

```
1. ADMIN SETUP
   Create Medicine → Create Warehouse → Create Supplier → Create Customer

2. BUY STOCK
   Create PO (Draft) → Confirm PO → Receive Goods (creates Inventory Batch)

3. SELL
   Create Order (Placed) → Approve (reserves stock via FEFO) →
   Allocated → Picked → Packed → Dispatch (removes stock) →
   Delivered → Completed

4. INVOICE
   Generate Invoice → Mark Paid

5. MONITOR
   Expiry Dashboard → Reports → Adjust/Damage stock as needed
```
