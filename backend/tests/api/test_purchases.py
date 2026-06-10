"""Stage 8 — Purchase Management tests.

Tests verify:
- Create PO (auto-generated and custom po_number)
- Duplicate po_number → 409
- List/get PO, 404 for unknown id
- Status transitions (DRAFT→SENT→CONFIRMED, invalid transition → 400)
- Goods receipt: creates InventoryBatches + STOCK_IN transactions in a single DB tx
- Goods receipt: PO status transitions to PARTIALLY_RECEIVED / RECEIVED
- Goods receipt for PO not in CONFIRMED state → 400
- Sales rep cannot create/modify PO (403), can read
- Unauthenticated → 401
- Delete DRAFT PO; cannot delete CONFIRMED PO
"""

from __future__ import annotations

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

_TODAY = date(2026, 6, 10)
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
    return await _token_for_role(client, f"po_inv_{suffix}@example.com", UserRole.INVENTORY_MANAGER)


async def _wh_token(client: AsyncClient, suffix: str) -> str:
    return await _token_for_role(client, f"po_wh_{suffix}@example.com", UserRole.WAREHOUSE_STAFF)


async def _sales_token(client: AsyncClient, suffix: str) -> str:
    return await _token_for_role(
        client, f"po_sales_{suffix}@example.com", UserRole.SALES_REPRESENTATIVE
    )


async def _create_supplier(client: AsyncClient, token: str, code: str) -> str:
    resp = await client.post(
        "/api/v1/suppliers",
        json={
            "supplier_code": code,
            "supplier_name": f"Supplier {code}",
            "address": "123 Main St",
            "phone": "9999999999",
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


async def _create_po(
    client: AsyncClient,
    token: str,
    supplier_id: str,
    medicine_id: str,
    *,
    po_number: str | None = None,
    qty: int = 100,
    unit_price: str = "10.00",
) -> dict:
    body: dict = {
        "supplier_id": supplier_id,
        "order_date": str(_TODAY),
        "items": [
            {
                "medicine_id": medicine_id,
                "quantity_ordered": qty,
                "unit_price": unit_price,
            }
        ],
    }
    if po_number:
        body["po_number"] = po_number
    resp = await client.post("/api/v1/purchases", json=body, headers=_auth(token))
    return resp


async def _transition(client: AsyncClient, token: str, po_id: str, new_status: str) -> dict:
    return await client.patch(
        f"/api/v1/purchases/{po_id}/status",
        json={"status": new_status},
        headers=_auth(token),
    )


async def _receive(
    client: AsyncClient,
    token: str,
    po_id: str,
    item_id: str,
    medicine_id: str,
    warehouse_id: str,
    *,
    batch_number: str = "BATCH-001",
    expiry_date: str = "2028-12-31",
    quantity: int = 50,
) -> dict:
    return await client.post(
        f"/api/v1/purchases/{po_id}/receive",
        json={
            "items": [
                {
                    "purchase_order_item_id": item_id,
                    "batch_number": batch_number,
                    "expiry_date": expiry_date,
                    "warehouse_id": warehouse_id,
                    "quantity": quantity,
                }
            ],
            "reference_number": "GRN-001",
        },
        headers=_auth(token),
    )


# ── create ─────────────────────────────────────────────────────────────────────


@freeze_time("2026-06-10")
async def test_create_po_auto_number(client: AsyncClient):
    token = await _inv_token(client, "create_auto")
    sid = await _create_supplier(client, token, "SUP-A1")
    mid = await _create_medicine(client, token, "MED-A1")
    resp = await _create_po(client, token, sid, mid)
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["status"] == "draft"
    assert data["po_number"].startswith("PO-")
    assert len(data["items"]) == 1
    assert data["items"][0]["quantity_ordered"] == 100
    assert data["total_amount"] == "1000.00"


@freeze_time("2026-06-10")
async def test_create_po_custom_number(client: AsyncClient):
    token = await _inv_token(client, "create_custom")
    sid = await _create_supplier(client, token, "SUP-B1")
    mid = await _create_medicine(client, token, "MED-B1")
    resp = await _create_po(client, token, sid, mid, po_number="PO-CUSTOM-001")
    assert resp.status_code == 201
    assert resp.json()["data"]["po_number"] == "PO-CUSTOM-001"


@freeze_time("2026-06-10")
async def test_create_po_duplicate_number_409(client: AsyncClient):
    token = await _inv_token(client, "dup_po")
    sid = await _create_supplier(client, token, "SUP-DUP1")
    mid = await _create_medicine(client, token, "MED-DUP1")
    r1 = await _create_po(client, token, sid, mid, po_number="PO-DUPTEST")
    assert r1.status_code == 201
    r2 = await _create_po(client, token, sid, mid, po_number="PO-DUPTEST")
    assert r2.status_code == 409


# ── list / get ─────────────────────────────────────────────────────────────────


@freeze_time("2026-06-10")
async def test_list_purchase_orders(client: AsyncClient):
    token = await _inv_token(client, "list")
    sid = await _create_supplier(client, token, "SUP-L1")
    mid = await _create_medicine(client, token, "MED-L1")
    await _create_po(client, token, sid, mid, po_number="PO-LIST-001")
    resp = await client.get("/api/v1/purchases", headers=_auth(token))
    assert resp.status_code == 200
    assert any(p["po_number"] == "PO-LIST-001" for p in resp.json()["data"])


@freeze_time("2026-06-10")
async def test_get_purchase_order_by_id(client: AsyncClient):
    token = await _inv_token(client, "getbyid")
    sid = await _create_supplier(client, token, "SUP-G1")
    mid = await _create_medicine(client, token, "MED-G1")
    resp = await _create_po(client, token, sid, mid, po_number="PO-GET-001")
    po_id = resp.json()["data"]["id"]
    get_resp = await client.get(f"/api/v1/purchases/{po_id}", headers=_auth(token))
    assert get_resp.status_code == 200
    assert get_resp.json()["data"]["po_number"] == "PO-GET-001"


async def test_get_nonexistent_po_404(client: AsyncClient):
    token = await _inv_token(client, "get404")
    resp = await client.get(f"/api/v1/purchases/{uuid.uuid4()}", headers=_auth(token))
    assert resp.status_code == 404


# ── status transitions ─────────────────────────────────────────────────────────


@freeze_time("2026-06-10")
async def test_status_transition_draft_to_sent(client: AsyncClient):
    token = await _inv_token(client, "trans_sent")
    sid = await _create_supplier(client, token, "SUP-T1")
    mid = await _create_medicine(client, token, "MED-T1")
    resp = await _create_po(client, token, sid, mid)
    po_id = resp.json()["data"]["id"]
    tr = await _transition(client, token, po_id, "sent")
    assert tr.status_code == 200
    assert tr.json()["data"]["status"] == "sent"


@freeze_time("2026-06-10")
async def test_status_transition_sent_to_confirmed(client: AsyncClient):
    token = await _inv_token(client, "trans_conf")
    sid = await _create_supplier(client, token, "SUP-TC1")
    mid = await _create_medicine(client, token, "MED-TC1")
    resp = await _create_po(client, token, sid, mid)
    po_id = resp.json()["data"]["id"]
    await _transition(client, token, po_id, "sent")
    tr = await _transition(client, token, po_id, "confirmed")
    assert tr.status_code == 200
    assert tr.json()["data"]["status"] == "confirmed"


@freeze_time("2026-06-10")
async def test_invalid_status_transition_400(client: AsyncClient):
    token = await _inv_token(client, "trans_inv")
    sid = await _create_supplier(client, token, "SUP-TI1")
    mid = await _create_medicine(client, token, "MED-TI1")
    resp = await _create_po(client, token, sid, mid)
    po_id = resp.json()["data"]["id"]
    # DRAFT → CONFIRMED is not a valid transition
    tr = await _transition(client, token, po_id, "confirmed")
    assert tr.status_code == 400


@freeze_time("2026-06-10")
async def test_cannot_transition_out_of_received(client: AsyncClient):
    token = await _inv_token(client, "trans_final")
    sid = await _create_supplier(client, token, "SUP-TF1")
    mid = await _create_medicine(client, token, "MED-TF1")
    wid = await _create_warehouse(client, token, "WH-TF1")
    resp = await _create_po(client, token, sid, mid, po_number="PO-TF-001")
    po_id = resp.json()["data"]["id"]
    item_id = resp.json()["data"]["items"][0]["id"]
    await _transition(client, token, po_id, "sent")
    await _transition(client, token, po_id, "confirmed")
    # Receive fully
    await _receive(client, token, po_id, item_id, mid, wid, quantity=100, batch_number="TF-B1")
    # Now try to cancel — should fail
    tr = await _transition(client, token, po_id, "cancelled")
    assert tr.status_code == 400


# ── goods receipt ──────────────────────────────────────────────────────────────


@freeze_time("2026-06-10")
async def test_receive_goods_creates_batch_and_stock_in_txn(client: AsyncClient):
    token = await _inv_token(client, "recv_batch")
    sid = await _create_supplier(client, token, "SUP-R1")
    mid = await _create_medicine(client, token, "MED-R1")
    wid = await _create_warehouse(client, token, "WH-R1")

    resp = await _create_po(client, token, sid, mid, po_number="PO-RECV-001", qty=100)
    po_id = resp.json()["data"]["id"]
    item_id = resp.json()["data"]["items"][0]["id"]

    await _transition(client, token, po_id, "sent")
    await _transition(client, token, po_id, "confirmed")

    recv_resp = await _receive(
        client,
        token,
        po_id,
        item_id,
        mid,
        wid,
        batch_number="RECV-B001",
        expiry_date="2028-12-31",
        quantity=50,
    )
    assert recv_resp.status_code == 200, recv_resp.text
    data = recv_resp.json()["data"]
    assert data["new_status"] == "partially_received"
    assert len(data["items_received"]) == 1
    assert data["items_received"][0]["quantity_received"] == 50

    batch_id = data["items_received"][0]["batch_id"]

    # Verify batch was created in DB with correct quantity
    async with get_session_local()() as session:
        batch = await session.get(InventoryBatch, batch_id)
        assert batch is not None
        assert batch.quantity_available == 50

        # Verify STOCK_IN transaction was created
        result = await session.execute(
            select(InventoryTransaction).where(
                InventoryTransaction.batch_id == batch_id,
                InventoryTransaction.transaction_type == TransactionType.STOCK_IN,
            )
        )
        txns = result.scalars().all()
        assert len(txns) == 1
        assert txns[0].quantity == 50
        assert txns[0].reference_number == "GRN-001"


@freeze_time("2026-06-10")
async def test_receive_fully_marks_po_received(client: AsyncClient):
    token = await _inv_token(client, "recv_full")
    sid = await _create_supplier(client, token, "SUP-RF1")
    mid = await _create_medicine(client, token, "MED-RF1")
    wid = await _create_warehouse(client, token, "WH-RF1")

    resp = await _create_po(client, token, sid, mid, po_number="PO-FULL-001", qty=50)
    po_id = resp.json()["data"]["id"]
    item_id = resp.json()["data"]["items"][0]["id"]

    await _transition(client, token, po_id, "sent")
    await _transition(client, token, po_id, "confirmed")

    recv_resp = await _receive(
        client,
        token,
        po_id,
        item_id,
        mid,
        wid,
        batch_number="FULL-B001",
        expiry_date="2028-12-31",
        quantity=50,
    )
    assert recv_resp.status_code == 200
    assert recv_resp.json()["data"]["new_status"] == "received"


@freeze_time("2026-06-10")
async def test_receive_twice_creates_same_batch_adds_qty(client: AsyncClient):
    token = await _inv_token(client, "recv_twice")
    sid = await _create_supplier(client, token, "SUP-RT1")
    mid = await _create_medicine(client, token, "MED-RT1")
    wid = await _create_warehouse(client, token, "WH-RT1")

    resp = await _create_po(client, token, sid, mid, po_number="PO-TWICE-001", qty=100)
    po_id = resp.json()["data"]["id"]
    item_id = resp.json()["data"]["items"][0]["id"]

    await _transition(client, token, po_id, "sent")
    await _transition(client, token, po_id, "confirmed")

    r1 = await _receive(
        client,
        token,
        po_id,
        item_id,
        mid,
        wid,
        batch_number="SAME-BATCH",
        expiry_date="2028-12-31",
        quantity=40,
    )
    assert r1.status_code == 200
    batch_id = r1.json()["data"]["items_received"][0]["batch_id"]

    # Second receipt for same batch_number — should add to existing batch
    r2 = await _receive(
        client,
        token,
        po_id,
        item_id,
        mid,
        wid,
        batch_number="SAME-BATCH",
        expiry_date="2028-12-31",
        quantity=60,
    )
    assert r2.status_code == 200
    assert r2.json()["data"]["new_status"] == "received"

    async with get_session_local()() as session:
        batch = await session.get(InventoryBatch, batch_id)
        assert batch.quantity_available == 100  # 40 + 60


@freeze_time("2026-06-10")
async def test_receive_non_confirmed_po_400(client: AsyncClient):
    token = await _inv_token(client, "recv_draft")
    sid = await _create_supplier(client, token, "SUP-RD1")
    mid = await _create_medicine(client, token, "MED-RD1")
    wid = await _create_warehouse(client, token, "WH-RD1")

    resp = await _create_po(client, token, sid, mid, po_number="PO-DRAFT-RECV")
    po_id = resp.json()["data"]["id"]
    item_id = resp.json()["data"]["items"][0]["id"]

    # Try to receive without confirming
    recv_resp = await _receive(client, token, po_id, item_id, mid, wid)
    assert recv_resp.status_code == 400


@freeze_time("2026-06-10")
async def test_receive_wrong_po_item_400(client: AsyncClient):
    token = await _inv_token(client, "recv_wrong_item")
    sid = await _create_supplier(client, token, "SUP-RWI1")
    mid = await _create_medicine(client, token, "MED-RWI1")
    wid = await _create_warehouse(client, token, "WH-RWI1")

    resp = await _create_po(client, token, sid, mid, po_number="PO-WRONG-ITEM")
    po_id = resp.json()["data"]["id"]
    await _transition(client, token, po_id, "sent")
    await _transition(client, token, po_id, "confirmed")

    fake_item_id = str(uuid.uuid4())
    recv_resp = await _receive(
        client,
        token,
        po_id,
        fake_item_id,
        mid,
        wid,
        quantity=50,
    )
    assert recv_resp.status_code == 400


# ── role checks ────────────────────────────────────────────────────────────────


@freeze_time("2026-06-10")
async def test_sales_rep_cannot_create_po(client: AsyncClient):
    inv_token = await _inv_token(client, "role_sales_cr")
    sales_token = await _sales_token(client, "role_sales_cr")
    sid = await _create_supplier(client, inv_token, "SUP-ROLE1")
    mid = await _create_medicine(client, inv_token, "MED-ROLE1")
    resp = await _create_po(client, sales_token, sid, mid)
    assert resp.status_code == 403


@freeze_time("2026-06-10")
async def test_sales_rep_can_read_po(client: AsyncClient):
    inv_token = await _inv_token(client, "role_sales_rd")
    sales_token = await _sales_token(client, "role_sales_rd")
    sid = await _create_supplier(client, inv_token, "SUP-ROLE2")
    mid = await _create_medicine(client, inv_token, "MED-ROLE2")
    resp = await _create_po(client, inv_token, sid, mid, po_number="PO-ROLE-READ")
    po_id = resp.json()["data"]["id"]
    get_resp = await client.get(f"/api/v1/purchases/{po_id}", headers=_auth(sales_token))
    assert get_resp.status_code == 200


@freeze_time("2026-06-10")
async def test_warehouse_staff_can_receive_goods(client: AsyncClient):
    inv_token = await _inv_token(client, "role_wh_recv")
    wh_token = await _wh_token(client, "role_wh_recv")
    sid = await _create_supplier(client, inv_token, "SUP-WH-R")
    mid = await _create_medicine(client, inv_token, "MED-WH-R")
    wid = await _create_warehouse(client, inv_token, "WH-WH-R")

    resp = await _create_po(client, inv_token, sid, mid, po_number="PO-WH-RECV", qty=50)
    po_id = resp.json()["data"]["id"]
    item_id = resp.json()["data"]["items"][0]["id"]
    await _transition(client, inv_token, po_id, "sent")
    await _transition(client, inv_token, po_id, "confirmed")

    recv_resp = await _receive(
        client,
        wh_token,
        po_id,
        item_id,
        mid,
        wid,
        batch_number="WH-RECV-B1",
        expiry_date="2028-12-31",
        quantity=50,
    )
    assert recv_resp.status_code == 200


async def test_unauthenticated_cannot_create_po(client: AsyncClient):
    resp = await client.post(
        "/api/v1/purchases",
        json={"supplier_id": str(uuid.uuid4()), "order_date": str(_TODAY), "items": []},
    )
    assert resp.status_code == 401


async def test_unauthenticated_cannot_list_po(client: AsyncClient):
    resp = await client.get("/api/v1/purchases")
    assert resp.status_code == 401


# ── delete ─────────────────────────────────────────────────────────────────────


@freeze_time("2026-06-10")
async def test_delete_draft_po(client: AsyncClient):
    token = await _inv_token(client, "del_draft")
    sid = await _create_supplier(client, token, "SUP-DEL1")
    mid = await _create_medicine(client, token, "MED-DEL1")
    resp = await _create_po(client, token, sid, mid, po_number="PO-DEL-001")
    po_id = resp.json()["data"]["id"]
    del_resp = await client.delete(f"/api/v1/purchases/{po_id}", headers=_auth(token))
    assert del_resp.status_code == 200
    get_resp = await client.get(f"/api/v1/purchases/{po_id}", headers=_auth(token))
    assert get_resp.status_code == 404


@freeze_time("2026-06-10")
async def test_cannot_delete_confirmed_po(client: AsyncClient):
    token = await _inv_token(client, "del_conf")
    sid = await _create_supplier(client, token, "SUP-DC1")
    mid = await _create_medicine(client, token, "MED-DC1")
    resp = await _create_po(client, token, sid, mid, po_number="PO-DELCONF-001")
    po_id = resp.json()["data"]["id"]
    await _transition(client, token, po_id, "sent")
    await _transition(client, token, po_id, "confirmed")
    del_resp = await client.delete(f"/api/v1/purchases/{po_id}", headers=_auth(token))
    assert del_resp.status_code == 400


async def test_delete_nonexistent_po_404(client: AsyncClient):
    token = await _inv_token(client, "del404")
    resp = await client.delete(f"/api/v1/purchases/{uuid.uuid4()}", headers=_auth(token))
    assert resp.status_code == 404
