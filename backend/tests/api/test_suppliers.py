"""Stage 5 — Supplier Management tests."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.db import get_session_local
from app.models.user import User, UserRole

pytestmark = pytest.mark.asyncio(loop_scope="session")

_SUPPLIER_PAYLOAD = {
    "supplier_code": "SUP001",
    "supplier_name": "MediCorp Ltd",
    "gst_number": "22AAAAA0000A1Z5",
    "drug_license_number": "DL-2024-001",
    "contact_person": "John Doe",
    "email": "contact@medicorp.com",
    "phone": "+91-9876543210",
    "address": "123 Pharma Street, Mumbai",
}


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


# ── create ────────────────────────────────────────────────────────────────────


async def test_inventory_manager_can_create_supplier(client: AsyncClient):
    token = await _token_for_role(client, "inv_sup_create@example.com", UserRole.INVENTORY_MANAGER)
    resp = await client.post("/api/v1/suppliers", json=_SUPPLIER_PAYLOAD, headers=_auth(token))
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["supplier_code"] == "SUP001"
    assert data["supplier_name"] == "MediCorp Ltd"
    assert data["status"] == "active"


async def test_admin_can_create_supplier(client: AsyncClient):
    token = await _token_for_role(client, "admin_sup_create@example.com", UserRole.ADMIN)
    payload = {**_SUPPLIER_PAYLOAD, "supplier_code": "SUP002"}
    resp = await client.post("/api/v1/suppliers", json=payload, headers=_auth(token))
    assert resp.status_code == 201


async def test_supplier_code_is_uppercased(client: AsyncClient):
    token = await _token_for_role(client, "inv_sup_upper@example.com", UserRole.INVENTORY_MANAGER)
    payload = {**_SUPPLIER_PAYLOAD, "supplier_code": "sup-lower"}
    resp = await client.post("/api/v1/suppliers", json=payload, headers=_auth(token))
    assert resp.status_code == 201
    assert resp.json()["data"]["supplier_code"] == "SUP-LOWER"


async def test_duplicate_supplier_code_rejected(client: AsyncClient):
    token = await _token_for_role(client, "inv_sup_dup@example.com", UserRole.INVENTORY_MANAGER)
    await client.post("/api/v1/suppliers", json=_SUPPLIER_PAYLOAD, headers=_auth(token))
    resp = await client.post("/api/v1/suppliers", json=_SUPPLIER_PAYLOAD, headers=_auth(token))
    assert resp.status_code == 409


async def test_customer_cannot_create_supplier(client: AsyncClient):
    token = await _token_for_role(client, "cust_sup_create@example.com", UserRole.CUSTOMER)
    resp = await client.post("/api/v1/suppliers", json=_SUPPLIER_PAYLOAD, headers=_auth(token))
    assert resp.status_code == 403


async def test_sales_rep_cannot_create_supplier(client: AsyncClient):
    token = await _token_for_role(
        client, "sales_sup_create@example.com", UserRole.SALES_REPRESENTATIVE
    )
    resp = await client.post("/api/v1/suppliers", json=_SUPPLIER_PAYLOAD, headers=_auth(token))
    assert resp.status_code == 403


async def test_unauthenticated_cannot_create_supplier(client: AsyncClient):
    resp = await client.post("/api/v1/suppliers", json=_SUPPLIER_PAYLOAD)
    assert resp.status_code == 401


# ── read ──────────────────────────────────────────────────────────────────────


async def test_list_suppliers(client: AsyncClient):
    token = await _token_for_role(client, "inv_sup_list@example.com", UserRole.INVENTORY_MANAGER)
    resp = await client.get("/api/v1/suppliers", headers=_auth(token))
    assert resp.status_code == 200
    assert isinstance(resp.json()["data"], list)


async def test_sales_rep_can_list_suppliers(client: AsyncClient):
    token = await _token_for_role(
        client, "sales_sup_list@example.com", UserRole.SALES_REPRESENTATIVE
    )
    resp = await client.get("/api/v1/suppliers", headers=_auth(token))
    assert resp.status_code == 200


async def test_warehouse_staff_can_list_suppliers(client: AsyncClient):
    token = await _token_for_role(client, "wh_sup_list@example.com", UserRole.WAREHOUSE_STAFF)
    resp = await client.get("/api/v1/suppliers", headers=_auth(token))
    assert resp.status_code == 200


async def test_customer_cannot_list_suppliers(client: AsyncClient):
    token = await _token_for_role(client, "cust_sup_list@example.com", UserRole.CUSTOMER)
    resp = await client.get("/api/v1/suppliers", headers=_auth(token))
    assert resp.status_code == 403


async def test_get_supplier_by_id(client: AsyncClient):
    token = await _token_for_role(client, "inv_sup_get@example.com", UserRole.INVENTORY_MANAGER)
    create_resp = await client.post(
        "/api/v1/suppliers",
        json={**_SUPPLIER_PAYLOAD, "supplier_code": "GET-SUP"},
        headers=_auth(token),
    )
    sid = create_resp.json()["data"]["id"]
    resp = await client.get(f"/api/v1/suppliers/{sid}", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["data"]["id"] == sid


async def test_get_supplier_404(client: AsyncClient):
    token = await _token_for_role(client, "inv_sup_404@example.com", UserRole.INVENTORY_MANAGER)
    resp = await client.get(f"/api/v1/suppliers/{uuid.uuid4()}", headers=_auth(token))
    assert resp.status_code == 404


# ── update ────────────────────────────────────────────────────────────────────


async def test_update_supplier(client: AsyncClient):
    token = await _token_for_role(client, "inv_sup_update@example.com", UserRole.INVENTORY_MANAGER)
    create_resp = await client.post(
        "/api/v1/suppliers",
        json={**_SUPPLIER_PAYLOAD, "supplier_code": "UPD-SUP"},
        headers=_auth(token),
    )
    sid = create_resp.json()["data"]["id"]
    resp = await client.put(
        f"/api/v1/suppliers/{sid}",
        json={"status": "inactive", "contact_person": "Jane Smith"},
        headers=_auth(token),
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "inactive"
    assert data["contact_person"] == "Jane Smith"


async def test_update_nonexistent_supplier(client: AsyncClient):
    token = await _token_for_role(client, "inv_sup_upd404@example.com", UserRole.INVENTORY_MANAGER)
    resp = await client.put(
        f"/api/v1/suppliers/{uuid.uuid4()}",
        json={"status": "inactive"},
        headers=_auth(token),
    )
    assert resp.status_code == 404


async def test_sales_rep_cannot_update_supplier(client: AsyncClient):
    inv_token = await _token_for_role(
        client, "inv_sup_for_sales@example.com", UserRole.INVENTORY_MANAGER
    )
    create_resp = await client.post(
        "/api/v1/suppliers",
        json={**_SUPPLIER_PAYLOAD, "supplier_code": "SALES-SUP"},
        headers=_auth(inv_token),
    )
    sid = create_resp.json()["data"]["id"]
    sales_token = await _token_for_role(
        client, "sales_sup_update@example.com", UserRole.SALES_REPRESENTATIVE
    )
    resp = await client.put(
        f"/api/v1/suppliers/{sid}",
        json={"status": "inactive"},
        headers=_auth(sales_token),
    )
    assert resp.status_code == 403


# ── delete ────────────────────────────────────────────────────────────────────


async def test_soft_delete_supplier(client: AsyncClient):
    token = await _token_for_role(client, "inv_sup_del@example.com", UserRole.INVENTORY_MANAGER)
    create_resp = await client.post(
        "/api/v1/suppliers",
        json={**_SUPPLIER_PAYLOAD, "supplier_code": "DEL-SUP"},
        headers=_auth(token),
    )
    sid = create_resp.json()["data"]["id"]
    resp = await client.delete(f"/api/v1/suppliers/{sid}", headers=_auth(token))
    assert resp.status_code == 204

    get_resp = await client.get(f"/api/v1/suppliers/{sid}", headers=_auth(token))
    assert get_resp.status_code == 404


async def test_delete_nonexistent_supplier(client: AsyncClient):
    token = await _token_for_role(client, "inv_sup_del404@example.com", UserRole.INVENTORY_MANAGER)
    resp = await client.delete(f"/api/v1/suppliers/{uuid.uuid4()}", headers=_auth(token))
    assert resp.status_code == 404
