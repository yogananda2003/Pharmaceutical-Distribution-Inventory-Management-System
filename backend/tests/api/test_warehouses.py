"""Stage 5 — Warehouse Management tests."""
from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.db import get_session_local
from app.models.user import User, UserRole

pytestmark = pytest.mark.asyncio(loop_scope="session")

_WAREHOUSE_PAYLOAD = {
    "warehouse_code": "WH001",
    "warehouse_name": "Central Warehouse",
    "address": "456 Logistics Park, Delhi",
    "contact_details": "Tel: +91-11-12345678",
    "is_active": True,
}


# ── helpers ───────────────────────────────────────────────────────────────────


async def _register_and_login(
    client: AsyncClient, email: str, password: str = "Pass1234"
) -> dict:
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


async def test_inventory_manager_can_create_warehouse(client: AsyncClient):
    token = await _token_for_role(
        client, "inv_wh_create@example.com", UserRole.INVENTORY_MANAGER
    )
    resp = await client.post("/api/v1/warehouses", json=_WAREHOUSE_PAYLOAD, headers=_auth(token))
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["warehouse_code"] == "WH001"
    assert data["warehouse_name"] == "Central Warehouse"
    assert data["is_active"] is True


async def test_admin_can_create_warehouse(client: AsyncClient):
    token = await _token_for_role(client, "admin_wh_create@example.com", UserRole.ADMIN)
    payload = {**_WAREHOUSE_PAYLOAD, "warehouse_code": "WH002"}
    resp = await client.post("/api/v1/warehouses", json=payload, headers=_auth(token))
    assert resp.status_code == 201


async def test_warehouse_code_is_uppercased(client: AsyncClient):
    token = await _token_for_role(
        client, "inv_wh_upper@example.com", UserRole.INVENTORY_MANAGER
    )
    payload = {**_WAREHOUSE_PAYLOAD, "warehouse_code": "wh-lower"}
    resp = await client.post("/api/v1/warehouses", json=payload, headers=_auth(token))
    assert resp.status_code == 201
    assert resp.json()["data"]["warehouse_code"] == "WH-LOWER"


async def test_duplicate_warehouse_code_rejected(client: AsyncClient):
    token = await _token_for_role(
        client, "inv_wh_dup@example.com", UserRole.INVENTORY_MANAGER
    )
    await client.post("/api/v1/warehouses", json=_WAREHOUSE_PAYLOAD, headers=_auth(token))
    resp = await client.post("/api/v1/warehouses", json=_WAREHOUSE_PAYLOAD, headers=_auth(token))
    assert resp.status_code == 409


async def test_customer_cannot_create_warehouse(client: AsyncClient):
    token = await _token_for_role(client, "cust_wh_create@example.com", UserRole.CUSTOMER)
    resp = await client.post("/api/v1/warehouses", json=_WAREHOUSE_PAYLOAD, headers=_auth(token))
    assert resp.status_code == 403


async def test_sales_rep_cannot_create_warehouse(client: AsyncClient):
    token = await _token_for_role(
        client, "sales_wh_create@example.com", UserRole.SALES_REPRESENTATIVE
    )
    resp = await client.post("/api/v1/warehouses", json=_WAREHOUSE_PAYLOAD, headers=_auth(token))
    assert resp.status_code == 403


async def test_unauthenticated_cannot_create_warehouse(client: AsyncClient):
    resp = await client.post("/api/v1/warehouses", json=_WAREHOUSE_PAYLOAD)
    assert resp.status_code == 401


# ── read ──────────────────────────────────────────────────────────────────────


async def test_list_warehouses(client: AsyncClient):
    token = await _token_for_role(client, "inv_wh_list@example.com", UserRole.INVENTORY_MANAGER)
    resp = await client.get("/api/v1/warehouses", headers=_auth(token))
    assert resp.status_code == 200
    assert isinstance(resp.json()["data"], list)


async def test_sales_rep_can_list_warehouses(client: AsyncClient):
    token = await _token_for_role(
        client, "sales_wh_list@example.com", UserRole.SALES_REPRESENTATIVE
    )
    resp = await client.get("/api/v1/warehouses", headers=_auth(token))
    assert resp.status_code == 200


async def test_warehouse_staff_can_list_warehouses(client: AsyncClient):
    token = await _token_for_role(
        client, "wh_staff_wh_list@example.com", UserRole.WAREHOUSE_STAFF
    )
    resp = await client.get("/api/v1/warehouses", headers=_auth(token))
    assert resp.status_code == 200


async def test_customer_cannot_list_warehouses(client: AsyncClient):
    token = await _token_for_role(
        client, "cust_wh_list@example.com", UserRole.CUSTOMER
    )
    resp = await client.get("/api/v1/warehouses", headers=_auth(token))
    assert resp.status_code == 403


async def test_get_warehouse_by_id(client: AsyncClient):
    token = await _token_for_role(
        client, "inv_wh_get@example.com", UserRole.INVENTORY_MANAGER
    )
    create_resp = await client.post(
        "/api/v1/warehouses",
        json={**_WAREHOUSE_PAYLOAD, "warehouse_code": "GET-WH"},
        headers=_auth(token),
    )
    wid = create_resp.json()["data"]["id"]
    resp = await client.get(f"/api/v1/warehouses/{wid}", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["data"]["id"] == wid


async def test_get_warehouse_404(client: AsyncClient):
    token = await _token_for_role(client, "inv_wh_404@example.com", UserRole.INVENTORY_MANAGER)
    resp = await client.get(f"/api/v1/warehouses/{uuid.uuid4()}", headers=_auth(token))
    assert resp.status_code == 404


async def test_list_active_only_warehouses(client: AsyncClient):
    token = await _token_for_role(
        client, "inv_wh_active@example.com", UserRole.INVENTORY_MANAGER
    )
    await client.post(
        "/api/v1/warehouses",
        json={**_WAREHOUSE_PAYLOAD, "warehouse_code": "ACTIVE-WH", "is_active": True},
        headers=_auth(token),
    )
    await client.post(
        "/api/v1/warehouses",
        json={**_WAREHOUSE_PAYLOAD, "warehouse_code": "INACTIVE-WH", "is_active": False},
        headers=_auth(token),
    )
    resp = await client.get("/api/v1/warehouses?active_only=true", headers=_auth(token))
    assert resp.status_code == 200
    for w in resp.json()["data"]:
        assert w["is_active"] is True


# ── update ────────────────────────────────────────────────────────────────────


async def test_update_warehouse(client: AsyncClient):
    token = await _token_for_role(
        client, "inv_wh_update@example.com", UserRole.INVENTORY_MANAGER
    )
    create_resp = await client.post(
        "/api/v1/warehouses",
        json={**_WAREHOUSE_PAYLOAD, "warehouse_code": "UPD-WH"},
        headers=_auth(token),
    )
    wid = create_resp.json()["data"]["id"]
    resp = await client.put(
        f"/api/v1/warehouses/{wid}",
        json={"is_active": False, "contact_details": "Tel: +91-22-99887766"},
        headers=_auth(token),
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["is_active"] is False
    assert data["contact_details"] == "Tel: +91-22-99887766"


async def test_update_nonexistent_warehouse(client: AsyncClient):
    token = await _token_for_role(
        client, "inv_wh_upd404@example.com", UserRole.INVENTORY_MANAGER
    )
    resp = await client.put(
        f"/api/v1/warehouses/{uuid.uuid4()}",
        json={"is_active": False},
        headers=_auth(token),
    )
    assert resp.status_code == 404


async def test_sales_rep_cannot_update_warehouse(client: AsyncClient):
    inv_token = await _token_for_role(
        client, "inv_wh_for_sales@example.com", UserRole.INVENTORY_MANAGER
    )
    create_resp = await client.post(
        "/api/v1/warehouses",
        json={**_WAREHOUSE_PAYLOAD, "warehouse_code": "SALES-WH"},
        headers=_auth(inv_token),
    )
    wid = create_resp.json()["data"]["id"]
    sales_token = await _token_for_role(
        client, "sales_wh_update@example.com", UserRole.SALES_REPRESENTATIVE
    )
    resp = await client.put(
        f"/api/v1/warehouses/{wid}",
        json={"is_active": False},
        headers=_auth(sales_token),
    )
    assert resp.status_code == 403


# ── delete ────────────────────────────────────────────────────────────────────


async def test_soft_delete_warehouse(client: AsyncClient):
    token = await _token_for_role(
        client, "inv_wh_del@example.com", UserRole.INVENTORY_MANAGER
    )
    create_resp = await client.post(
        "/api/v1/warehouses",
        json={**_WAREHOUSE_PAYLOAD, "warehouse_code": "DEL-WH"},
        headers=_auth(token),
    )
    wid = create_resp.json()["data"]["id"]
    resp = await client.delete(f"/api/v1/warehouses/{wid}", headers=_auth(token))
    assert resp.status_code == 204

    get_resp = await client.get(f"/api/v1/warehouses/{wid}", headers=_auth(token))
    assert get_resp.status_code == 404


async def test_delete_nonexistent_warehouse(client: AsyncClient):
    token = await _token_for_role(
        client, "inv_wh_del404@example.com", UserRole.INVENTORY_MANAGER
    )
    resp = await client.delete(f"/api/v1/warehouses/{uuid.uuid4()}", headers=_auth(token))
    assert resp.status_code == 404


async def test_warehouse_staff_can_read_but_not_write(client: AsyncClient):
    inv_token = await _token_for_role(
        client, "inv_wh_for_wh_staff@example.com", UserRole.INVENTORY_MANAGER
    )
    create_resp = await client.post(
        "/api/v1/warehouses",
        json={**_WAREHOUSE_PAYLOAD, "warehouse_code": "WH-STAFF-READ"},
        headers=_auth(inv_token),
    )
    wid = create_resp.json()["data"]["id"]

    wh_token = await _token_for_role(
        client, "wh_staff_rw@example.com", UserRole.WAREHOUSE_STAFF
    )
    read_resp = await client.get(f"/api/v1/warehouses/{wid}", headers=_auth(wh_token))
    assert read_resp.status_code == 200

    write_resp = await client.put(
        f"/api/v1/warehouses/{wid}",
        json={"is_active": False},
        headers=_auth(wh_token),
    )
    assert write_resp.status_code == 403
