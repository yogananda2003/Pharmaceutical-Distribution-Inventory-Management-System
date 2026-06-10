"""Stage 6 — Inventory Batch & Transaction tests.

Five inventory rules verified explicitly:
1. Quantity cannot become negative.
2. Expired inventory cannot be sold/allocated.
3. Every movement creates a transaction record.
4. Updates occur within DB transactions (verified via atomicity of operations).
5. Transactions are never deleted (no DELETE endpoint exists).
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import date, timedelta

import pytest
from freezegun import freeze_time
from httpx import AsyncClient
from sqlalchemy import select

from app.core.db import get_session_local
from app.models.user import User, UserRole

pytestmark = pytest.mark.asyncio(loop_scope="session")


# ── date helpers ──────────────────────────────────────────────────────────────

_TODAY = date(2026, 6, 10)
_TOMORROW = _TODAY + timedelta(days=1)
_YESTERDAY = _TODAY - timedelta(days=1)
_FAR_FUTURE = date(2028, 12, 31)


# ── shared test fixtures / helpers ────────────────────────────────────────────


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


async def _create_medicine(client: AsyncClient, token: str, code: str) -> str:
    resp = await client.post(
        "/api/v1/medicines",
        json={
            "code": code,
            "name": f"Medicine {code}",
            "generic_name": "Generic",
            "manufacturer": "MfgCo",
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
    batch_number: str = "BATCH-001",
    expiry_date: str = str(_FAR_FUTURE),
    initial_quantity: int = 0,
) -> dict:
    resp = await client.post(
        "/api/v1/inventory/batches",
        json={
            "medicine_id": medicine_id,
            "warehouse_id": warehouse_id,
            "batch_number": batch_number,
            "expiry_date": expiry_date,
            "initial_quantity": initial_quantity,
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


async def _inv_token(client: AsyncClient, suffix: str) -> str:
    return await _token_for_role(client, f"inv_{suffix}@example.com", UserRole.INVENTORY_MANAGER)


# ── create batch ──────────────────────────────────────────────────────────────


async def test_create_batch_no_initial_quantity(client: AsyncClient):
    token = await _inv_token(client, "create_no_qty")
    mid = await _create_medicine(client, token, "INV-MED-C1")
    wid = await _create_warehouse(client, token, "INV-WH-C1")
    batch = await _create_batch(client, token, mid, wid, batch_number="BATCH-C1")
    assert batch["quantity_available"] == 0
    assert batch["status"] == "active"


async def test_create_batch_with_initial_quantity_creates_stock_in(client: AsyncClient):
    """Rule 3: initial_quantity > 0 must create a STOCK_IN transaction."""
    token = await _inv_token(client, "create_with_qty")
    mid = await _create_medicine(client, token, "INV-MED-C2")
    wid = await _create_warehouse(client, token, "INV-WH-C2")
    batch = await _create_batch(
        client, token, mid, wid, batch_number="BATCH-C2", initial_quantity=50
    )
    assert batch["quantity_available"] == 50

    txn_resp = await client.get(
        f"/api/v1/inventory/batches/{batch['id']}/transactions",
        headers=_auth(token),
    )
    assert txn_resp.status_code == 200
    txns = txn_resp.json()["data"]
    assert len(txns) == 1
    assert txns[0]["transaction_type"] == "stock_in"
    assert txns[0]["quantity"] == 50


async def test_batch_number_uppercased(client: AsyncClient):
    token = await _inv_token(client, "create_upper")
    mid = await _create_medicine(client, token, "INV-MED-C3")
    wid = await _create_warehouse(client, token, "INV-WH-C3")
    resp = await client.post(
        "/api/v1/inventory/batches",
        json={
            "medicine_id": mid,
            "warehouse_id": wid,
            "batch_number": "batch-lower",
            "expiry_date": str(_FAR_FUTURE),
            "initial_quantity": 0,
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201
    assert resp.json()["data"]["batch_number"] == "BATCH-LOWER"


async def test_duplicate_batch_rejected(client: AsyncClient):
    token = await _inv_token(client, "create_dup")
    mid = await _create_medicine(client, token, "INV-MED-C4")
    wid = await _create_warehouse(client, token, "INV-WH-C4")
    await _create_batch(client, token, mid, wid, batch_number="BATCH-DUP")
    resp = await client.post(
        "/api/v1/inventory/batches",
        json={
            "medicine_id": mid,
            "warehouse_id": wid,
            "batch_number": "BATCH-DUP",
            "expiry_date": str(_FAR_FUTURE),
        },
        headers=_auth(token),
    )
    assert resp.status_code == 409


async def test_customer_cannot_create_batch(client: AsyncClient):
    token = await _token_for_role(client, "cust_inv_c@example.com", UserRole.CUSTOMER)
    resp = await client.post(
        "/api/v1/inventory/batches",
        json={
            "medicine_id": str(uuid.uuid4()),
            "warehouse_id": str(uuid.uuid4()),
            "batch_number": "BATCH-NOPE",
            "expiry_date": str(_FAR_FUTURE),
        },
        headers=_auth(token),
    )
    assert resp.status_code == 403


# ── read ──────────────────────────────────────────────────────────────────────


async def test_list_batches(client: AsyncClient):
    token = await _inv_token(client, "list_batches")
    resp = await client.get("/api/v1/inventory/batches", headers=_auth(token))
    assert resp.status_code == 200
    assert isinstance(resp.json()["data"], list)


async def test_get_batch_by_id(client: AsyncClient):
    token = await _inv_token(client, "get_by_id")
    mid = await _create_medicine(client, token, "INV-MED-R1")
    wid = await _create_warehouse(client, token, "INV-WH-R1")
    batch = await _create_batch(client, token, mid, wid, batch_number="BATCH-R1")
    resp = await client.get(f"/api/v1/inventory/batches/{batch['id']}", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["data"]["id"] == batch["id"]


async def test_get_batch_404(client: AsyncClient):
    token = await _inv_token(client, "get_404")
    resp = await client.get(f"/api/v1/inventory/batches/{uuid.uuid4()}", headers=_auth(token))
    assert resp.status_code == 404


async def test_sales_rep_can_list_batches(client: AsyncClient):
    token = await _token_for_role(
        client, "sales_inv_list@example.com", UserRole.SALES_REPRESENTATIVE
    )
    resp = await client.get("/api/v1/inventory/batches", headers=_auth(token))
    assert resp.status_code == 200


async def test_customer_cannot_list_batches(client: AsyncClient):
    token = await _token_for_role(client, "cust_inv_list@example.com", UserRole.CUSTOMER)
    resp = await client.get("/api/v1/inventory/batches", headers=_auth(token))
    assert resp.status_code == 403


# ── Rule 1: quantity cannot become negative ───────────────────────────────────


async def test_adjust_negative_beyond_available_rejected(client: AsyncClient):
    """Rule 1: quantity_available cannot go below zero."""
    token = await _inv_token(client, "rule1_adj")
    mid = await _create_medicine(client, token, "INV-MED-R1A")
    wid = await _create_warehouse(client, token, "INV-WH-R1A")
    batch = await _create_batch(
        client, token, mid, wid, batch_number="RULE1-ADJ", initial_quantity=10
    )
    resp = await client.post(
        f"/api/v1/inventory/batches/{batch['id']}/adjust",
        json={"quantity_delta": -11},
        headers=_auth(token),
    )
    assert resp.status_code == 400
    assert "negative" in resp.json()["message"].lower()


async def test_damage_more_than_available_rejected(client: AsyncClient):
    """Rule 1: cannot mark more as damaged than is available."""
    token = await _inv_token(client, "rule1_dmg")
    mid = await _create_medicine(client, token, "INV-MED-R1B")
    wid = await _create_warehouse(client, token, "INV-WH-R1B")
    batch = await _create_batch(
        client, token, mid, wid, batch_number="RULE1-DMG", initial_quantity=5
    )
    resp = await client.post(
        f"/api/v1/inventory/batches/{batch['id']}/damage",
        json={"quantity": 10},
        headers=_auth(token),
    )
    assert resp.status_code == 400


async def test_allocate_more_than_available_rejected(client: AsyncClient):
    """Rule 1: cannot allocate more than is available."""
    token = await _inv_token(client, "rule1_alloc")
    mid = await _create_medicine(client, token, "INV-MED-R1C")
    wid = await _create_warehouse(client, token, "INV-WH-R1C")
    batch = await _create_batch(
        client, token, mid, wid, batch_number="RULE1-ALLOC", initial_quantity=3
    )
    resp = await client.post(
        f"/api/v1/inventory/batches/{batch['id']}/allocate",
        json={"quantity": 4},
        headers=_auth(token),
    )
    assert resp.status_code == 400


async def test_stock_out_more_than_reserved_rejected(client: AsyncClient):
    """Rule 1: cannot stock-out more than is reserved."""
    token = await _inv_token(client, "rule1_sout")
    mid = await _create_medicine(client, token, "INV-MED-R1D")
    wid = await _create_warehouse(client, token, "INV-WH-R1D")
    batch = await _create_batch(
        client, token, mid, wid, batch_number="RULE1-SOUT", initial_quantity=10
    )
    # Allocate 3 first
    await client.post(
        f"/api/v1/inventory/batches/{batch['id']}/allocate",
        json={"quantity": 3},
        headers=_auth(token),
    )
    resp = await client.post(
        f"/api/v1/inventory/batches/{batch['id']}/stock-out",
        json={"quantity": 5},
        headers=_auth(token),
    )
    assert resp.status_code == 400


async def test_release_more_than_reserved_rejected(client: AsyncClient):
    """Rule 1: cannot release more than is reserved."""
    token = await _inv_token(client, "rule1_rel")
    mid = await _create_medicine(client, token, "INV-MED-R1E")
    wid = await _create_warehouse(client, token, "INV-WH-R1E")
    batch = await _create_batch(
        client, token, mid, wid, batch_number="RULE1-REL", initial_quantity=10
    )
    resp = await client.post(
        f"/api/v1/inventory/batches/{batch['id']}/release",
        json={"quantity": 1},
        headers=_auth(token),
    )
    assert resp.status_code == 400


# ── Rule 2: expired inventory cannot be sold ──────────────────────────────────


@freeze_time("2026-06-10")
async def test_allocate_expired_batch_rejected(client: AsyncClient):
    """Rule 2: batch expiring before today cannot be allocated."""
    token = await _inv_token(client, "rule2_expired")
    mid = await _create_medicine(client, token, "INV-MED-R2A")
    wid = await _create_warehouse(client, token, "INV-WH-R2A")
    yesterday = str(_YESTERDAY)
    batch = await _create_batch(
        client,
        token,
        mid,
        wid,
        batch_number="RULE2-EXP",
        expiry_date=yesterday,
        initial_quantity=100,
    )
    resp = await client.post(
        f"/api/v1/inventory/batches/{batch['id']}/allocate",
        json={"quantity": 1},
        headers=_auth(token),
    )
    assert resp.status_code == 400
    assert "expired" in resp.json()["message"].lower()


@freeze_time("2026-06-10")
async def test_allocate_batch_expiring_today_allowed(client: AsyncClient):
    """Rule 2 boundary: expiry_date == today is still valid (last day of validity)."""
    token = await _inv_token(client, "rule2_today")
    mid = await _create_medicine(client, token, "INV-MED-R2B")
    wid = await _create_warehouse(client, token, "INV-WH-R2B")
    batch = await _create_batch(
        client,
        token,
        mid,
        wid,
        batch_number="RULE2-TODAY",
        expiry_date=str(_TODAY),
        initial_quantity=10,
    )
    resp = await client.post(
        f"/api/v1/inventory/batches/{batch['id']}/allocate",
        json={"quantity": 1},
        headers=_auth(token),
    )
    assert resp.status_code == 200


@freeze_time("2026-06-10")
async def test_stock_in_on_expired_batch_allowed(client: AsyncClient):
    """Rule 2 applies only to sales/allocation — receiving goods is unrestricted."""
    token = await _inv_token(client, "rule2_sin_exp")
    mid = await _create_medicine(client, token, "INV-MED-R2C")
    wid = await _create_warehouse(client, token, "INV-WH-R2C")
    batch = await _create_batch(
        client,
        token,
        mid,
        wid,
        batch_number="RULE2-SIN",
        expiry_date=str(_YESTERDAY),
    )
    resp = await client.post(
        f"/api/v1/inventory/batches/{batch['id']}/stock-in",
        json={"quantity": 5, "remarks": "Returned stock"},
        headers=_auth(token),
    )
    assert resp.status_code == 200


# ── Rule 3: every movement creates a transaction ──────────────────────────────


async def test_stock_in_creates_transaction(client: AsyncClient):
    """Rule 3: stock-in endpoint creates a STOCK_IN transaction."""
    token = await _inv_token(client, "rule3_sin")
    mid = await _create_medicine(client, token, "INV-MED-R3A")
    wid = await _create_warehouse(client, token, "INV-WH-R3A")
    batch = await _create_batch(client, token, mid, wid, batch_number="RULE3-SIN")
    await client.post(
        f"/api/v1/inventory/batches/{batch['id']}/stock-in",
        json={"quantity": 20, "reference_number": "PO-001"},
        headers=_auth(token),
    )
    txn_resp = await client.get(
        f"/api/v1/inventory/batches/{batch['id']}/transactions",
        headers=_auth(token),
    )
    txns = txn_resp.json()["data"]
    assert any(t["transaction_type"] == "stock_in" and t["quantity"] == 20 for t in txns)


async def test_adjust_creates_transaction(client: AsyncClient):
    """Rule 3: adjust creates an ADJUSTMENT transaction."""
    token = await _inv_token(client, "rule3_adj")
    mid = await _create_medicine(client, token, "INV-MED-R3B")
    wid = await _create_warehouse(client, token, "INV-WH-R3B")
    batch = await _create_batch(
        client, token, mid, wid, batch_number="RULE3-ADJ", initial_quantity=50
    )
    await client.post(
        f"/api/v1/inventory/batches/{batch['id']}/adjust",
        json={"quantity_delta": -5, "remarks": "Physical count discrepancy"},
        headers=_auth(token),
    )
    txn_resp = await client.get(
        f"/api/v1/inventory/batches/{batch['id']}/transactions",
        headers=_auth(token),
    )
    txns = txn_resp.json()["data"]
    assert any(t["transaction_type"] == "adjustment" and t["quantity"] == -5 for t in txns)


async def test_damage_creates_transaction(client: AsyncClient):
    """Rule 3: damage creates a DAMAGE transaction."""
    token = await _inv_token(client, "rule3_dmg")
    mid = await _create_medicine(client, token, "INV-MED-R3C")
    wid = await _create_warehouse(client, token, "INV-WH-R3C")
    batch = await _create_batch(
        client, token, mid, wid, batch_number="RULE3-DMG", initial_quantity=20
    )
    await client.post(
        f"/api/v1/inventory/batches/{batch['id']}/damage",
        json={"quantity": 2},
        headers=_auth(token),
    )
    txn_resp = await client.get(
        f"/api/v1/inventory/batches/{batch['id']}/transactions",
        headers=_auth(token),
    )
    txns = txn_resp.json()["data"]
    assert any(t["transaction_type"] == "damage" and t["quantity"] == 2 for t in txns)


async def test_allocate_creates_transaction(client: AsyncClient):
    """Rule 3: allocation creates an ALLOCATION transaction."""
    token = await _inv_token(client, "rule3_alloc")
    mid = await _create_medicine(client, token, "INV-MED-R3D")
    wid = await _create_warehouse(client, token, "INV-WH-R3D")
    batch = await _create_batch(
        client, token, mid, wid, batch_number="RULE3-ALLOC", initial_quantity=30
    )
    await client.post(
        f"/api/v1/inventory/batches/{batch['id']}/allocate",
        json={"quantity": 10, "reference_number": "ORD-001"},
        headers=_auth(token),
    )
    txn_resp = await client.get(
        f"/api/v1/inventory/batches/{batch['id']}/transactions",
        headers=_auth(token),
    )
    txns = txn_resp.json()["data"]
    assert any(t["transaction_type"] == "allocation" and t["quantity"] == 10 for t in txns)


async def test_release_creates_transaction(client: AsyncClient):
    """Rule 3: release creates a RELEASE transaction."""
    token = await _inv_token(client, "rule3_rel")
    mid = await _create_medicine(client, token, "INV-MED-R3E")
    wid = await _create_warehouse(client, token, "INV-WH-R3E")
    batch = await _create_batch(
        client, token, mid, wid, batch_number="RULE3-REL", initial_quantity=30
    )
    await client.post(
        f"/api/v1/inventory/batches/{batch['id']}/allocate",
        json={"quantity": 5},
        headers=_auth(token),
    )
    await client.post(
        f"/api/v1/inventory/batches/{batch['id']}/release",
        json={"quantity": 5},
        headers=_auth(token),
    )
    txn_resp = await client.get(
        f"/api/v1/inventory/batches/{batch['id']}/transactions",
        headers=_auth(token),
    )
    txns = txn_resp.json()["data"]
    assert any(t["transaction_type"] == "release" and t["quantity"] == 5 for t in txns)


async def test_stock_out_creates_transaction(client: AsyncClient):
    """Rule 3: stock-out creates a STOCK_OUT transaction."""
    token = await _inv_token(client, "rule3_sout")
    mid = await _create_medicine(client, token, "INV-MED-R3F")
    wid = await _create_warehouse(client, token, "INV-WH-R3F")
    batch = await _create_batch(
        client, token, mid, wid, batch_number="RULE3-SOUT", initial_quantity=20
    )
    await client.post(
        f"/api/v1/inventory/batches/{batch['id']}/allocate",
        json={"quantity": 10},
        headers=_auth(token),
    )
    await client.post(
        f"/api/v1/inventory/batches/{batch['id']}/stock-out",
        json={"quantity": 10, "reference_number": "DISPATCH-001"},
        headers=_auth(token),
    )
    txn_resp = await client.get(
        f"/api/v1/inventory/batches/{batch['id']}/transactions",
        headers=_auth(token),
    )
    txns = txn_resp.json()["data"]
    assert any(t["transaction_type"] == "stock_out" and t["quantity"] == 10 for t in txns)


# ── Rule 5: transactions are never deleted ────────────────────────────────────


async def test_no_delete_endpoint_for_transactions(client: AsyncClient):
    """Rule 5: the audit ledger has no DELETE endpoint."""
    token = await _inv_token(client, "rule5_del")
    mid = await _create_medicine(client, token, "INV-MED-R5")
    wid = await _create_warehouse(client, token, "INV-WH-R5")
    batch = await _create_batch(
        client, token, mid, wid, batch_number="RULE5-DEL", initial_quantity=10
    )
    txn_resp = await client.get(
        f"/api/v1/inventory/batches/{batch['id']}/transactions",
        headers=_auth(token),
    )
    txn_id = txn_resp.json()["data"][0]["id"]
    # Both DELETE paths should return 404 or 405 (not 204)
    del_resp = await client.delete(f"/api/v1/inventory/transactions/{txn_id}", headers=_auth(token))
    assert del_resp.status_code in (404, 405)


async def test_transactions_accumulate_and_are_never_purged(client: AsyncClient):
    """Rule 5: all historical transactions remain accessible."""
    token = await _inv_token(client, "rule5_accum")
    mid = await _create_medicine(client, token, "INV-MED-R5B")
    wid = await _create_warehouse(client, token, "INV-WH-R5B")
    batch = await _create_batch(
        client, token, mid, wid, batch_number="RULE5-ACCUM", initial_quantity=100
    )
    bid = batch["id"]
    # Perform 4 more movements
    for _i in range(4):
        await client.post(
            f"/api/v1/inventory/batches/{bid}/stock-in",
            json={"quantity": 1},
            headers=_auth(token),
        )
    txn_resp = await client.get(
        f"/api/v1/inventory/batches/{bid}/transactions",
        headers=_auth(token),
    )
    # 1 (initial STOCK_IN from create) + 4 stock-in = 5
    assert len(txn_resp.json()["data"]) == 5


# ── quantity arithmetic correctness ──────────────────────────────────────────


async def test_stock_in_increases_available(client: AsyncClient):
    token = await _inv_token(client, "arith_sin")
    mid = await _create_medicine(client, token, "INV-MED-A1")
    wid = await _create_warehouse(client, token, "INV-WH-A1")
    batch = await _create_batch(
        client, token, mid, wid, batch_number="ARITH-SIN", initial_quantity=10
    )
    resp = await client.post(
        f"/api/v1/inventory/batches/{batch['id']}/stock-in",
        json={"quantity": 5},
        headers=_auth(token),
    )
    assert resp.json()["data"]["quantity_available"] == 15


async def test_adjust_up_increases_available(client: AsyncClient):
    token = await _inv_token(client, "arith_adj_up")
    mid = await _create_medicine(client, token, "INV-MED-A2")
    wid = await _create_warehouse(client, token, "INV-WH-A2")
    batch = await _create_batch(
        client, token, mid, wid, batch_number="ARITH-ADJ-UP", initial_quantity=10
    )
    resp = await client.post(
        f"/api/v1/inventory/batches/{batch['id']}/adjust",
        json={"quantity_delta": 3},
        headers=_auth(token),
    )
    assert resp.json()["data"]["quantity_available"] == 13


async def test_adjust_down_decreases_available(client: AsyncClient):
    token = await _inv_token(client, "arith_adj_dn")
    mid = await _create_medicine(client, token, "INV-MED-A3")
    wid = await _create_warehouse(client, token, "INV-WH-A3")
    batch = await _create_batch(
        client, token, mid, wid, batch_number="ARITH-ADJ-DN", initial_quantity=10
    )
    resp = await client.post(
        f"/api/v1/inventory/batches/{batch['id']}/adjust",
        json={"quantity_delta": -4},
        headers=_auth(token),
    )
    assert resp.json()["data"]["quantity_available"] == 6


async def test_damage_moves_available_to_damaged(client: AsyncClient):
    token = await _inv_token(client, "arith_dmg")
    mid = await _create_medicine(client, token, "INV-MED-A4")
    wid = await _create_warehouse(client, token, "INV-WH-A4")
    batch = await _create_batch(
        client, token, mid, wid, batch_number="ARITH-DMG", initial_quantity=20
    )
    resp = await client.post(
        f"/api/v1/inventory/batches/{batch['id']}/damage",
        json={"quantity": 3},
        headers=_auth(token),
    )
    data = resp.json()["data"]
    assert data["quantity_available"] == 17
    assert data["quantity_damaged"] == 3


async def test_allocate_moves_available_to_reserved(client: AsyncClient):
    token = await _inv_token(client, "arith_alloc")
    mid = await _create_medicine(client, token, "INV-MED-A5")
    wid = await _create_warehouse(client, token, "INV-WH-A5")
    batch = await _create_batch(
        client, token, mid, wid, batch_number="ARITH-ALLOC", initial_quantity=15
    )
    resp = await client.post(
        f"/api/v1/inventory/batches/{batch['id']}/allocate",
        json={"quantity": 7},
        headers=_auth(token),
    )
    data = resp.json()["data"]
    assert data["quantity_available"] == 8
    assert data["quantity_reserved"] == 7


async def test_release_moves_reserved_to_available(client: AsyncClient):
    token = await _inv_token(client, "arith_rel")
    mid = await _create_medicine(client, token, "INV-MED-A6")
    wid = await _create_warehouse(client, token, "INV-WH-A6")
    batch = await _create_batch(
        client, token, mid, wid, batch_number="ARITH-REL", initial_quantity=20
    )
    await client.post(
        f"/api/v1/inventory/batches/{batch['id']}/allocate",
        json={"quantity": 10},
        headers=_auth(token),
    )
    resp = await client.post(
        f"/api/v1/inventory/batches/{batch['id']}/release",
        json={"quantity": 4},
        headers=_auth(token),
    )
    data = resp.json()["data"]
    assert data["quantity_available"] == 14
    assert data["quantity_reserved"] == 6


async def test_stock_out_reduces_reserved(client: AsyncClient):
    token = await _inv_token(client, "arith_sout")
    mid = await _create_medicine(client, token, "INV-MED-A7")
    wid = await _create_warehouse(client, token, "INV-WH-A7")
    batch = await _create_batch(
        client, token, mid, wid, batch_number="ARITH-SOUT", initial_quantity=30
    )
    await client.post(
        f"/api/v1/inventory/batches/{batch['id']}/allocate",
        json={"quantity": 12},
        headers=_auth(token),
    )
    resp = await client.post(
        f"/api/v1/inventory/batches/{batch['id']}/stock-out",
        json={"quantity": 12},
        headers=_auth(token),
    )
    data = resp.json()["data"]
    assert data["quantity_reserved"] == 0


async def test_stock_out_full_exhausts_batch(client: AsyncClient):
    """When all available AND reserved drop to 0, batch status → exhausted."""
    token = await _inv_token(client, "arith_exhaust")
    mid = await _create_medicine(client, token, "INV-MED-A8")
    wid = await _create_warehouse(client, token, "INV-WH-A8")
    batch = await _create_batch(
        client, token, mid, wid, batch_number="ARITH-EXHAUST", initial_quantity=5
    )
    await client.post(
        f"/api/v1/inventory/batches/{batch['id']}/allocate",
        json={"quantity": 5},
        headers=_auth(token),
    )
    resp = await client.post(
        f"/api/v1/inventory/batches/{batch['id']}/stock-out",
        json={"quantity": 5},
        headers=_auth(token),
    )
    assert resp.json()["data"]["status"] == "exhausted"


# ── Rule 4 / concurrency: only one of two simultaneous allocations succeeds ───


async def test_concurrent_allocation_atomicity(client: AsyncClient):
    """Rule 4: row-level lock ensures only one of two racing allocations wins."""
    token = await _inv_token(client, "rule4_concurrent")
    mid = await _create_medicine(client, token, "INV-MED-R4")
    wid = await _create_warehouse(client, token, "INV-WH-R4")
    batch = await _create_batch(
        client, token, mid, wid, batch_number="RULE4-CONCUR", initial_quantity=1
    )
    bid = batch["id"]

    async def allocate_one() -> int:
        r = await client.post(
            f"/api/v1/inventory/batches/{bid}/allocate",
            json={"quantity": 1},
            headers=_auth(token),
        )
        return r.status_code

    codes = await asyncio.gather(allocate_one(), allocate_one())
    # Exactly one should succeed (200) and one should fail (400)
    assert sorted(codes) == [200, 400]


# ── active-only filter ────────────────────────────────────────────────────────


async def test_active_only_filter(client: AsyncClient):
    token = await _inv_token(client, "active_filter")
    mid = await _create_medicine(client, token, "INV-MED-AF")
    wid = await _create_warehouse(client, token, "INV-WH-AF")
    # Create active batch
    await _create_batch(client, token, mid, wid, batch_number="ACTIVE-BATCH", initial_quantity=10)
    # Create exhausted batch
    exhausted = await _create_batch(
        client, token, mid, wid, batch_number="EXHAUST-BATCH", initial_quantity=1
    )
    await client.post(
        f"/api/v1/inventory/batches/{exhausted['id']}/allocate",
        json={"quantity": 1},
        headers=_auth(token),
    )
    await client.post(
        f"/api/v1/inventory/batches/{exhausted['id']}/stock-out",
        json={"quantity": 1},
        headers=_auth(token),
    )
    resp = await client.get("/api/v1/inventory/batches?active_only=true", headers=_auth(token))
    for b in resp.json()["data"]:
        assert b["status"] == "active"


# ── global transaction log ────────────────────────────────────────────────────


async def test_admin_can_list_all_transactions(client: AsyncClient):
    token = await _token_for_role(client, "admin_txn_list@example.com", UserRole.ADMIN)
    resp = await client.get("/api/v1/inventory/transactions", headers=_auth(token))
    assert resp.status_code == 200
    assert isinstance(resp.json()["data"], list)


async def test_sales_rep_cannot_list_all_transactions(client: AsyncClient):
    token = await _token_for_role(
        client, "sales_txn_list@example.com", UserRole.SALES_REPRESENTATIVE
    )
    resp = await client.get("/api/v1/inventory/transactions", headers=_auth(token))
    assert resp.status_code == 403
