"""Stage 10 — Order Management & Lifecycle tests.

Tests verify:
- Create order: auto-number, custom number, duplicate 409, totals/discount/tax
- ALLOCATION RULE: creating order leaves available stock unchanged
- Status transitions: DRAFT→PLACED, invalid transitions → 400
- Approve (PLACED→APPROVED): reserves stock via FEFO (ALLOCATION txns, available↓ reserved↑)
- Approve: insufficient stock → 400, no stock moved
- Lifecycle steps: APPROVED→ALLOCATED→PICKED→PACKED via PATCH /status
- Dispatch (PACKED→DISPATCHED): creates STOCK_OUT txns, reserved↓, allocations deleted
- Cancel from DRAFT/PLACED: no stock ops, order → CANCELLED
- Cancel from APPROVED: releases reserved stock (RELEASE txns, reserved↓ available↑)
- Cannot cancel DISPATCHED order
- Delete DRAFT order, cannot delete PLACED order
- Role checks (warehouse_staff read-only for create, can dispatch)
- Unauthenticated → 401
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import date

import pytest
from freezegun import freeze_time
from httpx import AsyncClient
from sqlalchemy import select

from app.core.db import get_session_local
from app.models.inventory_batch import InventoryBatch
from app.models.inventory_transaction import InventoryTransaction, TransactionType
from app.models.user import User, UserRole

pytestmark = pytest.mark.asyncio(loop_scope="session")

_TODAY = date(2026, 6, 11)
_FAR = date(2028, 12, 31)


# ── helpers ───────────────────────────────────────────────────────────────────


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
    return await _token_for_role(
        client, f"ord_inv_{suffix}@example.com", UserRole.INVENTORY_MANAGER
    )


async def _sales_token(client: AsyncClient, suffix: str) -> str:
    return await _token_for_role(
        client, f"ord_sales_{suffix}@example.com", UserRole.SALES_REPRESENTATIVE
    )


async def _wh_token(client: AsyncClient, suffix: str) -> str:
    return await _token_for_role(client, f"ord_wh_{suffix}@example.com", UserRole.WAREHOUSE_STAFF)


async def _create_supplier(client: AsyncClient, token: str, code: str) -> str:
    resp = await client.post(
        "/api/v1/suppliers",
        json={
            "supplier_code": code,
            "supplier_name": f"Sup {code}",
            "address": "Addr",
            "phone": "9999",
            "status": "active",
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


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


async def _create_customer(client: AsyncClient, token: str, code: str) -> str:
    resp = await client.post(
        "/api/v1/customers",
        json={
            "customer_code": code,
            "business_name": f"Biz {code}",
            "credit_limit": "10000.00",
            "status": "active",
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


async def _create_batch_with_stock(
    client: AsyncClient,
    token: str,
    medicine_id: str,
    warehouse_id: str,
    *,
    batch_number: str,
    qty: int,
    expiry: str = "2028-12-31",
) -> str:
    resp = await client.post(
        "/api/v1/inventory/batches",
        json={
            "medicine_id": medicine_id,
            "warehouse_id": warehouse_id,
            "batch_number": batch_number,
            "expiry_date": expiry,
            "initial_quantity": qty,
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


async def _create_order(
    client: AsyncClient,
    token: str,
    customer_id: str,
    medicine_id: str,
    *,
    order_number: str | None = None,
    qty: int = 10,
    unit_price: str = "100.00",
    discount: str = "0.00",
    tax_amount: str = "0.00",
) -> dict:
    body: dict = {
        "customer_id": customer_id,
        "order_date": str(_TODAY),
        "items": [
            {
                "medicine_id": medicine_id,
                "quantity": qty,
                "unit_price": unit_price,
                "discount": discount,
                "tax_amount": tax_amount,
            }
        ],
    }
    if order_number:
        body["order_number"] = order_number
    return await client.post("/api/v1/orders", json=body, headers=_auth(token))


async def _transition(client: AsyncClient, token: str, order_id: str, new_status: str) -> dict:
    return await client.patch(
        f"/api/v1/orders/{order_id}/status",
        json={"status": new_status},
        headers=_auth(token),
    )


# ── create ─────────────────────────────────────────────────────────────────────


@freeze_time("2026-06-11")
async def test_create_order_auto_number(client: AsyncClient):
    token = await _inv_token(client, "cr_auto")
    cid = await _create_customer(client, token, "ORD-CUST-A1")
    mid = await _create_medicine(client, token, "ORD-MED-A1")
    resp = await _create_order(client, token, cid, mid)
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["status"] == "draft"
    assert data["order_number"].startswith("ORD-")
    assert len(data["items"]) == 1
    assert data["total_amount"] == "1000.00"


@freeze_time("2026-06-11")
async def test_create_order_totals_with_discount_and_tax(client: AsyncClient):
    token = await _inv_token(client, "cr_totals")
    cid = await _create_customer(client, token, "ORD-CUST-TOT1")
    mid = await _create_medicine(client, token, "ORD-MED-TOT1")
    # line_total = 100 * 5 - 50 + 25 = 475
    resp = await _create_order(
        client,
        token,
        cid,
        mid,
        qty=5,
        unit_price="100.00",
        discount="50.00",
        tax_amount="25.00",
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["items"][0]["line_total"] == "475.00"
    assert data["total_amount"] == "475.00"


@freeze_time("2026-06-11")
async def test_create_order_duplicate_number_409(client: AsyncClient):
    token = await _inv_token(client, "cr_dup")
    cid = await _create_customer(client, token, "ORD-CUST-DUP1")
    mid = await _create_medicine(client, token, "ORD-MED-DUP1")
    r1 = await _create_order(client, token, cid, mid, order_number="ORD-DUP-001")
    assert r1.status_code == 201
    r2 = await _create_order(client, token, cid, mid, order_number="ORD-DUP-001")
    assert r2.status_code == 409


@freeze_time("2026-06-11")
async def test_create_order_empty_items_422(client: AsyncClient):
    token = await _inv_token(client, "cr_empty")
    cid = await _create_customer(client, token, "ORD-CUST-EMP1")
    resp = await client.post(
        "/api/v1/orders",
        json={"customer_id": cid, "order_date": str(_TODAY), "items": []},
        headers=_auth(token),
    )
    assert resp.status_code == 422


# ── allocation rule: create does NOT touch stock ────────────────────────────────


@freeze_time("2026-06-11")
async def test_create_order_does_not_reduce_stock(client: AsyncClient):
    token = await _inv_token(client, "alloc_rule")
    cid = await _create_customer(client, token, "ORD-CUST-AR1")
    mid = await _create_medicine(client, token, "ORD-MED-AR1")
    wid = await _create_warehouse(client, token, "ORD-WH-AR1")
    bid = await _create_batch_with_stock(client, token, mid, wid, batch_number="AR-B1", qty=50)

    await _create_order(client, token, cid, mid, qty=30)

    async with get_session_local()() as session:
        batch = await session.get(InventoryBatch, bid)
        assert batch.quantity_available == 50  # unchanged
        assert batch.quantity_reserved == 0


# ── status transitions ─────────────────────────────────────────────────────────


@freeze_time("2026-06-11")
async def test_draft_to_placed(client: AsyncClient):
    token = await _inv_token(client, "trans_placed")
    cid = await _create_customer(client, token, "ORD-CUST-TP1")
    mid = await _create_medicine(client, token, "ORD-MED-TP1")
    resp = await _create_order(client, token, cid, mid)
    oid = resp.json()["data"]["id"]
    tr = await _transition(client, token, oid, "placed")
    assert tr.status_code == 200
    assert tr.json()["data"]["status"] == "placed"


@freeze_time("2026-06-11")
async def test_invalid_transition_rejected(client: AsyncClient):
    token = await _inv_token(client, "trans_inv")
    cid = await _create_customer(client, token, "ORD-CUST-TI1")
    mid = await _create_medicine(client, token, "ORD-MED-TI1")
    resp = await _create_order(client, token, cid, mid)
    oid = resp.json()["data"]["id"]
    # DRAFT → APPROVED is invalid (must go via /approve)
    tr = await _transition(client, token, oid, "approved")
    assert tr.status_code == 400


@freeze_time("2026-06-11")
async def test_cannot_patch_to_approved_directly(client: AsyncClient):
    """PLACED→APPROVED must use /approve, not PATCH /status."""
    token = await _inv_token(client, "trans_noapp")
    cid = await _create_customer(client, token, "ORD-CUST-TNA1")
    mid = await _create_medicine(client, token, "ORD-MED-TNA1")
    wid = await _create_warehouse(client, token, "ORD-WH-TNA1")
    await _create_batch_with_stock(client, token, mid, wid, batch_number="TNA-B1", qty=50)
    resp = await _create_order(client, token, cid, mid, qty=10)
    oid = resp.json()["data"]["id"]
    await _transition(client, token, oid, "placed")
    # Try to patch directly to approved — should fail
    tr = await _transition(client, token, oid, "approved")
    assert tr.status_code == 400


# ── approve: PLACED→APPROVED + FEFO stock reservation ─────────────────────────


@freeze_time("2026-06-11")
async def test_approve_reserves_stock(client: AsyncClient):
    token = await _inv_token(client, "approve_res")
    cid = await _create_customer(client, token, "ORD-CUST-APR1")
    mid = await _create_medicine(client, token, "ORD-MED-APR1")
    wid = await _create_warehouse(client, token, "ORD-WH-APR1")
    bid = await _create_batch_with_stock(client, token, mid, wid, batch_number="APR-B1", qty=100)

    resp = await _create_order(client, token, cid, mid, qty=30)
    oid = resp.json()["data"]["id"]
    await _transition(client, token, oid, "placed")

    approve_resp = await client.post(f"/api/v1/orders/{oid}/approve", headers=_auth(token))
    assert approve_resp.status_code == 200, approve_resp.text
    assert approve_resp.json()["data"]["status"] == "approved"

    async with get_session_local()() as session:
        batch = await session.get(InventoryBatch, bid)
        assert batch.quantity_available == 70  # 100 - 30
        assert batch.quantity_reserved == 30  # reserved

        txns = await session.execute(
            select(InventoryTransaction).where(
                InventoryTransaction.batch_id == bid,
                InventoryTransaction.transaction_type == TransactionType.ALLOCATION,
            )
        )
        allocs = txns.scalars().all()
        assert len(allocs) == 1
        assert allocs[0].quantity == 30


@freeze_time("2026-06-11")
async def test_approve_insufficient_stock_400(client: AsyncClient):
    token = await _inv_token(client, "approve_insuf")
    cid = await _create_customer(client, token, "ORD-CUST-INS1")
    mid = await _create_medicine(client, token, "ORD-MED-INS1")
    wid = await _create_warehouse(client, token, "ORD-WH-INS1")
    bid = await _create_batch_with_stock(client, token, mid, wid, batch_number="INS-B1", qty=5)

    resp = await _create_order(client, token, cid, mid, qty=50)
    oid = resp.json()["data"]["id"]
    await _transition(client, token, oid, "placed")

    approve_resp = await client.post(f"/api/v1/orders/{oid}/approve", headers=_auth(token))
    assert approve_resp.status_code == 400

    # Stock must be unchanged
    async with get_session_local()() as session:
        batch = await session.get(InventoryBatch, bid)
        assert batch.quantity_available == 5
        assert batch.quantity_reserved == 0


@freeze_time("2026-06-11")
async def test_approve_requires_placed_status(client: AsyncClient):
    token = await _inv_token(client, "approve_notplaced")
    cid = await _create_customer(client, token, "ORD-CUST-ANP1")
    mid = await _create_medicine(client, token, "ORD-MED-ANP1")
    resp = await _create_order(client, token, cid, mid)
    oid = resp.json()["data"]["id"]
    # Approve directly from DRAFT — should fail
    resp = await client.post(f"/api/v1/orders/{oid}/approve", headers=_auth(token))
    assert resp.status_code == 400


# ── full lifecycle: approve → allocated → picked → packed → dispatch ──────────


@freeze_time("2026-06-11")
async def test_full_lifecycle_dispatch_creates_stock_out(client: AsyncClient):
    token = await _inv_token(client, "lifecycle")
    cid = await _create_customer(client, token, "ORD-CUST-LC1")
    mid = await _create_medicine(client, token, "ORD-MED-LC1")
    wid = await _create_warehouse(client, token, "ORD-WH-LC1")
    bid = await _create_batch_with_stock(client, token, mid, wid, batch_number="LC-B1", qty=100)

    resp = await _create_order(client, token, cid, mid, qty=20)
    oid = resp.json()["data"]["id"]

    await _transition(client, token, oid, "placed")
    await client.post(f"/api/v1/orders/{oid}/approve", headers=_auth(token))
    await _transition(client, token, oid, "allocated")
    await _transition(client, token, oid, "picked")
    await _transition(client, token, oid, "packed")

    dispatch_resp = await client.post(f"/api/v1/orders/{oid}/dispatch", headers=_auth(token))
    assert dispatch_resp.status_code == 200, dispatch_resp.text
    assert dispatch_resp.json()["data"]["status"] == "dispatched"

    async with get_session_local()() as session:
        batch = await session.get(InventoryBatch, bid)
        assert batch.quantity_available == 80  # 100 - 20
        assert batch.quantity_reserved == 0  # cleared

        txns = await session.execute(
            select(InventoryTransaction).where(
                InventoryTransaction.batch_id == bid,
                InventoryTransaction.transaction_type == TransactionType.STOCK_OUT,
            )
        )
        stock_outs = txns.scalars().all()
        assert len(stock_outs) == 1
        assert stock_outs[0].quantity == 20


@freeze_time("2026-06-11")
async def test_dispatch_requires_packed_status(client: AsyncClient):
    token = await _inv_token(client, "dispatch_notpacked")
    cid = await _create_customer(client, token, "ORD-CUST-DNP1")
    mid = await _create_medicine(client, token, "ORD-MED-DNP1")
    wid = await _create_warehouse(client, token, "ORD-WH-DNP1")
    await _create_batch_with_stock(client, token, mid, wid, batch_number="DNP-B1", qty=50)
    resp = await _create_order(client, token, cid, mid, qty=10)
    oid = resp.json()["data"]["id"]
    await _transition(client, token, oid, "placed")
    await client.post(f"/api/v1/orders/{oid}/approve", headers=_auth(token))
    # Try to dispatch from APPROVED (not PACKED) — should fail
    resp = await client.post(f"/api/v1/orders/{oid}/dispatch", headers=_auth(token))
    assert resp.status_code == 400


# ── cancel ─────────────────────────────────────────────────────────────────────


@freeze_time("2026-06-11")
async def test_cancel_draft_order(client: AsyncClient):
    token = await _inv_token(client, "cancel_draft")
    cid = await _create_customer(client, token, "ORD-CUST-CD1")
    mid = await _create_medicine(client, token, "ORD-MED-CD1")
    resp = await _create_order(client, token, cid, mid)
    oid = resp.json()["data"]["id"]
    cancel_resp = await client.post(f"/api/v1/orders/{oid}/cancel", headers=_auth(token))
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["data"]["status"] == "cancelled"


@freeze_time("2026-06-11")
async def test_cancel_approved_order_releases_stock(client: AsyncClient):
    token = await _inv_token(client, "cancel_approved")
    cid = await _create_customer(client, token, "ORD-CUST-CA1")
    mid = await _create_medicine(client, token, "ORD-MED-CA1")
    wid = await _create_warehouse(client, token, "ORD-WH-CA1")
    bid = await _create_batch_with_stock(client, token, mid, wid, batch_number="CA-B1", qty=100)

    resp = await _create_order(client, token, cid, mid, qty=40)
    oid = resp.json()["data"]["id"]
    await _transition(client, token, oid, "placed")
    await client.post(f"/api/v1/orders/{oid}/approve", headers=_auth(token))

    # Confirm stock was reserved
    async with get_session_local()() as session:
        batch = await session.get(InventoryBatch, bid)
        assert batch.quantity_reserved == 40

    cancel_resp = await client.post(f"/api/v1/orders/{oid}/cancel", headers=_auth(token))
    assert cancel_resp.status_code == 200
    assert cancel_resp.json()["data"]["status"] == "cancelled"

    async with get_session_local()() as session:
        batch = await session.get(InventoryBatch, bid)
        assert batch.quantity_available == 100  # fully restored
        assert batch.quantity_reserved == 0

        txns = await session.execute(
            select(InventoryTransaction).where(
                InventoryTransaction.batch_id == bid,
                InventoryTransaction.transaction_type == TransactionType.RELEASE,
            )
        )
        releases = txns.scalars().all()
        assert len(releases) == 1
        assert releases[0].quantity == 40


@freeze_time("2026-06-11")
async def test_cannot_cancel_dispatched_order(client: AsyncClient):
    token = await _inv_token(client, "cancel_dispatched")
    cid = await _create_customer(client, token, "ORD-CUST-CND1")
    mid = await _create_medicine(client, token, "ORD-MED-CND1")
    wid = await _create_warehouse(client, token, "ORD-WH-CND1")
    await _create_batch_with_stock(client, token, mid, wid, batch_number="CND-B1", qty=50)
    resp = await _create_order(client, token, cid, mid, qty=10)
    oid = resp.json()["data"]["id"]
    await _transition(client, token, oid, "placed")
    await client.post(f"/api/v1/orders/{oid}/approve", headers=_auth(token))
    await _transition(client, token, oid, "allocated")
    await _transition(client, token, oid, "picked")
    await _transition(client, token, oid, "packed")
    await client.post(f"/api/v1/orders/{oid}/dispatch", headers=_auth(token))
    cancel_resp = await client.post(f"/api/v1/orders/{oid}/cancel", headers=_auth(token))
    assert cancel_resp.status_code == 400


# ── delete ─────────────────────────────────────────────────────────────────────


@freeze_time("2026-06-11")
async def test_delete_draft_order(client: AsyncClient):
    token = await _inv_token(client, "del_draft")
    cid = await _create_customer(client, token, "ORD-CUST-DD1")
    mid = await _create_medicine(client, token, "ORD-MED-DD1")
    resp = await _create_order(client, token, cid, mid)
    oid = resp.json()["data"]["id"]
    del_resp = await client.delete(f"/api/v1/orders/{oid}", headers=_auth(token))
    assert del_resp.status_code == 200
    get_resp = await client.get(f"/api/v1/orders/{oid}", headers=_auth(token))
    assert get_resp.status_code == 404


@freeze_time("2026-06-11")
async def test_cannot_delete_placed_order(client: AsyncClient):
    token = await _inv_token(client, "del_placed")
    cid = await _create_customer(client, token, "ORD-CUST-DP1")
    mid = await _create_medicine(client, token, "ORD-MED-DP1")
    resp = await _create_order(client, token, cid, mid)
    oid = resp.json()["data"]["id"]
    await _transition(client, token, oid, "placed")
    del_resp = await client.delete(f"/api/v1/orders/{oid}", headers=_auth(token))
    assert del_resp.status_code == 400


# ── list / get ─────────────────────────────────────────────────────────────────


@freeze_time("2026-06-11")
async def test_list_orders(client: AsyncClient):
    token = await _inv_token(client, "list")
    cid = await _create_customer(client, token, "ORD-CUST-LST1")
    mid = await _create_medicine(client, token, "ORD-MED-LST1")
    resp = await _create_order(client, token, cid, mid, order_number="ORD-LIST-001")
    assert resp.status_code == 201
    list_resp = await client.get("/api/v1/orders", headers=_auth(token))
    assert list_resp.status_code == 200
    nums = [o["order_number"] for o in list_resp.json()["data"]]
    assert "ORD-LIST-001" in nums


async def test_get_nonexistent_order_404(client: AsyncClient):
    token = await _inv_token(client, "get404")
    resp = await client.get(f"/api/v1/orders/{uuid.uuid4()}", headers=_auth(token))
    assert resp.status_code == 404


# ── role checks ────────────────────────────────────────────────────────────────


@freeze_time("2026-06-11")
async def test_warehouse_staff_cannot_create_order(client: AsyncClient):
    wh_token = await _wh_token(client, "cr_block")
    inv_token = await _inv_token(client, "cr_block")
    cid = await _create_customer(client, inv_token, "ORD-CUST-WCR1")
    mid = await _create_medicine(client, inv_token, "ORD-MED-WCR1")
    resp = await _create_order(client, wh_token, cid, mid)
    assert resp.status_code == 403


@freeze_time("2026-06-11")
async def test_warehouse_staff_can_dispatch(client: AsyncClient):
    inv_token = await _inv_token(client, "wh_dispatch")
    wh_token = await _wh_token(client, "wh_dispatch")
    cid = await _create_customer(client, inv_token, "ORD-CUST-WHD1")
    mid = await _create_medicine(client, inv_token, "ORD-MED-WHD1")
    wid = await _create_warehouse(client, inv_token, "ORD-WH-WHD1")
    await _create_batch_with_stock(client, inv_token, mid, wid, batch_number="WHD-B1", qty=50)
    resp = await _create_order(client, inv_token, cid, mid, qty=10)
    oid = resp.json()["data"]["id"]
    await _transition(client, inv_token, oid, "placed")
    await client.post(f"/api/v1/orders/{oid}/approve", headers=_auth(inv_token))
    await _transition(client, inv_token, oid, "allocated")
    await _transition(client, inv_token, oid, "picked")
    await _transition(client, inv_token, oid, "packed")
    dispatch_resp = await client.post(f"/api/v1/orders/{oid}/dispatch", headers=_auth(wh_token))
    assert dispatch_resp.status_code == 200


@freeze_time("2026-06-11")
async def test_sales_rep_cannot_approve_order(client: AsyncClient):
    inv_token = await _inv_token(client, "sales_approve")
    sales_token = await _sales_token(client, "sales_approve")
    cid = await _create_customer(client, inv_token, "ORD-CUST-SA1")
    mid = await _create_medicine(client, inv_token, "ORD-MED-SA1")
    wid = await _create_warehouse(client, inv_token, "ORD-WH-SA1")
    await _create_batch_with_stock(client, inv_token, mid, wid, batch_number="SA-B1", qty=50)
    resp = await _create_order(client, sales_token, cid, mid, qty=10)
    oid = resp.json()["data"]["id"]
    await _transition(client, sales_token, oid, "placed")
    approve_resp = await client.post(f"/api/v1/orders/{oid}/approve", headers=_auth(sales_token))
    assert approve_resp.status_code == 403


async def test_unauthenticated_cannot_create_order(client: AsyncClient):
    resp = await client.post(
        "/api/v1/orders",
        json={
            "customer_id": str(uuid.uuid4()),
            "order_date": str(_TODAY),
            "items": [
                {
                    "medicine_id": str(uuid.uuid4()),
                    "quantity": 1,
                    "unit_price": "10.00",
                }
            ],
        },
    )
    assert resp.status_code == 401


async def test_unauthenticated_cannot_list_orders(client: AsyncClient):
    resp = await client.get("/api/v1/orders")
    assert resp.status_code == 401


# ── concurrent approval ────────────────────────────────────────────────────────


@freeze_time("2026-06-11")
async def test_concurrent_approval_only_one_wins(client: AsyncClient):
    """Two orders competing for the same last 10 units — only one can be approved."""
    token = await _inv_token(client, "concurrent")
    cid = await _create_customer(client, token, "ORD-CUST-CONC1")
    mid = await _create_medicine(client, token, "ORD-MED-CONC1")
    wid = await _create_warehouse(client, token, "ORD-WH-CONC1")
    await _create_batch_with_stock(client, token, mid, wid, batch_number="CONC-B1", qty=10)

    r1 = await _create_order(client, token, cid, mid, qty=10)
    r2 = await _create_order(client, token, cid, mid, qty=10)
    oid1 = r1.json()["data"]["id"]
    oid2 = r2.json()["data"]["id"]
    await _transition(client, token, oid1, "placed")
    await _transition(client, token, oid2, "placed")

    async def approve_one(oid: str) -> int:
        resp = await client.post(f"/api/v1/orders/{oid}/approve", headers=_auth(token))
        return resp.status_code

    codes = await asyncio.gather(approve_one(oid1), approve_one(oid2))
    assert sorted(codes) == [200, 400]
