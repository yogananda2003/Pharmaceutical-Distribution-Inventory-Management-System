"""Stage 3 — User Management & RBAC tests."""
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


async def _promote_to_admin(email: str) -> str:
    """Set user role to ADMIN in DB and return a fresh access token."""
    async with get_session_local()() as session:
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one()
        user.role = UserRole.ADMIN
        await session.commit()
    return email


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _admin_token(client: AsyncClient, email: str, password: str = "Pass1234") -> str:
    """Register, promote to admin, re-login, return access token."""
    await _register_and_login(client, email, password)
    await _promote_to_admin(email)
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return resp.json()["data"]["access_token"]


# ── /users/me ─────────────────────────────────────────────────────────────────


async def test_get_me_returns_own_profile(client: AsyncClient):
    data = await _register_and_login(client, "me_get@example.com")
    resp = await client.get("/api/v1/users/me", headers=_auth(data["access_token"]))
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["data"]["email"] == "me_get@example.com"
    assert body["data"]["role"] == "customer"


async def test_get_me_requires_auth(client: AsyncClient):
    resp = await client.get("/api/v1/users/me")
    assert resp.status_code == 401  # HTTPBearer: no credentials → 401


async def test_update_me_email(client: AsyncClient):
    data = await _register_and_login(client, "me_update@example.com")
    resp = await client.put(
        "/api/v1/users/me",
        json={"email": "me_updated@example.com"},
        headers=_auth(data["access_token"]),
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["email"] == "me_updated@example.com"


async def test_update_me_duplicate_email_rejected(client: AsyncClient):
    await _register_and_login(client, "taken_email@example.com")
    data = await _register_and_login(client, "wants_taken@example.com")
    resp = await client.put(
        "/api/v1/users/me",
        json={"email": "taken_email@example.com"},
        headers=_auth(data["access_token"]),
    )
    assert resp.status_code == 409


# ── admin CRUD ────────────────────────────────────────────────────────────────


async def test_list_users_requires_admin(client: AsyncClient):
    data = await _register_and_login(client, "non_admin_list@example.com")
    resp = await client.get("/api/v1/users", headers=_auth(data["access_token"]))
    assert resp.status_code == 403


async def test_list_users_as_admin(client: AsyncClient):
    token = await _admin_token(client, "admin_list@example.com")
    resp = await client.get("/api/v1/users", headers=_auth(token))
    assert resp.status_code == 200
    users = resp.json()["data"]
    assert isinstance(users, list)
    assert len(users) >= 1


async def test_get_user_as_admin(client: AsyncClient):
    target = await _register_and_login(client, "target_get@example.com")
    token = await _admin_token(client, "admin_get_user@example.com")

    resp = await client.get(f"/api/v1/users/{target['user_id']}", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.json()["data"]["id"] == target["user_id"]


async def test_get_user_404_for_unknown_id(client: AsyncClient):
    token = await _admin_token(client, "admin_404@example.com")
    resp = await client.get(f"/api/v1/users/{uuid.uuid4()}", headers=_auth(token))
    assert resp.status_code == 404


async def test_admin_can_change_user_role(client: AsyncClient):
    target = await _register_and_login(client, "role_change_target@example.com")
    token = await _admin_token(client, "admin_role_change@example.com")

    resp = await client.put(
        f"/api/v1/users/{target['user_id']}",
        json={"role": "inventory_manager"},
        headers=_auth(token),
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["role"] == "inventory_manager"


async def test_admin_can_deactivate_user(client: AsyncClient):
    target = await _register_and_login(client, "deactivate_target@example.com")
    token = await _admin_token(client, "admin_deactivate@example.com")

    resp = await client.put(
        f"/api/v1/users/{target['user_id']}",
        json={"is_active": False},
        headers=_auth(token),
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["is_active"] is False


async def test_admin_soft_delete_user(client: AsyncClient):
    target = await _register_and_login(client, "delete_target@example.com")
    token = await _admin_token(client, "admin_delete@example.com")

    resp = await client.delete(f"/api/v1/users/{target['user_id']}", headers=_auth(token))
    assert resp.status_code == 204


async def test_non_admin_cannot_delete_user(client: AsyncClient):
    target = await _register_and_login(client, "nodelete_target@example.com")
    attacker = await _register_and_login(client, "attacker_delete@example.com")

    resp = await client.delete(
        f"/api/v1/users/{target['user_id']}",
        headers=_auth(attacker["access_token"]),
    )
    assert resp.status_code == 403


# ── role isolation ────────────────────────────────────────────────────────────


async def test_each_non_admin_role_cannot_access_admin_endpoints(client: AsyncClient):
    """inventory_manager, sales_representative, warehouse_staff, customer all get 403."""
    roles_to_test = [
        UserRole.INVENTORY_MANAGER,
        UserRole.SALES_REPRESENTATIVE,
        UserRole.WAREHOUSE_STAFF,
        UserRole.CUSTOMER,
    ]
    for role in roles_to_test:
        email = f"rbac_{role.value}@example.com"
        await _register_and_login(client, email)

        async with get_session_local()() as session:
            result = await session.execute(select(User).where(User.email == email))
            u = result.scalar_one()
            u.role = role
            await session.commit()

        login_resp = await client.post(
            "/api/v1/auth/login", json={"email": email, "password": "Pass1234"}
        )
        token = login_resp.json()["data"]["access_token"]

        resp = await client.get("/api/v1/users", headers=_auth(token))
        assert resp.status_code == 403, f"role {role.value} should be forbidden on GET /users"
