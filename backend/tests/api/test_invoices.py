"""Stage 12 — Invoice Generation tests.

Tests verify:
- Generate invoice from DISPATCHED/DELIVERED/COMPLETED order → 201
- Invoice number format INV-YYYY-NNNN; sequential numbers
- Amounts reconcile with order items (subtotal, tax, discount, total)
- Line items mirror order items (quantity, unit_price, line_total)
- Cannot generate for DRAFT/PLACED/APPROVED → 400
- Duplicate invoice for same order → 409
- GET by id, GET by order id, list, list by customer filter
- Status transitions: draft→issued, issued→paid, invalid → 400
- Delete DRAFT invoice → 204; cannot delete ISSUED invoice → 400
- Role checks: SALES_REP can generate; WAREHOUSE_STAFF view-only; unauth → 401
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

_TODAY = "2026-06-11"
_FAR = "2028-12-31"


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
    return await _token_for_role(client, f"inv12_{suffix}@example.com", UserRole.INVENTORY_MANAGER)


async def _sales_token(client: AsyncClient, suffix: str) -> str:
    return await _token_for_role(
        client, f"sales12_{suffix}@example.com", UserRole.SALES_REPRESENTATIVE
    )


async def _wh_token(client: AsyncClient, suffix: str) -> str:
    return await _token_for_role(client, f"wh12_{suffix}@example.com", UserRole.WAREHOUSE_STAFF)


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
            "credit_limit": "50000.00",
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
) -> str:
    resp = await client.post(
        "/api/v1/inventory/batches",
        json={
            "medicine_id": medicine_id,
            "warehouse_id": warehouse_id,
            "batch_number": batch_number,
            "expiry_date": _FAR,
            "initial_quantity": qty,
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


async def _dispatch_order(
    client: AsyncClient,
    token: str,
    customer_id: str,
    medicine_id: str,
    *,
    qty: int = 10,
    unit_price: str = "100.00",
    discount: str = "0.00",
    tax_amount: str = "0.00",
) -> str:
    """Create an order and walk it to DISPATCHED; return the order id."""
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
                    "discount": discount,
                    "tax_amount": tax_amount,
                }
            ],
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    oid = resp.json()["data"]["id"]

    for transition in ("placed",):
        r = await client.patch(
            f"/api/v1/orders/{oid}/status",
            json={"status": transition},
            headers=_auth(token),
        )
        assert r.status_code == 200, r.text

    r = await client.post(f"/api/v1/orders/{oid}/approve", headers=_auth(token))
    assert r.status_code == 200, r.text

    for transition in ("allocated", "picked", "packed"):
        r = await client.patch(
            f"/api/v1/orders/{oid}/status",
            json={"status": transition},
            headers=_auth(token),
        )
        assert r.status_code == 200, r.text

    r = await client.post(f"/api/v1/orders/{oid}/dispatch", headers=_auth(token))
    assert r.status_code == 200, r.text

    return oid


async def _setup(
    client: AsyncClient,
    suffix: str,
    *,
    qty: int = 10,
    unit_price: str = "100.00",
    discount: str = "0.00",
    tax_amount: str = "0.00",
) -> tuple[str, str, str]:
    """Return (token, order_id, customer_id) for a freshly dispatched order."""
    token = await _inv_token(client, suffix)
    mid = await _create_medicine(client, token, f"INV12-MED-{suffix}")
    wid = await _create_warehouse(client, token, f"INV12-WH-{suffix}")
    cid = await _create_customer(client, token, f"INV12-CUST-{suffix}")
    await _create_batch(client, token, mid, wid, batch_number=f"INV12-B-{suffix}", qty=qty + 5)
    oid = await _dispatch_order(
        client,
        token,
        cid,
        mid,
        qty=qty,
        unit_price=unit_price,
        discount=discount,
        tax_amount=tax_amount,
    )
    return token, oid, cid


# ── generate ───────────────────────────────────────────────────────────────────


@freeze_time("2026-06-11")
async def test_generate_invoice_for_dispatched_order(client: AsyncClient):
    token, oid, _ = await _setup(client, "gen_disp")
    resp = await client.post("/api/v1/invoices", json={"order_id": oid}, headers=_auth(token))
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["status"] == "draft"
    assert data["order_id"] == oid
    assert data["invoice_number"].startswith("INV-2026-")
    assert data["total_amount"] == "1000.00"


@freeze_time("2026-06-11")
async def test_generate_invoice_for_delivered_order(client: AsyncClient):
    token, oid, _ = await _setup(client, "gen_deliv")
    await client.patch(
        f"/api/v1/orders/{oid}/status", json={"status": "delivered"}, headers=_auth(token)
    )
    resp = await client.post("/api/v1/invoices", json={"order_id": oid}, headers=_auth(token))
    assert resp.status_code == 201, resp.text
    assert resp.json()["data"]["status"] == "draft"


@freeze_time("2026-06-11")
async def test_generate_invoice_for_completed_order(client: AsyncClient):
    token, oid, _ = await _setup(client, "gen_comp")
    await client.patch(
        f"/api/v1/orders/{oid}/status", json={"status": "delivered"}, headers=_auth(token)
    )
    await client.patch(
        f"/api/v1/orders/{oid}/status", json={"status": "completed"}, headers=_auth(token)
    )
    resp = await client.post("/api/v1/invoices", json={"order_id": oid}, headers=_auth(token))
    assert resp.status_code == 201, resp.text


@freeze_time("2026-06-11")
async def test_invoice_number_format(client: AsyncClient):
    token, oid, _ = await _setup(client, "numfmt")
    resp = await client.post("/api/v1/invoices", json={"order_id": oid}, headers=_auth(token))
    assert resp.status_code == 201
    num = resp.json()["data"]["invoice_number"]
    # Format: INV-YYYY-NNNN
    parts = num.split("-")
    assert len(parts) == 3
    assert parts[0] == "INV"
    assert parts[1] == "2026"
    assert parts[2].isdigit() and len(parts[2]) == 4


@freeze_time("2026-06-11")
async def test_invoice_numbers_sequential(client: AsyncClient):
    token = await _inv_token(client, "seq")
    mid = await _create_medicine(client, token, "INV12-MED-SEQ")
    wid = await _create_warehouse(client, token, "INV12-WH-SEQ")
    cid = await _create_customer(client, token, "INV12-CUST-SEQ")
    await _create_batch(client, token, mid, wid, batch_number="INV12-B-SEQ", qty=30)
    oid1 = await _dispatch_order(client, token, cid, mid, qty=10)
    oid2 = await _dispatch_order(client, token, cid, mid, qty=10)

    r1 = await client.post("/api/v1/invoices", json={"order_id": oid1}, headers=_auth(token))
    r2 = await client.post("/api/v1/invoices", json={"order_id": oid2}, headers=_auth(token))
    assert r1.status_code == 201
    assert r2.status_code == 201

    seq1 = int(r1.json()["data"]["invoice_number"].split("-")[-1])
    seq2 = int(r2.json()["data"]["invoice_number"].split("-")[-1])
    assert seq2 == seq1 + 1


@freeze_time("2026-06-11")
async def test_amounts_reconcile_with_order(client: AsyncClient):
    # line_total = 5 * 200 - 100 + 50 = 950
    token, oid, _ = await _setup(
        client,
        "amounts",
        qty=5,
        unit_price="200.00",
        discount="100.00",
        tax_amount="50.00",
    )
    resp = await client.post("/api/v1/invoices", json={"order_id": oid}, headers=_auth(token))
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["subtotal"] == "1000.00"  # 5 * 200
    assert data["discount_amount"] == "100.00"
    assert data["tax_amount"] == "50.00"
    assert data["total_amount"] == "950.00"  # 1000 - 100 + 50


@freeze_time("2026-06-11")
async def test_invoice_line_items_created(client: AsyncClient):
    token, oid, _ = await _setup(client, "lines", qty=7, unit_price="50.00")
    resp = await client.post("/api/v1/invoices", json={"order_id": oid}, headers=_auth(token))
    assert resp.status_code == 201
    lines = resp.json()["data"]["lines"]
    assert len(lines) == 1
    line = lines[0]
    assert line["quantity"] == 7
    assert line["unit_price"] == "50.00"
    assert line["line_total"] == "350.00"


# ── eligible status gate ───────────────────────────────────────────────────────


@freeze_time("2026-06-11")
async def test_cannot_generate_for_draft_order(client: AsyncClient):
    token = await _inv_token(client, "elig_draft")
    cid = await _create_customer(client, token, "INV12-CUST-ED")
    mid = await _create_medicine(client, token, "INV12-MED-ED")
    resp = await client.post(
        "/api/v1/orders",
        json={
            "customer_id": cid,
            "order_date": _TODAY,
            "items": [{"medicine_id": mid, "quantity": 1, "unit_price": "10.00"}],
        },
        headers=_auth(token),
    )
    oid = resp.json()["data"]["id"]
    r = await client.post("/api/v1/invoices", json={"order_id": oid}, headers=_auth(token))
    assert r.status_code == 400


@freeze_time("2026-06-11")
async def test_cannot_generate_for_placed_order(client: AsyncClient):
    token = await _inv_token(client, "elig_placed")
    cid = await _create_customer(client, token, "INV12-CUST-EP")
    mid = await _create_medicine(client, token, "INV12-MED-EP")
    resp = await client.post(
        "/api/v1/orders",
        json={
            "customer_id": cid,
            "order_date": _TODAY,
            "items": [{"medicine_id": mid, "quantity": 1, "unit_price": "10.00"}],
        },
        headers=_auth(token),
    )
    oid = resp.json()["data"]["id"]
    await client.patch(
        f"/api/v1/orders/{oid}/status", json={"status": "placed"}, headers=_auth(token)
    )
    r = await client.post("/api/v1/invoices", json={"order_id": oid}, headers=_auth(token))
    assert r.status_code == 400


@freeze_time("2026-06-11")
async def test_cannot_generate_for_approved_order(client: AsyncClient):
    token = await _inv_token(client, "elig_appr")
    mid = await _create_medicine(client, token, "INV12-MED-EA")
    wid = await _create_warehouse(client, token, "INV12-WH-EA")
    cid = await _create_customer(client, token, "INV12-CUST-EA")
    await _create_batch(client, token, mid, wid, batch_number="INV12-B-EA", qty=15)
    resp = await client.post(
        "/api/v1/orders",
        json={
            "customer_id": cid,
            "order_date": _TODAY,
            "items": [{"medicine_id": mid, "quantity": 5, "unit_price": "10.00"}],
        },
        headers=_auth(token),
    )
    oid = resp.json()["data"]["id"]
    await client.patch(
        f"/api/v1/orders/{oid}/status", json={"status": "placed"}, headers=_auth(token)
    )
    await client.post(f"/api/v1/orders/{oid}/approve", headers=_auth(token))
    r = await client.post("/api/v1/invoices", json={"order_id": oid}, headers=_auth(token))
    assert r.status_code == 400


@freeze_time("2026-06-11")
async def test_duplicate_invoice_returns_409(client: AsyncClient):
    token, oid, _ = await _setup(client, "dup_inv")
    r1 = await client.post("/api/v1/invoices", json={"order_id": oid}, headers=_auth(token))
    assert r1.status_code == 201
    r2 = await client.post("/api/v1/invoices", json={"order_id": oid}, headers=_auth(token))
    assert r2.status_code == 409


@freeze_time("2026-06-11")
async def test_order_not_found_returns_404(client: AsyncClient):
    token = await _inv_token(client, "inv_nf")
    r = await client.post(
        "/api/v1/invoices",
        json={"order_id": str(uuid.uuid4())},
        headers=_auth(token),
    )
    assert r.status_code == 404


# ── read endpoints ─────────────────────────────────────────────────────────────


@freeze_time("2026-06-11")
async def test_get_invoice_by_id(client: AsyncClient):
    token, oid, _ = await _setup(client, "get_id")
    gen = await client.post("/api/v1/invoices", json={"order_id": oid}, headers=_auth(token))
    inv_id = gen.json()["data"]["id"]

    resp = await client.get(f"/api/v1/invoices/{inv_id}", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["data"]["id"] == inv_id
    assert resp.json()["data"]["order_number"] is not None


@freeze_time("2026-06-11")
async def test_get_invoice_by_order_id(client: AsyncClient):
    token, oid, _ = await _setup(client, "get_ord")
    await client.post("/api/v1/invoices", json={"order_id": oid}, headers=_auth(token))

    resp = await client.get(f"/api/v1/invoices/order/{oid}", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["data"]["order_id"] == oid


@freeze_time("2026-06-11")
async def test_get_invoice_not_found_returns_404(client: AsyncClient):
    token = await _inv_token(client, "inv_get_nf")
    resp = await client.get(f"/api/v1/invoices/{uuid.uuid4()}", headers=_auth(token))
    assert resp.status_code == 404


@freeze_time("2026-06-11")
async def test_list_invoices(client: AsyncClient):
    token, oid, _ = await _setup(client, "list_inv")
    await client.post("/api/v1/invoices", json={"order_id": oid}, headers=_auth(token))

    resp = await client.get("/api/v1/invoices", headers=_auth(token))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert isinstance(data, list)
    assert any(inv["order_id"] == oid for inv in data)


@freeze_time("2026-06-11")
async def test_list_invoices_by_customer_filter(client: AsyncClient):
    token, oid, cid = await _setup(client, "list_cust")
    await client.post("/api/v1/invoices", json={"order_id": oid}, headers=_auth(token))

    resp = await client.get(f"/api/v1/invoices?customer_id={cid}", headers=_auth(token))
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) >= 1
    assert all(inv["customer_id"] == cid for inv in data)


# ── status transitions ─────────────────────────────────────────────────────────


@freeze_time("2026-06-11")
async def test_update_status_draft_to_issued(client: AsyncClient):
    token, oid, _ = await _setup(client, "st_issued")
    gen = await client.post("/api/v1/invoices", json={"order_id": oid}, headers=_auth(token))
    inv_id = gen.json()["data"]["id"]

    resp = await client.patch(
        f"/api/v1/invoices/{inv_id}/status",
        json={"status": "issued"},
        headers=_auth(token),
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "issued"


@freeze_time("2026-06-11")
async def test_update_status_issued_to_paid(client: AsyncClient):
    token, oid, _ = await _setup(client, "st_paid")
    gen = await client.post("/api/v1/invoices", json={"order_id": oid}, headers=_auth(token))
    inv_id = gen.json()["data"]["id"]

    await client.patch(
        f"/api/v1/invoices/{inv_id}/status",
        json={"status": "issued"},
        headers=_auth(token),
    )
    resp = await client.patch(
        f"/api/v1/invoices/{inv_id}/status",
        json={"status": "paid"},
        headers=_auth(token),
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "paid"


@freeze_time("2026-06-11")
async def test_invalid_status_transition_returns_400(client: AsyncClient):
    token, oid, _ = await _setup(client, "st_invalid")
    gen = await client.post("/api/v1/invoices", json={"order_id": oid}, headers=_auth(token))
    inv_id = gen.json()["data"]["id"]

    # DRAFT → PAID is not a valid transition (must go through ISSUED first)
    resp = await client.patch(
        f"/api/v1/invoices/{inv_id}/status",
        json={"status": "paid"},
        headers=_auth(token),
    )
    assert resp.status_code == 400


@freeze_time("2026-06-11")
async def test_update_status_invoice_not_found_404(client: AsyncClient):
    token = await _inv_token(client, "st_nf")
    resp = await client.patch(
        f"/api/v1/invoices/{uuid.uuid4()}/status",
        json={"status": "issued"},
        headers=_auth(token),
    )
    assert resp.status_code == 404


# ── delete ─────────────────────────────────────────────────────────────────────


@freeze_time("2026-06-11")
async def test_delete_draft_invoice(client: AsyncClient):
    token, oid, _ = await _setup(client, "del_draft")
    gen = await client.post("/api/v1/invoices", json={"order_id": oid}, headers=_auth(token))
    inv_id = gen.json()["data"]["id"]

    del_resp = await client.delete(f"/api/v1/invoices/{inv_id}", headers=_auth(token))
    assert del_resp.status_code == 204

    get_resp = await client.get(f"/api/v1/invoices/{inv_id}", headers=_auth(token))
    assert get_resp.status_code == 404


@freeze_time("2026-06-11")
async def test_cannot_delete_issued_invoice(client: AsyncClient):
    token, oid, _ = await _setup(client, "del_issued")
    gen = await client.post("/api/v1/invoices", json={"order_id": oid}, headers=_auth(token))
    inv_id = gen.json()["data"]["id"]

    await client.patch(
        f"/api/v1/invoices/{inv_id}/status",
        json={"status": "issued"},
        headers=_auth(token),
    )
    resp = await client.delete(f"/api/v1/invoices/{inv_id}", headers=_auth(token))
    assert resp.status_code == 400


# ── role checks ────────────────────────────────────────────────────────────────


@freeze_time("2026-06-11")
async def test_sales_rep_can_generate_invoice(client: AsyncClient):
    inv_tok = await _inv_token(client, "sales_gen_inv")
    sales_tok = await _sales_token(client, "sales_gen")
    mid = await _create_medicine(client, inv_tok, "INV12-MED-SG")
    wid = await _create_warehouse(client, inv_tok, "INV12-WH-SG")
    cid = await _create_customer(client, inv_tok, "INV12-CUST-SG")
    await _create_batch(client, inv_tok, mid, wid, batch_number="INV12-B-SG", qty=15)
    oid = await _dispatch_order(client, inv_tok, cid, mid, qty=10)

    resp = await client.post("/api/v1/invoices", json={"order_id": oid}, headers=_auth(sales_tok))
    assert resp.status_code == 201


@freeze_time("2026-06-11")
async def test_warehouse_staff_can_view_invoice(client: AsyncClient):
    token, oid, _ = await _setup(client, "wh_view")
    wh_tok = await _wh_token(client, "wh_view")
    gen = await client.post("/api/v1/invoices", json={"order_id": oid}, headers=_auth(token))
    inv_id = gen.json()["data"]["id"]

    resp = await client.get(f"/api/v1/invoices/{inv_id}", headers=_auth(wh_tok))
    assert resp.status_code == 200


@freeze_time("2026-06-11")
async def test_warehouse_staff_cannot_generate_invoice(client: AsyncClient):
    token, oid, _ = await _setup(client, "wh_nogen")
    wh_tok = await _wh_token(client, "wh_nogen")

    resp = await client.post("/api/v1/invoices", json={"order_id": oid}, headers=_auth(wh_tok))
    assert resp.status_code == 403


async def test_unauthenticated_cannot_access_invoices(client: AsyncClient):
    resp = await client.get("/api/v1/invoices")
    assert resp.status_code == 401

    resp = await client.post("/api/v1/invoices", json={"order_id": str(uuid.uuid4())})
    assert resp.status_code == 401
