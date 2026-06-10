"""Stage 4 — Medicine Management tests."""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.db import get_session_local
from app.models.user import User, UserRole

pytestmark = pytest.mark.asyncio(loop_scope="session")

_MEDICINE_PAYLOAD = {
    "code": "MED001",
    "name": "Paracetamol 500mg",
    "generic_name": "Paracetamol",
    "manufacturer": "ABC Pharma",
    "dosage": "500mg",
    "strength": "500mg",
    "dosage_form": "tablet",
    "unit_type": "Strip",
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


async def test_inventory_manager_can_create_medicine(client: AsyncClient):
    token = await _token_for_role(client, "inv_create@example.com", UserRole.INVENTORY_MANAGER)
    resp = await client.post("/api/v1/medicines", json=_MEDICINE_PAYLOAD, headers=_auth(token))
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["code"] == "MED001"
    assert data["dosage_form"] == "tablet"
    assert data["status"] == "active"


async def test_admin_can_create_medicine(client: AsyncClient):
    token = await _token_for_role(client, "admin_create_med@example.com", UserRole.ADMIN)
    payload = {**_MEDICINE_PAYLOAD, "code": "MED002"}
    resp = await client.post("/api/v1/medicines", json=payload, headers=_auth(token))
    assert resp.status_code == 201


async def test_duplicate_code_rejected(client: AsyncClient):
    token = await _token_for_role(client, "inv_dup@example.com", UserRole.INVENTORY_MANAGER)
    await client.post("/api/v1/medicines", json=_MEDICINE_PAYLOAD, headers=_auth(token))
    resp = await client.post("/api/v1/medicines", json=_MEDICINE_PAYLOAD, headers=_auth(token))
    assert resp.status_code == 409


async def test_code_is_uppercased(client: AsyncClient):
    token = await _token_for_role(client, "inv_upper@example.com", UserRole.INVENTORY_MANAGER)
    payload = {**_MEDICINE_PAYLOAD, "code": "med-lower"}
    resp = await client.post("/api/v1/medicines", json=payload, headers=_auth(token))
    assert resp.status_code == 201
    assert resp.json()["data"]["code"] == "MED-LOWER"


async def test_invalid_dosage_form_rejected(client: AsyncClient):
    token = await _token_for_role(client, "inv_bad_form@example.com", UserRole.INVENTORY_MANAGER)
    payload = {**_MEDICINE_PAYLOAD, "code": "MED-BAD", "dosage_form": "spaceship"}
    resp = await client.post("/api/v1/medicines", json=payload, headers=_auth(token))
    assert resp.status_code == 422


async def test_blank_name_rejected(client: AsyncClient):
    token = await _token_for_role(client, "inv_blank@example.com", UserRole.INVENTORY_MANAGER)
    payload = {**_MEDICINE_PAYLOAD, "code": "MED-BL", "name": "   "}
    resp = await client.post("/api/v1/medicines", json=payload, headers=_auth(token))
    assert resp.status_code == 422


async def test_customer_cannot_create_medicine(client: AsyncClient):
    token = await _token_for_role(client, "cust_create@example.com", UserRole.CUSTOMER)
    resp = await client.post("/api/v1/medicines", json=_MEDICINE_PAYLOAD, headers=_auth(token))
    assert resp.status_code == 403


async def test_sales_rep_cannot_create_medicine(client: AsyncClient):
    token = await _token_for_role(client, "sales_create@example.com", UserRole.SALES_REPRESENTATIVE)
    resp = await client.post("/api/v1/medicines", json=_MEDICINE_PAYLOAD, headers=_auth(token))
    assert resp.status_code == 403


# ── read ──────────────────────────────────────────────────────────────────────


async def test_list_medicines(client: AsyncClient):
    token = await _token_for_role(client, "inv_list@example.com", UserRole.INVENTORY_MANAGER)
    resp = await client.get("/api/v1/medicines", headers=_auth(token))
    assert resp.status_code == 200
    assert isinstance(resp.json()["data"], list)


async def test_sales_rep_can_list_medicines(client: AsyncClient):
    token = await _token_for_role(client, "sales_list@example.com", UserRole.SALES_REPRESENTATIVE)
    resp = await client.get("/api/v1/medicines", headers=_auth(token))
    assert resp.status_code == 200


async def test_get_medicine_by_id(client: AsyncClient):
    token = await _token_for_role(client, "inv_get_id@example.com", UserRole.INVENTORY_MANAGER)
    create_resp = await client.post(
        "/api/v1/medicines",
        json={**_MEDICINE_PAYLOAD, "code": "GET-BY-ID"},
        headers=_auth(token),
    )
    mid = create_resp.json()["data"]["id"]
    resp = await client.get(f"/api/v1/medicines/{mid}", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["data"]["id"] == mid


async def test_get_medicine_404(client: AsyncClient):
    token = await _token_for_role(client, "inv_404@example.com", UserRole.INVENTORY_MANAGER)
    resp = await client.get(f"/api/v1/medicines/{uuid.uuid4()}", headers=_auth(token))
    assert resp.status_code == 404


async def test_search_medicines(client: AsyncClient):
    token = await _token_for_role(client, "inv_search@example.com", UserRole.INVENTORY_MANAGER)
    await client.post(
        "/api/v1/medicines",
        json={**_MEDICINE_PAYLOAD, "code": "SEARCH-MED", "name": "Ibuprofen 400mg"},
        headers=_auth(token),
    )
    resp = await client.get("/api/v1/medicines/search?q=Ibuprofen", headers=_auth(token))
    assert resp.status_code == 200
    results = resp.json()["data"]
    assert any("Ibuprofen" in m["name"] for m in results)


async def test_active_only_filter(client: AsyncClient):
    token = await _token_for_role(client, "inv_active@example.com", UserRole.INVENTORY_MANAGER)
    # Create one active and one inactive medicine
    await client.post(
        "/api/v1/medicines",
        json={**_MEDICINE_PAYLOAD, "code": "ACTIVE-MED"},
        headers=_auth(token),
    )
    await client.post(
        "/api/v1/medicines",
        json={**_MEDICINE_PAYLOAD, "code": "INACTIVE-MED", "status": "inactive"},
        headers=_auth(token),
    )
    resp = await client.get("/api/v1/medicines?active_only=true", headers=_auth(token))
    assert resp.status_code == 200
    for m in resp.json()["data"]:
        assert m["status"] == "active"


# ── update ────────────────────────────────────────────────────────────────────


async def test_update_medicine(client: AsyncClient):
    token = await _token_for_role(client, "inv_update@example.com", UserRole.INVENTORY_MANAGER)
    create_resp = await client.post(
        "/api/v1/medicines",
        json={**_MEDICINE_PAYLOAD, "code": "UPD-MED"},
        headers=_auth(token),
    )
    mid = create_resp.json()["data"]["id"]
    resp = await client.put(
        f"/api/v1/medicines/{mid}",
        json={"status": "inactive", "manufacturer": "XYZ Pharma"},
        headers=_auth(token),
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["status"] == "inactive"
    assert data["manufacturer"] == "XYZ Pharma"


async def test_update_nonexistent_medicine(client: AsyncClient):
    token = await _token_for_role(client, "inv_upd404@example.com", UserRole.INVENTORY_MANAGER)
    resp = await client.put(
        f"/api/v1/medicines/{uuid.uuid4()}",
        json={"status": "inactive"},
        headers=_auth(token),
    )
    assert resp.status_code == 404


# ── delete ────────────────────────────────────────────────────────────────────


async def test_soft_delete_medicine(client: AsyncClient):
    token = await _token_for_role(client, "inv_del@example.com", UserRole.INVENTORY_MANAGER)
    create_resp = await client.post(
        "/api/v1/medicines",
        json={**_MEDICINE_PAYLOAD, "code": "DEL-MED"},
        headers=_auth(token),
    )
    mid = create_resp.json()["data"]["id"]
    resp = await client.delete(f"/api/v1/medicines/{mid}", headers=_auth(token))
    assert resp.status_code == 204

    # should not appear in list after deletion
    get_resp = await client.get(f"/api/v1/medicines/{mid}", headers=_auth(token))
    assert get_resp.status_code == 404


async def test_warehouse_staff_can_read_but_not_write(client: AsyncClient):
    inv_token = await _token_for_role(client, "inv_for_wh@example.com", UserRole.INVENTORY_MANAGER)
    create_resp = await client.post(
        "/api/v1/medicines",
        json={**_MEDICINE_PAYLOAD, "code": "WH-READ-MED"},
        headers=_auth(inv_token),
    )
    mid = create_resp.json()["data"]["id"]

    wh_token = await _token_for_role(client, "wh_staff@example.com", UserRole.WAREHOUSE_STAFF)
    # read — allowed
    read_resp = await client.get(f"/api/v1/medicines/{mid}", headers=_auth(wh_token))
    assert read_resp.status_code == 200
    # write — forbidden
    assert (
        await client.put(
            f"/api/v1/medicines/{mid}",
            json={"status": "inactive"},
            headers=_auth(wh_token),
        )
    ).status_code == 403
