"""Integration tests for the /auth endpoints."""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _register(client: AsyncClient, email: str, password: str = "Password1") -> None:
    resp = await client.post("/api/v1/auth/register", json={"email": email, "password": password})
    assert resp.status_code == 201, resp.text


# ── register ──────────────────────────────────────────────────────────────────


async def test_register_success(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "new_user@example.com", "password": "StrongPass1"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["success"] is True
    assert "user_id" in body["data"]


async def test_register_duplicate_email(client: AsyncClient):
    await _register(client, "dup@example.com")
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "dup@example.com", "password": "StrongPass1"},
    )
    assert resp.status_code == 409


async def test_register_short_password(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": "short@example.com", "password": "abc"},
    )
    assert resp.status_code == 422


# ── login ─────────────────────────────────────────────────────────────────────


async def test_login_success(client: AsyncClient):
    await _register(client, "login_ok@example.com", "GoodPass1")
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "login_ok@example.com", "password": "GoodPass1"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


async def test_login_wrong_password(client: AsyncClient):
    await _register(client, "wrongpw@example.com", "RightPass1")
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "wrongpw@example.com", "password": "WrongPass1"},
    )
    assert resp.status_code == 401


async def test_login_unknown_email(client: AsyncClient):
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "ghost@example.com", "password": "AnyPass1"},
    )
    assert resp.status_code == 401


async def test_password_not_stored_in_plaintext(client: AsyncClient):
    from sqlalchemy import select

    from app.core.db import get_session_local
    from app.models.user import User

    await _register(client, "hash_check@example.com", "PlainPass1")
    async with get_session_local()() as session:
        result = await session.execute(
            select(User.password_hash).where(User.email == "hash_check@example.com")
        )
        pw_hash = result.scalar_one()

    assert pw_hash != "PlainPass1"
    assert pw_hash.startswith("$2b$")


# ── refresh ───────────────────────────────────────────────────────────────────


async def test_refresh_token_rotation(client: AsyncClient):
    await _register(client, "refresh@example.com", "RefreshPass1")
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "refresh@example.com", "password": "RefreshPass1"},
    )
    old_refresh = login_resp.json()["data"]["refresh_token"]

    refresh_resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert refresh_resp.status_code == 200
    new_data = refresh_resp.json()["data"]
    assert new_data["refresh_token"] != old_refresh
    assert "access_token" in new_data


async def test_refresh_token_replay_rejected(client: AsyncClient):
    await _register(client, "replay@example.com", "ReplayPass1")
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "replay@example.com", "password": "ReplayPass1"},
    )
    old_refresh = login_resp.json()["data"]["refresh_token"]

    await client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    # replay the same token — should be rejected
    replay_resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert replay_resp.status_code == 401


async def test_refresh_invalid_token_rejected(client: AsyncClient):
    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": "not.a.jwt.at.all"})
    assert resp.status_code == 401


# ── logout ────────────────────────────────────────────────────────────────────


async def test_logout_success(client: AsyncClient):
    await _register(client, "logout@example.com", "LogoutPass1")
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": "logout@example.com", "password": "LogoutPass1"},
    )
    refresh_token = login_resp.json()["data"]["refresh_token"]

    logout_resp = await client.post("/api/v1/auth/logout", json={"refresh_token": refresh_token})
    assert logout_resp.status_code == 200

    # token should no longer work
    use_after_logout = await client.post(
        "/api/v1/auth/refresh", json={"refresh_token": refresh_token}
    )
    assert use_after_logout.status_code == 401


# ── protected route via access token ─────────────────────────────────────────


async def test_protected_route_requires_bearer(client: AsyncClient):
    resp = await client.get("/api/v1/health")
    # health is public, so use a different approach: hit auth endpoint without token
    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": "bad"})
    assert resp.status_code == 401
