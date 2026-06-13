"""Stage 13 — Expiry Management & Alerts tests.

Tests verify:
- GET /expiry/dashboard returns correct expired/30d/60d/90d counts
- GET /expiry/expired returns batches with expiry_date < today only
- GET /expiry/near-expiry?days=30 returns batches expiring today..+30d
- GET /expiry/near-expiry?days=60 and ?days=90 work correctly
- EXHAUSTED batches excluded from near-expiry results
- Expired batches excluded from near-expiry results (and vice-versa)
- Batch expiring exactly today is in near-expiry critical (not expired)
- Batch expiring exactly at 30-day boundary is in the 30d window
- Invalid threshold days → 400
- Celery task 'expiry_alerts.scan' is registered
- Role checks: ADMIN, INVENTORY_MANAGER, WAREHOUSE_STAFF can view; SALES_REP denied; unauth → 401
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest
from freezegun import freeze_time
from httpx import AsyncClient
from sqlalchemy import select

from app.core.db import get_session_local
from app.models.inventory_batch import BatchStatus, InventoryBatch
from app.models.user import User, UserRole

pytestmark = pytest.mark.asyncio(loop_scope="session")

_TODAY = "2026-06-12"
_TODAY_DATE = date(2026, 6, 12)


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
    return await _token_for_role(client, f"inv13_{suffix}@example.com", UserRole.INVENTORY_MANAGER)


async def _wh_token(client: AsyncClient, suffix: str) -> str:
    return await _token_for_role(client, f"wh13_{suffix}@example.com", UserRole.WAREHOUSE_STAFF)


async def _sales_token(client: AsyncClient, suffix: str) -> str:
    return await _token_for_role(
        client, f"sales13_{suffix}@example.com", UserRole.SALES_REPRESENTATIVE
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


async def _create_batch(
    client: AsyncClient,
    token: str,
    medicine_id: str,
    warehouse_id: str,
    *,
    batch_number: str,
    expiry_date: str,
    qty: int = 100,
) -> str:
    resp = await client.post(
        "/api/v1/inventory/batches",
        json={
            "medicine_id": medicine_id,
            "warehouse_id": warehouse_id,
            "batch_number": batch_number,
            "expiry_date": expiry_date,
            "initial_quantity": qty,
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


async def _exhaust_batch(batch_id: str) -> None:
    """Directly set batch status to EXHAUSTED via DB for test isolation."""
    async with get_session_local()() as session:
        result = await session.execute(
            select(InventoryBatch).where(InventoryBatch.id == uuid.UUID(batch_id))
        )
        batch = result.scalar_one()
        batch.status = BatchStatus.EXHAUSTED
        await session.commit()


def _date_str(delta_days: int) -> str:
    return (_TODAY_DATE + timedelta(days=delta_days)).isoformat()


# ── stage 13 tests ─────────────────────────────────────────────────────────────


@freeze_time(_TODAY)
async def test_expired_batch_appears_in_expired_list(client: AsyncClient) -> None:
    tok = await _inv_token(client, "exp1")
    med = await _create_medicine(client, tok, f"EXP1{uuid.uuid4().hex[:4]}")
    wh = await _create_warehouse(client, tok, f"EWH1{uuid.uuid4().hex[:4]}")
    await _create_batch(
        client,
        tok,
        med,
        wh,
        batch_number="EXP-001",
        expiry_date=_date_str(-10),  # 10 days ago
    )

    resp = await client.get("/api/v1/expiry/expired", headers=_auth(tok))
    assert resp.status_code == 200
    data = resp.json()["data"]
    batch_ids = [b["medicine_id"] for b in data]
    assert med in batch_ids


@freeze_time(_TODAY)
async def test_future_batch_not_in_expired_list(client: AsyncClient) -> None:
    tok = await _inv_token(client, "exp2")
    med = await _create_medicine(client, tok, f"FUT1{uuid.uuid4().hex[:4]}")
    wh = await _create_warehouse(client, tok, f"FWH1{uuid.uuid4().hex[:4]}")
    await _create_batch(
        client,
        tok,
        med,
        wh,
        batch_number="FUT-001",
        expiry_date=_date_str(45),  # 45 days in future
    )

    resp = await client.get("/api/v1/expiry/expired", headers=_auth(tok))
    assert resp.status_code == 200
    data = resp.json()["data"]
    medicine_ids = [b["medicine_id"] for b in data]
    assert med not in medicine_ids


@freeze_time(_TODAY)
async def test_batch_expiring_today_not_in_expired_list(client: AsyncClient) -> None:
    """Batch expiring exactly today (0 days) goes to near-expiry critical, NOT expired."""
    tok = await _inv_token(client, "today1")
    med = await _create_medicine(client, tok, f"TD1{uuid.uuid4().hex[:4]}")
    wh = await _create_warehouse(client, tok, f"TWH1{uuid.uuid4().hex[:4]}")
    await _create_batch(
        client,
        tok,
        med,
        wh,
        batch_number="TODAY-001",
        expiry_date=_date_str(0),  # expires today
    )

    resp = await client.get("/api/v1/expiry/expired", headers=_auth(tok))
    assert resp.status_code == 200
    medicine_ids = [b["medicine_id"] for b in resp.json()["data"]]
    assert med not in medicine_ids


@freeze_time(_TODAY)
async def test_batch_expiring_today_in_near_expiry_30d(client: AsyncClient) -> None:
    """Batch expiring exactly today appears in near-expiry with alert_level=critical."""
    tok = await _inv_token(client, "today2")
    med = await _create_medicine(client, tok, f"TD2{uuid.uuid4().hex[:4]}")
    wh = await _create_warehouse(client, tok, f"TWH2{uuid.uuid4().hex[:4]}")
    await _create_batch(
        client,
        tok,
        med,
        wh,
        batch_number="TODAY-002",
        expiry_date=_date_str(0),
    )

    resp = await client.get("/api/v1/expiry/near-expiry?days=30", headers=_auth(tok))
    assert resp.status_code == 200
    batches = resp.json()["data"]
    match = next((b for b in batches if b["medicine_id"] == med), None)
    assert match is not None
    assert match["alert_level"] == "critical"
    assert match["days_to_expiry"] == 0


@freeze_time(_TODAY)
async def test_batch_at_30d_boundary_in_near_expiry(client: AsyncClient) -> None:
    """Batch expiring exactly 30 days from today is included in the 30-day window."""
    tok = await _inv_token(client, "bnd1")
    med = await _create_medicine(client, tok, f"BND1{uuid.uuid4().hex[:4]}")
    wh = await _create_warehouse(client, tok, f"BWH1{uuid.uuid4().hex[:4]}")
    await _create_batch(
        client,
        tok,
        med,
        wh,
        batch_number="BND-001",
        expiry_date=_date_str(30),
    )

    resp = await client.get("/api/v1/expiry/near-expiry?days=30", headers=_auth(tok))
    assert resp.status_code == 200
    medicine_ids = [b["medicine_id"] for b in resp.json()["data"]]
    assert med in medicine_ids


@freeze_time(_TODAY)
async def test_batch_at_31d_not_in_30d_window(client: AsyncClient) -> None:
    """Batch expiring 31 days from today is excluded from the 30-day window."""
    tok = await _inv_token(client, "bnd2")
    med = await _create_medicine(client, tok, f"BND2{uuid.uuid4().hex[:4]}")
    wh = await _create_warehouse(client, tok, f"BWH2{uuid.uuid4().hex[:4]}")
    await _create_batch(
        client,
        tok,
        med,
        wh,
        batch_number="BND-002",
        expiry_date=_date_str(31),
    )

    resp = await client.get("/api/v1/expiry/near-expiry?days=30", headers=_auth(tok))
    assert resp.status_code == 200
    medicine_ids = [b["medicine_id"] for b in resp.json()["data"]]
    assert med not in medicine_ids


@freeze_time(_TODAY)
async def test_near_expiry_60d_includes_45d_batch(client: AsyncClient) -> None:
    tok = await _inv_token(client, "60d1")
    med = await _create_medicine(client, tok, f"N60{uuid.uuid4().hex[:4]}")
    wh = await _create_warehouse(client, tok, f"WH60{uuid.uuid4().hex[:4]}")
    await _create_batch(
        client,
        tok,
        med,
        wh,
        batch_number="N60-001",
        expiry_date=_date_str(45),
    )

    resp60 = await client.get("/api/v1/expiry/near-expiry?days=60", headers=_auth(tok))
    assert resp60.status_code == 200
    ids60 = [b["medicine_id"] for b in resp60.json()["data"]]
    assert med in ids60

    resp30 = await client.get("/api/v1/expiry/near-expiry?days=30", headers=_auth(tok))
    assert resp30.status_code == 200
    ids30 = [b["medicine_id"] for b in resp30.json()["data"]]
    assert med not in ids30


@freeze_time(_TODAY)
async def test_near_expiry_90d_includes_75d_batch(client: AsyncClient) -> None:
    tok = await _inv_token(client, "90d1")
    med = await _create_medicine(client, tok, f"N90{uuid.uuid4().hex[:4]}")
    wh = await _create_warehouse(client, tok, f"WH90{uuid.uuid4().hex[:4]}")
    await _create_batch(
        client,
        tok,
        med,
        wh,
        batch_number="N90-001",
        expiry_date=_date_str(75),
    )

    resp = await client.get("/api/v1/expiry/near-expiry?days=90", headers=_auth(tok))
    assert resp.status_code == 200
    ids = [b["medicine_id"] for b in resp.json()["data"]]
    assert med in ids


@freeze_time(_TODAY)
async def test_exhausted_batch_not_in_near_expiry(client: AsyncClient) -> None:
    tok = await _inv_token(client, "exh1")
    med = await _create_medicine(client, tok, f"EH1{uuid.uuid4().hex[:4]}")
    wh = await _create_warehouse(client, tok, f"EHW1{uuid.uuid4().hex[:4]}")
    batch_id = await _create_batch(
        client,
        tok,
        med,
        wh,
        batch_number="EXH-001",
        expiry_date=_date_str(20),
    )
    await _exhaust_batch(batch_id)

    resp = await client.get("/api/v1/expiry/near-expiry?days=30", headers=_auth(tok))
    assert resp.status_code == 200
    ids = [b["medicine_id"] for b in resp.json()["data"]]
    assert med not in ids


@freeze_time(_TODAY)
async def test_expired_batch_not_in_near_expiry(client: AsyncClient) -> None:
    """Expired batch (expiry_date < today) must NOT appear in near-expiry results."""
    tok = await _inv_token(client, "exp3")
    med = await _create_medicine(client, tok, f"EXP3{uuid.uuid4().hex[:4]}")
    wh = await _create_warehouse(client, tok, f"EXW3{uuid.uuid4().hex[:4]}")
    await _create_batch(
        client,
        tok,
        med,
        wh,
        batch_number="EXP-003",
        expiry_date=_date_str(-5),
    )

    resp = await client.get("/api/v1/expiry/near-expiry?days=90", headers=_auth(tok))
    assert resp.status_code == 200
    ids = [b["medicine_id"] for b in resp.json()["data"]]
    assert med not in ids


@freeze_time(_TODAY)
async def test_near_expiry_alert_levels(client: AsyncClient) -> None:
    """Verify alert levels: critical (<=30d), warning (31-60d), caution (61-90d)."""
    tok = await _inv_token(client, "lvl1")
    med_c = await _create_medicine(client, tok, f"LVC{uuid.uuid4().hex[:4]}")
    med_w = await _create_medicine(client, tok, f"LVW{uuid.uuid4().hex[:4]}")
    med_ca = await _create_medicine(client, tok, f"LVA{uuid.uuid4().hex[:4]}")
    wh = await _create_warehouse(client, tok, f"LWH{uuid.uuid4().hex[:4]}")

    await _create_batch(client, tok, med_c, wh, batch_number="LVC-001", expiry_date=_date_str(15))
    await _create_batch(client, tok, med_w, wh, batch_number="LVW-001", expiry_date=_date_str(45))
    await _create_batch(client, tok, med_ca, wh, batch_number="LVA-001", expiry_date=_date_str(75))

    resp = await client.get("/api/v1/expiry/near-expiry?days=90", headers=_auth(tok))
    assert resp.status_code == 200
    batches = {b["medicine_id"]: b for b in resp.json()["data"]}

    assert batches[med_c]["alert_level"] == "critical"
    assert batches[med_w]["alert_level"] == "warning"
    assert batches[med_ca]["alert_level"] == "caution"


@freeze_time(_TODAY)
async def test_expired_batch_has_negative_days_to_expiry(client: AsyncClient) -> None:
    tok = await _inv_token(client, "neg1")
    med = await _create_medicine(client, tok, f"NEG{uuid.uuid4().hex[:4]}")
    wh = await _create_warehouse(client, tok, f"NWH{uuid.uuid4().hex[:4]}")
    await _create_batch(
        client,
        tok,
        med,
        wh,
        batch_number="NEG-001",
        expiry_date=_date_str(-7),
    )

    resp = await client.get("/api/v1/expiry/expired", headers=_auth(tok))
    assert resp.status_code == 200
    match = next((b for b in resp.json()["data"] if b["medicine_id"] == med), None)
    assert match is not None
    assert match["days_to_expiry"] == -7
    assert match["alert_level"] == "expired"


@freeze_time(_TODAY)
async def test_dashboard_counts(client: AsyncClient) -> None:
    """dashboard expired_count and expiring_within_30d/60d/90d reflect created batches."""
    tok = await _inv_token(client, "dash1")
    wh = await _create_warehouse(client, tok, f"DWH{uuid.uuid4().hex[:4]}")
    med_exp = await _create_medicine(client, tok, f"DEXP{uuid.uuid4().hex[:4]}")
    med_30 = await _create_medicine(client, tok, f"D30{uuid.uuid4().hex[:4]}")
    med_60 = await _create_medicine(client, tok, f"D60{uuid.uuid4().hex[:4]}")
    med_90 = await _create_medicine(client, tok, f"D90{uuid.uuid4().hex[:4]}")

    await _create_batch(client, tok, med_exp, wh, batch_number="D-EXP", expiry_date=_date_str(-3))
    await _create_batch(client, tok, med_30, wh, batch_number="D-30", expiry_date=_date_str(20))
    await _create_batch(client, tok, med_60, wh, batch_number="D-60", expiry_date=_date_str(50))
    await _create_batch(client, tok, med_90, wh, batch_number="D-90", expiry_date=_date_str(80))

    resp = await client.get("/api/v1/expiry/dashboard", headers=_auth(tok))
    assert resp.status_code == 200
    dash = resp.json()["data"]

    # The DB may have batches from other tests; we assert ours are included (>=)
    assert dash["expired_count"] >= 1
    assert dash["expiring_within_30d"] >= 1
    assert dash["expiring_within_60d"] >= 2
    assert dash["expiring_within_90d"] >= 3
    assert dash["as_of"] == _TODAY


@freeze_time(_TODAY)
async def test_dashboard_90d_ge_60d_ge_30d(client: AsyncClient) -> None:
    """Dashboard 90d count >= 60d count >= 30d count (cumulative windows)."""
    tok = await _inv_token(client, "dash2")

    resp = await client.get("/api/v1/expiry/dashboard", headers=_auth(tok))
    assert resp.status_code == 200
    dash = resp.json()["data"]
    assert dash["expiring_within_90d"] >= dash["expiring_within_60d"]
    assert dash["expiring_within_60d"] >= dash["expiring_within_30d"]


@freeze_time(_TODAY)
async def test_near_expiry_invalid_days_returns_400(client: AsyncClient) -> None:
    tok = await _inv_token(client, "inv1")

    resp = await client.get("/api/v1/expiry/near-expiry?days=45", headers=_auth(tok))
    assert resp.status_code == 400


@freeze_time(_TODAY)
async def test_near_expiry_invalid_days_7_returns_400(client: AsyncClient) -> None:
    tok = await _inv_token(client, "inv2")

    resp = await client.get("/api/v1/expiry/near-expiry?days=7", headers=_auth(tok))
    assert resp.status_code == 400


# ── role checks ────────────────────────────────────────────────────────────────


@freeze_time(_TODAY)
async def test_warehouse_staff_can_view_expired(client: AsyncClient) -> None:
    tok = await _wh_token(client, "vw1")
    resp = await client.get("/api/v1/expiry/expired", headers=_auth(tok))
    assert resp.status_code == 200


@freeze_time(_TODAY)
async def test_warehouse_staff_can_view_near_expiry(client: AsyncClient) -> None:
    tok = await _wh_token(client, "vw2")
    resp = await client.get("/api/v1/expiry/near-expiry?days=30", headers=_auth(tok))
    assert resp.status_code == 200


@freeze_time(_TODAY)
async def test_warehouse_staff_can_view_dashboard(client: AsyncClient) -> None:
    tok = await _wh_token(client, "vw3")
    resp = await client.get("/api/v1/expiry/dashboard", headers=_auth(tok))
    assert resp.status_code == 200


@freeze_time(_TODAY)
async def test_sales_rep_cannot_view_expiry_endpoints(client: AsyncClient) -> None:
    tok = await _sales_token(client, "role1")
    paths = [
        "/api/v1/expiry/expired",
        "/api/v1/expiry/near-expiry?days=30",
        "/api/v1/expiry/dashboard",
    ]
    for path in paths:
        resp = await client.get(path, headers=_auth(tok))
        assert resp.status_code == 403, f"Expected 403 for {path}, got {resp.status_code}"


async def test_unauthenticated_returns_401(client: AsyncClient) -> None:
    paths = [
        "/api/v1/expiry/expired",
        "/api/v1/expiry/near-expiry?days=30",
        "/api/v1/expiry/dashboard",
    ]
    for path in paths:
        resp = await client.get(path)
        assert resp.status_code == 401, f"Expected 401 for {path}, got {resp.status_code}"


# ── celery task registration ───────────────────────────────────────────────────


def test_celery_task_registered() -> None:
    """Verify the expiry scan task is registered with the Celery app."""
    import app.workers.expiry_alerts  # noqa: F401 — registers tasks with celery_app
    from app.workers.celery_app import celery_app

    assert "expiry_alerts.scan" in celery_app.tasks
