"""Stage 14 — Reporting module tests.

Tests verify:
- GET /reports/inventory/current  — per-medicine aggregated stock
- GET /reports/inventory/batches  — per-batch detail, expiry filter
- GET /reports/inventory/expiry   — expired + near-expiry with alert_level
- GET /reports/transactions       — stock movement ledger with type filter
- GET /reports/purchases          — PO summary with supplier and qty totals
- GET /reports/sales              — order summary with linked invoice
- GET /reports/customers          — customer account summary with order totals
- GET /reports/orders/fulfillment — order counts by status
- warehouse_id / medicine_id / customer_id / date filters work
- Role checks: ADMIN/INV_MGR can access all; WAREHOUSE_STAFF can access inventory;
  SALES_REP can access business; each blocked from the other; unauth → 401
"""

from __future__ import annotations

import uuid

import pytest
from freezegun import freeze_time
from httpx import AsyncClient
from sqlalchemy import select

from app.core.db import get_session_local
from app.models.user import User, UserRole

pytestmark = pytest.mark.asyncio(loop_scope="session")

_TODAY = "2026-06-12"
_FAR = "2029-12-31"


# ── auth helpers ───────────────────────────────────────────────────────────────


async def _register_and_login(client: AsyncClient, email: str, password: str = "Pass1234") -> dict:
    await client.post("/api/v1/auth/register", json={"email": email, "password": password})
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return resp.json()["data"]


async def _set_role(email: str, role: UserRole) -> None:
    async with get_session_local()() as session:
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one()
        user.role = role
        await session.commit()


async def _token_for_role(client: AsyncClient, email: str, role: UserRole) -> str:
    await _register_and_login(client, email)
    await _set_role(email, role)
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": "Pass1234"})
    return resp.json()["data"]["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _inv_token(client: AsyncClient, suffix: str) -> str:
    return await _token_for_role(client, f"invr14_{suffix}@example.com", UserRole.INVENTORY_MANAGER)


async def _wh_token(client: AsyncClient, suffix: str) -> str:
    return await _token_for_role(client, f"whr14_{suffix}@example.com", UserRole.WAREHOUSE_STAFF)


async def _sales_token(client: AsyncClient, suffix: str) -> str:
    return await _token_for_role(
        client, f"slsr14_{suffix}@example.com", UserRole.SALES_REPRESENTATIVE
    )


# ── entity helpers ─────────────────────────────────────────────────────────────


async def _create_medicine(client: AsyncClient, token: str, code: str) -> str:
    resp = await client.post(
        "/api/v1/medicines",
        json={
            "code": code,
            "name": f"Med {code}",
            "generic_name": "G",
            "manufacturer": "M",
            "dosage": "10mg",
            "strength": "10mg",
            "dosage_form": "tablet",
            "unit_type": "Strip",
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


async def _create_warehouse(client: AsyncClient, token: str, code: str) -> str:
    resp = await client.post(
        "/api/v1/warehouses",
        json={"warehouse_code": code, "warehouse_name": f"WH {code}"},
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


async def _create_batch(
    client: AsyncClient,
    token: str,
    medicine_id: str,
    warehouse_id: str,
    *,
    batch_number: str,
    expiry_date: str = _FAR,
    qty: int = 100,
) -> str:
    resp = await client.post(
        "/api/v1/inventory/batches",
        json={
            "medicine_id": medicine_id,
            "warehouse_id": warehouse_id,
            "batch_number": batch_number,
            "expiry_date": expiry_date,
            "initial_quantity": qty,
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


async def _create_supplier(client: AsyncClient, token: str, code: str) -> str:
    resp = await client.post(
        "/api/v1/suppliers",
        json={"supplier_code": code, "supplier_name": f"Sup {code}"},
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


async def _create_customer(client: AsyncClient, token: str, code: str) -> str:
    resp = await client.post(
        "/api/v1/customers",
        json={
            "customer_code": code,
            "business_name": f"Biz {code}",
            "credit_limit": "50000.00",
            "status": "active",
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


async def _create_po(
    client: AsyncClient,
    token: str,
    supplier_id: str,
    medicine_id: str,
    *,
    qty: int = 50,
    unit_price: str = "20.00",
) -> str:
    resp = await client.post(
        "/api/v1/purchases",
        json={
            "supplier_id": supplier_id,
            "order_date": _TODAY,
            "items": [
                {
                    "medicine_id": medicine_id,
                    "quantity_ordered": qty,
                    "unit_price": unit_price,
                }
            ],
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


async def _place_and_dispatch_order(
    client: AsyncClient,
    token: str,
    customer_id: str,
    medicine_id: str,
    *,
    qty: int = 5,
    unit_price: str = "100.00",
) -> str:
    """Create + walk order to DISPATCHED; return order_id."""
    resp = await client.post(
        "/api/v1/orders",
        json={
            "customer_id": customer_id,
            "order_date": _TODAY,
            "items": [
                {
                    "medicine_id": medicine_id,
                    "quantity": qty,
                    "unit_price": unit_price,
                    "discount": "0.00",
                    "tax_amount": "0.00",
                }
            ],
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    oid = resp.json()["data"]["id"]

    await client.patch(
        f"/api/v1/orders/{oid}/status",
        json={"status": "placed"},
        headers=_auth(token),
    )
    await client.post(f"/api/v1/orders/{oid}/approve", headers=_auth(token))
    for s in ("allocated", "picked", "packed"):
        await client.patch(f"/api/v1/orders/{oid}/status", json={"status": s}, headers=_auth(token))
    r = await client.post(f"/api/v1/orders/{oid}/dispatch", headers=_auth(token))
    assert r.status_code == 200, r.text
    return oid


# ── 1. Current inventory report ────────────────────────────────────────────────


@freeze_time(_TODAY)
async def test_current_inventory_shows_medicine(client: AsyncClient) -> None:
    tok = await _inv_token(client, "ci1")
    med = await _create_medicine(client, tok, f"CI1{uuid.uuid4().hex[:4]}")
    wh = await _create_warehouse(client, tok, f"CWH{uuid.uuid4().hex[:4]}")
    await _create_batch(client, tok, med, wh, batch_number="CI-001", qty=200)

    resp = await client.get(
        f"/api/v1/reports/inventory/current?medicine_id={med}", headers=_auth(tok)
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 1
    row = data[0]
    assert row["medicine_id"] == med
    assert row["total_available"] == 200
    assert row["total_on_hand"] == 200
    assert row["active_batch_count"] == 1
    assert row["warehouse_count"] == 1


@freeze_time(_TODAY)
async def test_current_inventory_aggregates_across_warehouses(client: AsyncClient) -> None:
    tok = await _inv_token(client, "ci2")
    med = await _create_medicine(client, tok, f"CI2{uuid.uuid4().hex[:4]}")
    wh1 = await _create_warehouse(client, tok, f"CW1{uuid.uuid4().hex[:4]}")
    wh2 = await _create_warehouse(client, tok, f"CW2{uuid.uuid4().hex[:4]}")
    await _create_batch(client, tok, med, wh1, batch_number="CI-W1", qty=100)
    await _create_batch(client, tok, med, wh2, batch_number="CI-W2", qty=150)

    resp = await client.get(
        f"/api/v1/reports/inventory/current?medicine_id={med}", headers=_auth(tok)
    )
    assert resp.status_code == 200
    row = resp.json()["data"][0]
    assert row["total_available"] == 250
    assert row["active_batch_count"] == 2
    assert row["warehouse_count"] == 2


@freeze_time(_TODAY)
async def test_current_inventory_warehouse_filter(client: AsyncClient) -> None:
    tok = await _inv_token(client, "ci3")
    med = await _create_medicine(client, tok, f"CI3{uuid.uuid4().hex[:4]}")
    wh1 = await _create_warehouse(client, tok, f"WF1{uuid.uuid4().hex[:4]}")
    wh2 = await _create_warehouse(client, tok, f"WF2{uuid.uuid4().hex[:4]}")
    await _create_batch(client, tok, med, wh1, batch_number="CF-W1", qty=80)
    await _create_batch(client, tok, med, wh2, batch_number="CF-W2", qty=120)

    resp = await client.get(
        f"/api/v1/reports/inventory/current?warehouse_id={wh1}&medicine_id={med}",
        headers=_auth(tok),
    )
    assert resp.status_code == 200
    row = resp.json()["data"][0]
    assert row["total_available"] == 80


# ── 2. Batch inventory report ──────────────────────────────────────────────────


@freeze_time(_TODAY)
async def test_batch_inventory_filter_by_medicine(client: AsyncClient) -> None:
    tok = await _inv_token(client, "bi1")
    med = await _create_medicine(client, tok, f"BI1{uuid.uuid4().hex[:4]}")
    wh = await _create_warehouse(client, tok, f"BW1{uuid.uuid4().hex[:4]}")
    await _create_batch(client, tok, med, wh, batch_number="BI-001", qty=50)

    resp = await client.get(
        f"/api/v1/reports/inventory/batches?medicine_id={med}", headers=_auth(tok)
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) >= 1
    assert all(b["medicine_id"] == med for b in data)
    row = data[0]
    assert "batch_number" in row
    assert "days_to_expiry" in row
    assert "quantity_available" in row


@freeze_time(_TODAY)
async def test_batch_inventory_expiry_before_filter(client: AsyncClient) -> None:
    """expiry_before filter returns only batches expiring before the cutoff."""
    tok = await _inv_token(client, "bi2")
    med = await _create_medicine(client, tok, f"BI2{uuid.uuid4().hex[:4]}")
    wh = await _create_warehouse(client, tok, f"BW2{uuid.uuid4().hex[:4]}")
    await _create_batch(client, tok, med, wh, batch_number="BI-SOON", expiry_date="2026-07-01")
    await _create_batch(client, tok, med, wh, batch_number="BI-FAR", expiry_date="2030-01-01")

    resp = await client.get(
        f"/api/v1/reports/inventory/batches?medicine_id={med}&expiry_before=2027-01-01",
        headers=_auth(tok),
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    batch_numbers = [b["batch_number"] for b in data]
    assert "BI-SOON" in batch_numbers
    assert "BI-FAR" not in batch_numbers


# ── 3. Expiry report ───────────────────────────────────────────────────────────


@freeze_time(_TODAY)
async def test_expiry_report_includes_expired_and_near_expiry(client: AsyncClient) -> None:
    tok = await _inv_token(client, "er1")
    med = await _create_medicine(client, tok, f"ER1{uuid.uuid4().hex[:4]}")
    wh = await _create_warehouse(client, tok, f"ERW{uuid.uuid4().hex[:4]}")
    await _create_batch(client, tok, med, wh, batch_number="ER-EXP", expiry_date="2026-06-01")
    await _create_batch(client, tok, med, wh, batch_number="ER-NEAR", expiry_date="2026-07-01")

    resp = await client.get("/api/v1/reports/inventory/expiry", headers=_auth(tok))
    assert resp.status_code == 200
    data = resp.json()["data"]
    med_ids = [b["medicine_id"] for b in data]
    assert med in med_ids

    levels = {b["batch_number"]: b["alert_level"] for b in data if b["medicine_id"] == med}
    assert levels.get("ER-EXP") == "expired"
    assert levels.get("ER-NEAR") in ("critical", "warning", "caution")


# ── 4. Stock movements report ──────────────────────────────────────────────────


@freeze_time(_TODAY)
async def test_stock_movements_medicine_filter(client: AsyncClient) -> None:
    tok = await _inv_token(client, "sm1")
    med = await _create_medicine(client, tok, f"SM1{uuid.uuid4().hex[:4]}")
    wh = await _create_warehouse(client, tok, f"SMW{uuid.uuid4().hex[:4]}")
    await _create_batch(client, tok, med, wh, batch_number="SM-001", qty=50)

    resp = await client.get(f"/api/v1/reports/transactions?medicine_id={med}", headers=_auth(tok))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) >= 1
    assert all(r["medicine_id"] == med for r in data)
    row = data[0]
    assert row["transaction_type"] == "stock_in"
    assert row["quantity"] == 50
    assert "batch_number" in row
    assert "medicine_name" in row
    assert "warehouse_name" in row


@freeze_time(_TODAY)
async def test_stock_movements_type_filter(client: AsyncClient) -> None:
    tok = await _inv_token(client, "sm2")
    med = await _create_medicine(client, tok, f"SM2{uuid.uuid4().hex[:4]}")
    wh = await _create_warehouse(client, tok, f"SW2{uuid.uuid4().hex[:4]}")
    await _create_batch(client, tok, med, wh, batch_number="SM-002", qty=50)

    resp = await client.get(
        f"/api/v1/reports/transactions?medicine_id={med}&transaction_type=stock_in",
        headers=_auth(tok),
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert all(r["transaction_type"] == "stock_in" for r in data)


# ── 5. Purchase report ─────────────────────────────────────────────────────────


@freeze_time(_TODAY)
async def test_purchase_report_shows_po(client: AsyncClient) -> None:
    tok = await _inv_token(client, "pr1")
    sup = await _create_supplier(client, tok, f"SP1{uuid.uuid4().hex[:4]}")
    med = await _create_medicine(client, tok, f"PR1{uuid.uuid4().hex[:4]}")
    po_id = await _create_po(client, tok, sup, med, qty=100, unit_price="15.00")

    resp = await client.get(f"/api/v1/reports/purchases?supplier_id={sup}", headers=_auth(tok))
    assert resp.status_code == 200
    data = resp.json()["data"]
    po_ids = [r["po_id"] for r in data]
    assert po_id in po_ids

    row = next(r for r in data if r["po_id"] == po_id)
    assert row["item_count"] == 1
    assert row["total_ordered_qty"] == 100
    assert row["total_received_qty"] == 0
    assert float(row["total_amount"]) == pytest.approx(1500.0)


@freeze_time(_TODAY)
async def test_purchase_report_date_filter(client: AsyncClient) -> None:
    tok = await _inv_token(client, "pr2")
    sup = await _create_supplier(client, tok, f"SP2{uuid.uuid4().hex[:4]}")
    med = await _create_medicine(client, tok, f"PR2{uuid.uuid4().hex[:4]}")
    po_id = await _create_po(client, tok, sup, med)

    # Filter to a range that includes today
    resp = await client.get(
        "/api/v1/reports/purchases?date_from=2026-06-01&date_to=2026-06-30",
        headers=_auth(tok),
    )
    assert resp.status_code == 200
    ids = [r["po_id"] for r in resp.json()["data"]]
    assert po_id in ids

    # Filter to a range that excludes today
    resp2 = await client.get(
        "/api/v1/reports/purchases?date_from=2025-01-01&date_to=2025-12-31",
        headers=_auth(tok),
    )
    assert resp2.status_code == 200
    ids2 = [r["po_id"] for r in resp2.json()["data"]]
    assert po_id not in ids2


# ── 6. Sales report ────────────────────────────────────────────────────────────


@freeze_time(_TODAY)
async def test_sales_report_shows_dispatched_order(client: AsyncClient) -> None:
    tok = await _inv_token(client, "sr1")
    med = await _create_medicine(client, tok, f"SR1{uuid.uuid4().hex[:4]}")
    wh = await _create_warehouse(client, tok, f"SRW{uuid.uuid4().hex[:4]}")
    cust = await _create_customer(client, tok, f"SC1{uuid.uuid4().hex[:4]}")
    await _create_batch(client, tok, med, wh, batch_number="SR-001", qty=100)
    order_id = await _place_and_dispatch_order(client, tok, cust, med, qty=5)

    resp = await client.get(f"/api/v1/reports/sales?customer_id={cust}", headers=_auth(tok))
    assert resp.status_code == 200
    data = resp.json()["data"]
    order_ids = [r["order_id"] for r in data]
    assert order_id in order_ids

    row = next(r for r in data if r["order_id"] == order_id)
    assert row["status"] == "dispatched"
    assert row["item_count"] == 1
    assert float(row["total_amount"]) == pytest.approx(500.0)
    assert row["invoice_number"] is None  # no invoice generated yet
    assert row["invoice_status"] is None


@freeze_time(_TODAY)
async def test_sales_report_shows_invoice_when_generated(client: AsyncClient) -> None:
    tok = await _inv_token(client, "sr2")
    med = await _create_medicine(client, tok, f"SR2{uuid.uuid4().hex[:4]}")
    wh = await _create_warehouse(client, tok, f"SR2W{uuid.uuid4().hex[:4]}")
    cust = await _create_customer(client, tok, f"SC2{uuid.uuid4().hex[:4]}")
    await _create_batch(client, tok, med, wh, batch_number="SR-002", qty=100)
    order_id = await _place_and_dispatch_order(client, tok, cust, med, qty=3)

    # Generate invoice
    resp_inv = await client.post(
        "/api/v1/invoices",
        json={"order_id": order_id},
        headers=_auth(tok),
    )
    assert resp_inv.status_code == 201, resp_inv.text

    resp = await client.get(f"/api/v1/reports/sales?customer_id={cust}", headers=_auth(tok))
    assert resp.status_code == 200
    row = next(r for r in resp.json()["data"] if r["order_id"] == order_id)
    assert row["invoice_number"] is not None
    assert row["invoice_status"] == "draft"


@freeze_time(_TODAY)
async def test_sales_report_customer_filter(client: AsyncClient) -> None:
    tok = await _inv_token(client, "sr3")
    med = await _create_medicine(client, tok, f"SR3{uuid.uuid4().hex[:4]}")
    wh = await _create_warehouse(client, tok, f"SR3W{uuid.uuid4().hex[:4]}")
    c1 = await _create_customer(client, tok, f"SC3A{uuid.uuid4().hex[:4]}")
    c2 = await _create_customer(client, tok, f"SC3B{uuid.uuid4().hex[:4]}")
    await _create_batch(client, tok, med, wh, batch_number="SR-C1", qty=100)
    o1 = await _place_and_dispatch_order(client, tok, c1, med, qty=2)
    await _create_batch(client, tok, med, wh, batch_number="SR-C2", qty=100)
    o2 = await _place_and_dispatch_order(client, tok, c2, med, qty=2)

    resp = await client.get(f"/api/v1/reports/sales?customer_id={c1}", headers=_auth(tok))
    assert resp.status_code == 200
    ids = [r["order_id"] for r in resp.json()["data"]]
    assert o1 in ids
    assert o2 not in ids


# ── 7. Customer report ─────────────────────────────────────────────────────────


@freeze_time(_TODAY)
async def test_customer_report_shows_all_customers(client: AsyncClient) -> None:
    tok = await _inv_token(client, "cr1")
    cust = await _create_customer(client, tok, f"CR1{uuid.uuid4().hex[:4]}")

    resp = await client.get("/api/v1/reports/customers", headers=_auth(tok))
    assert resp.status_code == 200
    ids = [r["customer_id"] for r in resp.json()["data"]]
    assert cust in ids


@freeze_time(_TODAY)
async def test_customer_report_order_totals(client: AsyncClient) -> None:
    tok = await _inv_token(client, "cr2")
    med = await _create_medicine(client, tok, f"CR2M{uuid.uuid4().hex[:4]}")
    wh = await _create_warehouse(client, tok, f"CR2W{uuid.uuid4().hex[:4]}")
    cust = await _create_customer(client, tok, f"CR2{uuid.uuid4().hex[:4]}")
    await _create_batch(client, tok, med, wh, batch_number="CR-001", qty=200)
    await _place_and_dispatch_order(client, tok, cust, med, qty=5, unit_price="100.00")
    await _create_batch(client, tok, med, wh, batch_number="CR-002", qty=200)
    await _place_and_dispatch_order(client, tok, cust, med, qty=3, unit_price="100.00")

    resp = await client.get(f"/api/v1/reports/customers?customer_id={cust}", headers=_auth(tok))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 1
    row = data[0]
    assert row["total_orders"] == 2
    assert float(row["total_order_value"]) == pytest.approx(800.0)


@freeze_time(_TODAY)
async def test_customer_report_customer_id_filter(client: AsyncClient) -> None:
    tok = await _inv_token(client, "cr3")
    c1 = await _create_customer(client, tok, f"CRF1{uuid.uuid4().hex[:4]}")
    c2 = await _create_customer(client, tok, f"CRF2{uuid.uuid4().hex[:4]}")

    resp = await client.get(f"/api/v1/reports/customers?customer_id={c1}", headers=_auth(tok))
    assert resp.status_code == 200
    ids = [r["customer_id"] for r in resp.json()["data"]]
    assert c1 in ids
    assert c2 not in ids


# ── 8. Order fulfillment report ────────────────────────────────────────────────


@freeze_time(_TODAY)
async def test_order_fulfillment_structure(client: AsyncClient) -> None:
    tok = await _inv_token(client, "of1")

    resp = await client.get("/api/v1/reports/orders/fulfillment", headers=_auth(tok))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "as_of" in data
    assert "total_orders" in data
    assert "total_value" in data
    assert "by_status" in data
    assert data["as_of"] == _TODAY


@freeze_time(_TODAY)
async def test_order_fulfillment_counts_dispatched_orders(client: AsyncClient) -> None:
    tok = await _inv_token(client, "of2")
    med = await _create_medicine(client, tok, f"OF2M{uuid.uuid4().hex[:4]}")
    wh = await _create_warehouse(client, tok, f"OF2W{uuid.uuid4().hex[:4]}")
    cust = await _create_customer(client, tok, f"OF2C{uuid.uuid4().hex[:4]}")
    await _create_batch(client, tok, med, wh, batch_number="OF-001", qty=100)
    await _place_and_dispatch_order(client, tok, cust, med, qty=5)

    resp = await client.get("/api/v1/reports/orders/fulfillment", headers=_auth(tok))
    assert resp.status_code == 200
    data = resp.json()["data"]
    dispatched = next((s for s in data["by_status"] if s["status"] == "dispatched"), None)
    assert dispatched is not None
    assert dispatched["order_count"] >= 1


@freeze_time(_TODAY)
async def test_order_fulfillment_date_filter(client: AsyncClient) -> None:
    tok = await _inv_token(client, "of3")

    # Filter to a future date range — should return 0 orders
    resp = await client.get(
        "/api/v1/reports/orders/fulfillment?date_from=2030-01-01&date_to=2030-12-31",
        headers=_auth(tok),
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total_orders"] == 0


# ── role checks ────────────────────────────────────────────────────────────────


@freeze_time(_TODAY)
async def test_inventory_manager_can_access_all_reports(client: AsyncClient) -> None:
    tok = await _inv_token(client, "role1")
    for path in [
        "/api/v1/reports/inventory/current",
        "/api/v1/reports/inventory/batches",
        "/api/v1/reports/inventory/expiry",
        "/api/v1/reports/transactions",
        "/api/v1/reports/purchases",
        "/api/v1/reports/sales",
        "/api/v1/reports/customers",
        "/api/v1/reports/orders/fulfillment",
    ]:
        r = await client.get(path, headers=_auth(tok))
        assert r.status_code == 200, f"{path} returned {r.status_code}"


@freeze_time(_TODAY)
async def test_warehouse_staff_can_access_inventory_reports(client: AsyncClient) -> None:
    tok = await _wh_token(client, "role2")
    for path in [
        "/api/v1/reports/inventory/current",
        "/api/v1/reports/inventory/batches",
        "/api/v1/reports/inventory/expiry",
        "/api/v1/reports/transactions",
    ]:
        r = await client.get(path, headers=_auth(tok))
        assert r.status_code == 200, f"{path} returned {r.status_code}"


@freeze_time(_TODAY)
async def test_warehouse_staff_denied_business_reports(client: AsyncClient) -> None:
    tok = await _wh_token(client, "role3")
    for path in [
        "/api/v1/reports/purchases",
        "/api/v1/reports/sales",
        "/api/v1/reports/customers",
        "/api/v1/reports/orders/fulfillment",
    ]:
        r = await client.get(path, headers=_auth(tok))
        assert r.status_code == 403, f"{path} returned {r.status_code}"


@freeze_time(_TODAY)
async def test_sales_rep_can_access_business_reports(client: AsyncClient) -> None:
    tok = await _sales_token(client, "role4")
    for path in [
        "/api/v1/reports/purchases",
        "/api/v1/reports/sales",
        "/api/v1/reports/customers",
        "/api/v1/reports/orders/fulfillment",
    ]:
        r = await client.get(path, headers=_auth(tok))
        assert r.status_code == 200, f"{path} returned {r.status_code}"


@freeze_time(_TODAY)
async def test_sales_rep_denied_inventory_reports(client: AsyncClient) -> None:
    tok = await _sales_token(client, "role5")
    for path in [
        "/api/v1/reports/inventory/current",
        "/api/v1/reports/inventory/batches",
        "/api/v1/reports/inventory/expiry",
        "/api/v1/reports/transactions",
    ]:
        r = await client.get(path, headers=_auth(tok))
        assert r.status_code == 403, f"{path} returned {r.status_code}"


async def test_unauthenticated_returns_401(client: AsyncClient) -> None:
    paths = [
        "/api/v1/reports/inventory/current",
        "/api/v1/reports/sales",
        "/api/v1/reports/orders/fulfillment",
    ]
    for path in paths:
        r = await client.get(path)
        assert r.status_code == 401, f"{path} returned {r.status_code}"
