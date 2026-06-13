"""Stage 11 — Warehouse Operations tests.

Tests verify:
- Stock transfer between batches (same or different warehouses)
  - Reduces source qty_available, increases dest qty_available
  - Creates one TRANSFER transaction on each side (2 total)
  - Same batch → 400; insufficient stock → 400; qty=0 → 422
  - Source or dest not found → 404
  - Transferring all available stock marks source as EXHAUSTED
  - Transferring into an EXHAUSTED batch marks it ACTIVE
- Warehouse pending-order view: APPROVED/ALLOCATED/PICKED/PACKED only
- Pick list: batch locations + quantities from FEFO allocations
- Role checks: warehouse_staff and inventory_manager allowed; sales_rep → 403
- Unauthenticated → 401
"""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from freezegun import freeze_time
from httpx import AsyncClient
from sqlalchemy import select

from app.core.db import get_session_local
from app.models.inventory_batch import BatchStatus, InventoryBatch
from app.models.inventory_transaction import InventoryTransaction, TransactionType
from app.models.user import User, UserRole

pytestmark = pytest.mark.asyncio(loop_scope="session")

_TODAY = date(2026, 6, 11)


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
    return await _token_for_role(
        client, f"whops_inv_{suffix}@example.com", UserRole.INVENTORY_MANAGER
    )


async def _wh_token(client: AsyncClient, suffix: str) -> str:
    return await _token_for_role(
        client, f"whops_whs_{suffix}@example.com", UserRole.WAREHOUSE_STAFF
    )


async def _sales_token(client: AsyncClient, suffix: str) -> str:
    return await _token_for_role(
        client, f"whops_sal_{suffix}@example.com", UserRole.SALES_REPRESENTATIVE
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


async def _create_batch(
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
    qty: int = 10,
) -> str:
    resp = await client.post(
        "/api/v1/orders",
        json={
            "customer_id": customer_id,
            "order_date": str(_TODAY),
            "items": [{"medicine_id": medicine_id, "quantity": qty, "unit_price": "100.00"}],
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


async def _transition(client: AsyncClient, token: str, order_id: str, new_status: str) -> None:
    resp = await client.patch(
        f"/api/v1/orders/{order_id}/status",
        json={"status": new_status},
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text


async def _approve(client: AsyncClient, token: str, order_id: str) -> None:
    resp = await client.post(f"/api/v1/orders/{order_id}/approve", headers=_auth(token))
    assert resp.status_code == 200, resp.text


# ── stock transfer tests ───────────────────────────────────────────────────────


@freeze_time("2026-06-11")
async def test_transfer_reduces_source_adds_to_dest(client: AsyncClient):
    token = await _inv_token(client, "trf1")
    mid = await _create_medicine(client, token, "WHOPS-MED-TRF1")
    wid = await _create_warehouse(client, token, "WHOPS-WH-TRF1")
    src_id = await _create_batch(client, token, mid, wid, batch_number="TRF1-B1", qty=100)
    dst_id = await _create_batch(client, token, mid, wid, batch_number="TRF1-B2", qty=50)

    resp = await client.post(
        "/api/v1/warehouse/transfer",
        json={"source_batch_id": src_id, "destination_batch_id": dst_id, "quantity": 30},
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["source_quantity_available"] == 70
    assert data["destination_quantity_available"] == 80
    assert data["quantity"] == 30


@freeze_time("2026-06-11")
async def test_transfer_creates_two_transfer_txns(client: AsyncClient):
    token = await _inv_token(client, "trf2")
    mid = await _create_medicine(client, token, "WHOPS-MED-TRF2")
    wid = await _create_warehouse(client, token, "WHOPS-WH-TRF2")
    src_id = await _create_batch(client, token, mid, wid, batch_number="TRF2-B1", qty=60)
    dst_id = await _create_batch(client, token, mid, wid, batch_number="TRF2-B2", qty=20)

    resp = await client.post(
        "/api/v1/warehouse/transfer",
        json={"source_batch_id": src_id, "destination_batch_id": dst_id, "quantity": 15},
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text

    async with get_session_local()() as session:
        result = await session.execute(
            select(InventoryTransaction).where(
                InventoryTransaction.transaction_type == TransactionType.TRANSFER,
                InventoryTransaction.batch_id.in_([src_id, dst_id]),
            )
        )
        txns = result.scalars().all()

    assert len(txns) == 2
    batch_ids_in_txns = {str(t.batch_id) for t in txns}
    assert src_id in batch_ids_in_txns
    assert dst_id in batch_ids_in_txns
    assert all(t.quantity == 15 for t in txns)


@freeze_time("2026-06-11")
async def test_transfer_cross_warehouse(client: AsyncClient):
    token = await _inv_token(client, "trf3")
    mid = await _create_medicine(client, token, "WHOPS-MED-TRF3")
    wid1 = await _create_warehouse(client, token, "WHOPS-WH-TRF3A")
    wid2 = await _create_warehouse(client, token, "WHOPS-WH-TRF3B")
    src_id = await _create_batch(client, token, mid, wid1, batch_number="TRF3-B1", qty=50)
    dst_id = await _create_batch(client, token, mid, wid2, batch_number="TRF3-B2", qty=10)

    resp = await client.post(
        "/api/v1/warehouse/transfer",
        json={"source_batch_id": src_id, "destination_batch_id": dst_id, "quantity": 20},
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["source_quantity_available"] == 30
    assert data["destination_quantity_available"] == 30


async def test_transfer_same_batch_400(client: AsyncClient):
    token = await _inv_token(client, "trf_same")
    mid = await _create_medicine(client, token, "WHOPS-MED-TRF-SAME")
    wid = await _create_warehouse(client, token, "WHOPS-WH-TRF-SAME")
    batch_id = await _create_batch(client, token, mid, wid, batch_number="TRF-SAME-B", qty=100)

    resp = await client.post(
        "/api/v1/warehouse/transfer",
        json={"source_batch_id": batch_id, "destination_batch_id": batch_id, "quantity": 10},
        headers=_auth(token),
    )
    assert resp.status_code == 400


async def test_transfer_insufficient_stock_400(client: AsyncClient):
    token = await _inv_token(client, "trf_insuf")
    mid = await _create_medicine(client, token, "WHOPS-MED-TRF-INS")
    wid = await _create_warehouse(client, token, "WHOPS-WH-TRF-INS")
    src_id = await _create_batch(client, token, mid, wid, batch_number="TRF-INS-B1", qty=5)
    dst_id = await _create_batch(client, token, mid, wid, batch_number="TRF-INS-B2", qty=20)

    resp = await client.post(
        "/api/v1/warehouse/transfer",
        json={"source_batch_id": src_id, "destination_batch_id": dst_id, "quantity": 10},
        headers=_auth(token),
    )
    assert resp.status_code == 400


async def test_transfer_zero_qty_422(client: AsyncClient):
    token = await _inv_token(client, "trf_zero")
    mid = await _create_medicine(client, token, "WHOPS-MED-TRF-ZERO")
    wid = await _create_warehouse(client, token, "WHOPS-WH-TRF-ZERO")
    src_id = await _create_batch(client, token, mid, wid, batch_number="TRF-ZERO-B1", qty=50)
    dst_id = await _create_batch(client, token, mid, wid, batch_number="TRF-ZERO-B2", qty=10)

    resp = await client.post(
        "/api/v1/warehouse/transfer",
        json={"source_batch_id": src_id, "destination_batch_id": dst_id, "quantity": 0},
        headers=_auth(token),
    )
    assert resp.status_code == 422


async def test_transfer_source_not_found_404(client: AsyncClient):
    token = await _inv_token(client, "trf_nfsrc")
    mid = await _create_medicine(client, token, "WHOPS-MED-TRF-NFSRC")
    wid = await _create_warehouse(client, token, "WHOPS-WH-TRF-NFSRC")
    dst_id = await _create_batch(client, token, mid, wid, batch_number="TRF-NFSRC-B2", qty=50)

    resp = await client.post(
        "/api/v1/warehouse/transfer",
        json={
            "source_batch_id": str(uuid.uuid4()),
            "destination_batch_id": dst_id,
            "quantity": 10,
        },
        headers=_auth(token),
    )
    assert resp.status_code == 404


async def test_transfer_dest_not_found_404(client: AsyncClient):
    token = await _inv_token(client, "trf_nfdst")
    mid = await _create_medicine(client, token, "WHOPS-MED-TRF-NFDST")
    wid = await _create_warehouse(client, token, "WHOPS-WH-TRF-NFDST")
    src_id = await _create_batch(client, token, mid, wid, batch_number="TRF-NFDST-B1", qty=50)

    resp = await client.post(
        "/api/v1/warehouse/transfer",
        json={
            "source_batch_id": src_id,
            "destination_batch_id": str(uuid.uuid4()),
            "quantity": 10,
        },
        headers=_auth(token),
    )
    assert resp.status_code == 404


@freeze_time("2026-06-11")
async def test_transfer_exhausts_source_batch(client: AsyncClient):
    token = await _inv_token(client, "trf_exh")
    mid = await _create_medicine(client, token, "WHOPS-MED-TRF-EXH")
    wid = await _create_warehouse(client, token, "WHOPS-WH-TRF-EXH")
    src_id = await _create_batch(client, token, mid, wid, batch_number="TRF-EXH-B1", qty=20)
    dst_id = await _create_batch(client, token, mid, wid, batch_number="TRF-EXH-B2", qty=5)

    resp = await client.post(
        "/api/v1/warehouse/transfer",
        json={"source_batch_id": src_id, "destination_batch_id": dst_id, "quantity": 20},
        headers=_auth(token),
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["source_quantity_available"] == 0

    async with get_session_local()() as session:
        result = await session.execute(select(InventoryBatch).where(InventoryBatch.id == src_id))
        src_batch = result.scalar_one()
    assert src_batch.status == BatchStatus.EXHAUSTED
    assert src_batch.quantity_available == 0


@freeze_time("2026-06-11")
async def test_transfer_revives_exhausted_dest(client: AsyncClient):
    """Transferring stock into an EXHAUSTED batch marks it ACTIVE again."""
    token = await _inv_token(client, "trf_rev")
    mid = await _create_medicine(client, token, "WHOPS-MED-TRF-REV")
    wid = await _create_warehouse(client, token, "WHOPS-WH-TRF-REV")
    src_id = await _create_batch(client, token, mid, wid, batch_number="TRF-REV-B1", qty=30)
    dst_id = await _create_batch(client, token, mid, wid, batch_number="TRF-REV-B2", qty=0)

    # Directly mark dest as EXHAUSTED (the EXHAUSTED state is set by the service when
    # available+reserved drop to 0; here we seed it directly for test simplicity).
    async with get_session_local()() as session:
        result = await session.execute(select(InventoryBatch).where(InventoryBatch.id == dst_id))
        dst_batch = result.scalar_one()
        dst_batch.status = BatchStatus.EXHAUSTED
        await session.commit()

    # Transfer revives it
    resp = await client.post(
        "/api/v1/warehouse/transfer",
        json={"source_batch_id": src_id, "destination_batch_id": dst_id, "quantity": 10},
        headers=_auth(token),
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["destination_quantity_available"] == 10

    async with get_session_local()() as session:
        result = await session.execute(select(InventoryBatch).where(InventoryBatch.id == dst_id))
        dst_after = result.scalar_one()
    assert dst_after.status == BatchStatus.ACTIVE


@freeze_time("2026-06-11")
async def test_warehouse_staff_can_transfer(client: AsyncClient):
    inv_token = await _inv_token(client, "trf_whs")
    wh_token = await _wh_token(client, "trf_whs")
    mid = await _create_medicine(client, inv_token, "WHOPS-MED-TRF-WHS")
    wid = await _create_warehouse(client, inv_token, "WHOPS-WH-TRF-WHS")
    src_id = await _create_batch(client, inv_token, mid, wid, batch_number="TRF-WHS-B1", qty=50)
    dst_id = await _create_batch(client, inv_token, mid, wid, batch_number="TRF-WHS-B2", qty=10)

    resp = await client.post(
        "/api/v1/warehouse/transfer",
        json={"source_batch_id": src_id, "destination_batch_id": dst_id, "quantity": 20},
        headers=_auth(wh_token),
    )
    assert resp.status_code == 200


async def test_transfer_sales_rep_403(client: AsyncClient):
    inv_token = await _inv_token(client, "trf403")
    sales_token = await _sales_token(client, "trf403")
    mid = await _create_medicine(client, inv_token, "WHOPS-MED-TRF-403")
    wid = await _create_warehouse(client, inv_token, "WHOPS-WH-TRF-403")
    src_id = await _create_batch(client, inv_token, mid, wid, batch_number="TRF-403-B1", qty=30)
    dst_id = await _create_batch(client, inv_token, mid, wid, batch_number="TRF-403-B2", qty=5)

    resp = await client.post(
        "/api/v1/warehouse/transfer",
        json={"source_batch_id": src_id, "destination_batch_id": dst_id, "quantity": 10},
        headers=_auth(sales_token),
    )
    assert resp.status_code == 403


async def test_transfer_unauth_401(client: AsyncClient):
    resp = await client.post(
        "/api/v1/warehouse/transfer",
        json={
            "source_batch_id": str(uuid.uuid4()),
            "destination_batch_id": str(uuid.uuid4()),
            "quantity": 5,
        },
    )
    assert resp.status_code == 401


# ── warehouse pending orders tests ─────────────────────────────────────────────


@freeze_time("2026-06-11")
async def test_pending_orders_includes_approved(client: AsyncClient):
    token = await _inv_token(client, "pend1")
    mid = await _create_medicine(client, token, "WHOPS-MED-PEND1")
    wid = await _create_warehouse(client, token, "WHOPS-WH-PEND1")
    cid = await _create_customer(client, token, "WHOPS-CUST-PEND1")
    await _create_batch(client, token, mid, wid, batch_number="PEND1-B1", qty=50)
    oid = await _create_order(client, token, cid, mid, qty=10)
    await _transition(client, token, oid, "placed")
    await _approve(client, token, oid)

    resp = await client.get("/api/v1/warehouse/pending", headers=_auth(token))
    assert resp.status_code == 200
    order_ids = [o["id"] for o in resp.json()["data"]]
    assert oid in order_ids


@freeze_time("2026-06-11")
async def test_pending_orders_excludes_draft_and_placed(client: AsyncClient):
    token = await _inv_token(client, "pend2")
    mid = await _create_medicine(client, token, "WHOPS-MED-PEND2")
    wid = await _create_warehouse(client, token, "WHOPS-WH-PEND2")
    cid = await _create_customer(client, token, "WHOPS-CUST-PEND2")
    await _create_batch(client, token, mid, wid, batch_number="PEND2-B1", qty=50)

    draft_oid = await _create_order(client, token, cid, mid, qty=5)
    placed_oid = await _create_order(client, token, cid, mid, qty=5)
    await _transition(client, token, placed_oid, "placed")

    resp = await client.get("/api/v1/warehouse/pending", headers=_auth(token))
    assert resp.status_code == 200
    order_ids = {o["id"] for o in resp.json()["data"]}
    assert draft_oid not in order_ids
    assert placed_oid not in order_ids


async def test_warehouse_staff_can_see_pending(client: AsyncClient):
    wh_token = await _wh_token(client, "pend_whs")
    resp = await client.get("/api/v1/warehouse/pending", headers=_auth(wh_token))
    assert resp.status_code == 200


async def test_sales_rep_cannot_see_pending_403(client: AsyncClient):
    sales_token = await _sales_token(client, "pend_403")
    resp = await client.get("/api/v1/warehouse/pending", headers=_auth(sales_token))
    assert resp.status_code == 403


async def test_pending_unauth_401(client: AsyncClient):
    resp = await client.get("/api/v1/warehouse/pending")
    assert resp.status_code == 401


# ── pick list tests ────────────────────────────────────────────────────────────


@freeze_time("2026-06-11")
async def test_pick_list_for_approved_order(client: AsyncClient):
    token = await _inv_token(client, "pl1")
    mid = await _create_medicine(client, token, "WHOPS-MED-PL1")
    wid = await _create_warehouse(client, token, "WHOPS-WH-PL1")
    cid = await _create_customer(client, token, "WHOPS-CUST-PL1")
    await _create_batch(client, token, mid, wid, batch_number="PL1-B1", qty=50)
    oid = await _create_order(client, token, cid, mid, qty=15)
    await _transition(client, token, oid, "placed")
    await _approve(client, token, oid)

    resp = await client.get(f"/api/v1/warehouse/orders/{oid}/pick-list", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    pl = resp.json()["data"]
    assert pl["order_id"] == oid
    assert pl["order_status"] == "approved"
    assert len(pl["items"]) == 1
    item = pl["items"][0]
    assert item["total_quantity"] == 15
    assert len(item["batches"]) == 1
    b = item["batches"][0]
    assert b["quantity_to_pick"] == 15
    assert b["warehouse_name"] == "WH WHOPS-WH-PL1"
    assert b["batch_number"] == "PL1-B1"


@freeze_time("2026-06-11")
async def test_pick_list_multi_batch_fefo(client: AsyncClient):
    """Order of 7 units with two batches (3 + 5); FEFO takes from earliest expiry first."""
    token = await _inv_token(client, "pl2")
    mid = await _create_medicine(client, token, "WHOPS-MED-PL2")
    wid = await _create_warehouse(client, token, "WHOPS-WH-PL2")
    cid = await _create_customer(client, token, "WHOPS-CUST-PL2")
    # B1 expires sooner — FEFO picks all 3 from here first
    await _create_batch(client, token, mid, wid, batch_number="PL2-B1", qty=3, expiry="2027-06-30")
    # B2 expires later — remaining 4 come from here
    await _create_batch(client, token, mid, wid, batch_number="PL2-B2", qty=5, expiry="2028-12-31")

    oid = await _create_order(client, token, cid, mid, qty=7)
    await _transition(client, token, oid, "placed")
    await _approve(client, token, oid)

    resp = await client.get(f"/api/v1/warehouse/orders/{oid}/pick-list", headers=_auth(token))
    assert resp.status_code == 200, resp.text
    pl = resp.json()["data"]
    assert len(pl["items"]) == 1
    # Two batch allocations expected
    batches = pl["items"][0]["batches"]
    assert len(batches) == 2
    total_qty = sum(b["quantity_to_pick"] for b in batches)
    assert total_qty == 7
    # FEFO: B1 (earlier expiry) fully depleted first
    by_number = {b["batch_number"]: b["quantity_to_pick"] for b in batches}
    assert by_number["PL2-B1"] == 3
    assert by_number["PL2-B2"] == 4


async def test_pick_list_draft_order_400(client: AsyncClient):
    token = await _inv_token(client, "pl3")
    mid = await _create_medicine(client, token, "WHOPS-MED-PL3")
    cid = await _create_customer(client, token, "WHOPS-CUST-PL3")
    oid = await _create_order(client, token, cid, mid, qty=5)

    resp = await client.get(f"/api/v1/warehouse/orders/{oid}/pick-list", headers=_auth(token))
    assert resp.status_code == 400


async def test_pick_list_order_not_found_404(client: AsyncClient):
    token = await _inv_token(client, "pl4")
    resp = await client.get(
        f"/api/v1/warehouse/orders/{uuid.uuid4()}/pick-list",
        headers=_auth(token),
    )
    assert resp.status_code == 404


@freeze_time("2026-06-11")
async def test_warehouse_staff_can_access_pick_list(client: AsyncClient):
    inv_token = await _inv_token(client, "pl_whs")
    wh_token = await _wh_token(client, "pl_whs")
    mid = await _create_medicine(client, inv_token, "WHOPS-MED-PL-WHS")
    wid = await _create_warehouse(client, inv_token, "WHOPS-WH-PL-WHS")
    cid = await _create_customer(client, inv_token, "WHOPS-CUST-PL-WHS")
    await _create_batch(client, inv_token, mid, wid, batch_number="PL-WHS-B1", qty=30)
    oid = await _create_order(client, inv_token, cid, mid, qty=10)
    await _transition(client, inv_token, oid, "placed")
    await _approve(client, inv_token, oid)

    resp = await client.get(f"/api/v1/warehouse/orders/{oid}/pick-list", headers=_auth(wh_token))
    assert resp.status_code == 200


async def test_pick_list_unauth_401(client: AsyncClient):
    resp = await client.get(f"/api/v1/warehouse/orders/{uuid.uuid4()}/pick-list")
    assert resp.status_code == 401
