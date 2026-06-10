"""Stage 9 — Customer Management tests.

Tests verify:
- Create customer (code uppercased, all fields stored)
- Duplicate customer_code → 409
- Blank business_name → 422
- Negative credit_limit → 422
- List customers (all + active_only filter)
- Get by id, 404 for unknown
- Update (partial, credit_limit, status)
- Soft delete then 404
- Sales rep and inventory manager can write
- Warehouse staff read-only (403 on write)
- Unauthenticated → 401
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.db import get_session_local
from app.models.user import User, UserRole

pytestmark = pytest.mark.asyncio(loop_scope="session")


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
        client, f"cust_inv_{suffix}@example.com", UserRole.INVENTORY_MANAGER
    )


async def _sales_token(client: AsyncClient, suffix: str) -> str:
    return await _token_for_role(
        client, f"cust_sales_{suffix}@example.com", UserRole.SALES_REPRESENTATIVE
    )


async def _wh_token(client: AsyncClient, suffix: str) -> str:
    return await _token_for_role(client, f"cust_wh_{suffix}@example.com", UserRole.WAREHOUSE_STAFF)


def _customer_payload(code: str, **overrides) -> dict:
    base = {
        "customer_code": code,
        "business_name": f"Business {code}",
        "phone": "9876543210",
        "address": "123 Test Street",
        "credit_limit": "5000.00",
        "status": "active",
    }
    base.update(overrides)
    return base


# ── create ─────────────────────────────────────────────────────────────────────


async def test_create_customer_by_inventory_manager(client: AsyncClient):
    token = await _inv_token(client, "create_inv")
    resp = await client.post(
        "/api/v1/customers",
        json=_customer_payload("CUST-INV-001"),
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["customer_code"] == "CUST-INV-001"
    assert data["business_name"] == "Business CUST-INV-001"
    assert data["credit_limit"] == "5000.00"
    assert data["status"] == "active"


async def test_create_customer_by_sales_rep(client: AsyncClient):
    token = await _sales_token(client, "create_sales")
    resp = await client.post(
        "/api/v1/customers",
        json=_customer_payload("CUST-SALES-001"),
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text


async def test_customer_code_is_uppercased(client: AsyncClient):
    token = await _inv_token(client, "upper")
    resp = await client.post(
        "/api/v1/customers",
        json=_customer_payload("cust-lower-001"),
        headers=_auth(token),
    )
    assert resp.status_code == 201
    assert resp.json()["data"]["customer_code"] == "CUST-LOWER-001"


async def test_create_customer_all_fields(client: AsyncClient):
    token = await _inv_token(client, "allfields")
    payload = {
        "customer_code": "CUST-FULL-001",
        "business_name": "Full Business",
        "contact_person": "John Doe",
        "email": "john@example.com",
        "phone": "9876543210",
        "gst_number": "27AAPFU0939F1ZV",
        "drug_license_number": "MH-12345",
        "address": "456 Full Street",
        "credit_limit": "10000.00",
        "status": "active",
    }
    resp = await client.post("/api/v1/customers", json=payload, headers=_auth(token))
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["contact_person"] == "John Doe"
    assert data["gst_number"] == "27AAPFU0939F1ZV"
    assert data["drug_license_number"] == "MH-12345"


async def test_duplicate_customer_code_409(client: AsyncClient):
    token = await _inv_token(client, "dup")
    await client.post(
        "/api/v1/customers",
        json=_customer_payload("CUST-DUP-001"),
        headers=_auth(token),
    )
    resp = await client.post(
        "/api/v1/customers",
        json=_customer_payload("CUST-DUP-001"),
        headers=_auth(token),
    )
    assert resp.status_code == 409


async def test_blank_business_name_422(client: AsyncClient):
    token = await _inv_token(client, "blank_name")
    resp = await client.post(
        "/api/v1/customers",
        json=_customer_payload("CUST-BLANK-001", business_name="   "),
        headers=_auth(token),
    )
    assert resp.status_code == 422


async def test_negative_credit_limit_422(client: AsyncClient):
    token = await _inv_token(client, "neg_credit")
    resp = await client.post(
        "/api/v1/customers",
        json=_customer_payload("CUST-NEG-001", credit_limit="-100.00"),
        headers=_auth(token),
    )
    assert resp.status_code == 422


async def test_zero_credit_limit_allowed(client: AsyncClient):
    token = await _inv_token(client, "zero_credit")
    resp = await client.post(
        "/api/v1/customers",
        json=_customer_payload("CUST-ZERO-001", credit_limit="0.00"),
        headers=_auth(token),
    )
    assert resp.status_code == 201
    assert resp.json()["data"]["credit_limit"] == "0.00"


async def test_blacklisted_status_on_create(client: AsyncClient):
    token = await _inv_token(client, "blacklist_cr")
    resp = await client.post(
        "/api/v1/customers",
        json=_customer_payload("CUST-BL-001", status="blacklisted"),
        headers=_auth(token),
    )
    assert resp.status_code == 201
    assert resp.json()["data"]["status"] == "blacklisted"


# ── list ───────────────────────────────────────────────────────────────────────


async def test_list_customers_all_roles(client: AsyncClient):
    token = await _inv_token(client, "list_all")
    await client.post(
        "/api/v1/customers", json=_customer_payload("CUST-LIST-001"), headers=_auth(token)
    )
    resp = await client.get("/api/v1/customers", headers=_auth(token))
    assert resp.status_code == 200
    codes = [c["customer_code"] for c in resp.json()["data"]]
    assert "CUST-LIST-001" in codes


async def test_list_customers_active_only_filter(client: AsyncClient):
    token = await _inv_token(client, "list_active")
    await client.post(
        "/api/v1/customers",
        json=_customer_payload("CUST-ACT-001", status="active"),
        headers=_auth(token),
    )
    await client.post(
        "/api/v1/customers",
        json=_customer_payload("CUST-INACT-001", status="inactive"),
        headers=_auth(token),
    )
    resp = await client.get("/api/v1/customers?active_only=true", headers=_auth(token))
    assert resp.status_code == 200
    statuses = [c["status"] for c in resp.json()["data"]]
    assert all(s == "active" for s in statuses)
    codes = [c["customer_code"] for c in resp.json()["data"]]
    assert "CUST-INACT-001" not in codes


# ── get by id ──────────────────────────────────────────────────────────────────


async def test_get_customer_by_id(client: AsyncClient):
    token = await _inv_token(client, "getbyid")
    r = await client.post(
        "/api/v1/customers", json=_customer_payload("CUST-GET-001"), headers=_auth(token)
    )
    cid = r.json()["data"]["id"]
    resp = await client.get(f"/api/v1/customers/{cid}", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["data"]["customer_code"] == "CUST-GET-001"


async def test_get_nonexistent_customer_404(client: AsyncClient):
    token = await _inv_token(client, "get404")
    resp = await client.get(f"/api/v1/customers/{uuid.uuid4()}", headers=_auth(token))
    assert resp.status_code == 404


# ── update ─────────────────────────────────────────────────────────────────────


async def test_update_customer_credit_limit(client: AsyncClient):
    token = await _inv_token(client, "upd_credit")
    r = await client.post(
        "/api/v1/customers",
        json=_customer_payload("CUST-UPD-001", credit_limit="1000.00"),
        headers=_auth(token),
    )
    cid = r.json()["data"]["id"]
    resp = await client.put(
        f"/api/v1/customers/{cid}",
        json={"credit_limit": "25000.00"},
        headers=_auth(token),
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["credit_limit"] == "25000.00"


async def test_update_customer_status_to_blacklisted(client: AsyncClient):
    token = await _inv_token(client, "upd_bl")
    r = await client.post(
        "/api/v1/customers",
        json=_customer_payload("CUST-BL-UPD-001"),
        headers=_auth(token),
    )
    cid = r.json()["data"]["id"]
    resp = await client.put(
        f"/api/v1/customers/{cid}",
        json={"status": "blacklisted"},
        headers=_auth(token),
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "blacklisted"


async def test_update_customer_negative_credit_limit_422(client: AsyncClient):
    token = await _inv_token(client, "upd_neg")
    r = await client.post(
        "/api/v1/customers",
        json=_customer_payload("CUST-NEG-UPD-001"),
        headers=_auth(token),
    )
    cid = r.json()["data"]["id"]
    resp = await client.put(
        f"/api/v1/customers/{cid}",
        json={"credit_limit": "-500.00"},
        headers=_auth(token),
    )
    assert resp.status_code == 422


async def test_update_nonexistent_customer_404(client: AsyncClient):
    token = await _inv_token(client, "upd404")
    resp = await client.put(
        f"/api/v1/customers/{uuid.uuid4()}",
        json={"business_name": "New Name"},
        headers=_auth(token),
    )
    assert resp.status_code == 404


# ── soft delete ────────────────────────────────────────────────────────────────


async def test_soft_delete_customer_then_404(client: AsyncClient):
    token = await _inv_token(client, "del")
    r = await client.post(
        "/api/v1/customers",
        json=_customer_payload("CUST-DEL-001"),
        headers=_auth(token),
    )
    cid = r.json()["data"]["id"]
    del_resp = await client.delete(f"/api/v1/customers/{cid}", headers=_auth(token))
    assert del_resp.status_code == 200
    get_resp = await client.get(f"/api/v1/customers/{cid}", headers=_auth(token))
    assert get_resp.status_code == 404


async def test_delete_nonexistent_customer_404(client: AsyncClient):
    token = await _inv_token(client, "del404")
    resp = await client.delete(f"/api/v1/customers/{uuid.uuid4()}", headers=_auth(token))
    assert resp.status_code == 404


async def test_deleted_customer_excluded_from_list(client: AsyncClient):
    token = await _inv_token(client, "del_list")
    r = await client.post(
        "/api/v1/customers",
        json=_customer_payload("CUST-DELLIST-001"),
        headers=_auth(token),
    )
    cid = r.json()["data"]["id"]
    await client.delete(f"/api/v1/customers/{cid}", headers=_auth(token))
    resp = await client.get("/api/v1/customers", headers=_auth(token))
    codes = [c["customer_code"] for c in resp.json()["data"]]
    assert "CUST-DELLIST-001" not in codes


# ── role checks ────────────────────────────────────────────────────────────────


async def test_warehouse_staff_cannot_create_customer(client: AsyncClient):
    wh_token = await _wh_token(client, "cr_block")
    resp = await client.post(
        "/api/v1/customers",
        json=_customer_payload("CUST-WH-CR"),
        headers=_auth(wh_token),
    )
    assert resp.status_code == 403


async def test_warehouse_staff_cannot_update_customer(client: AsyncClient):
    inv_token = await _inv_token(client, "wh_upd")
    wh_token = await _wh_token(client, "wh_upd")
    r = await client.post(
        "/api/v1/customers",
        json=_customer_payload("CUST-WH-UPD"),
        headers=_auth(inv_token),
    )
    cid = r.json()["data"]["id"]
    resp = await client.put(
        f"/api/v1/customers/{cid}",
        json={"business_name": "Changed"},
        headers=_auth(wh_token),
    )
    assert resp.status_code == 403


async def test_warehouse_staff_can_read_customers(client: AsyncClient):
    inv_token = await _inv_token(client, "wh_rd")
    wh_token = await _wh_token(client, "wh_rd")
    r = await client.post(
        "/api/v1/customers",
        json=_customer_payload("CUST-WH-RD"),
        headers=_auth(inv_token),
    )
    cid = r.json()["data"]["id"]
    resp = await client.get(f"/api/v1/customers/{cid}", headers=_auth(wh_token))
    assert resp.status_code == 200


async def test_sales_rep_can_delete_customer(client: AsyncClient):
    sales_token = await _sales_token(client, "del_sales")
    r = await client.post(
        "/api/v1/customers",
        json=_customer_payload("CUST-SALES-DEL"),
        headers=_auth(sales_token),
    )
    cid = r.json()["data"]["id"]
    resp = await client.delete(f"/api/v1/customers/{cid}", headers=_auth(sales_token))
    assert resp.status_code == 200


async def test_unauthenticated_cannot_create_customer(client: AsyncClient):
    resp = await client.post("/api/v1/customers", json=_customer_payload("CUST-UNAUTH"))
    assert resp.status_code == 401


async def test_unauthenticated_cannot_list_customers(client: AsyncClient):
    resp = await client.get("/api/v1/customers")
    assert resp.status_code == 401
