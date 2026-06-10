"""Stage 7 — FEFO Allocation Engine tests.

Tests verify:
- Earliest-expiry batch consumed first
- Partial-fill spills across batches in expiry order
- Expired batches excluded from allocation
- Exhausted/non-active batches excluded
- All-or-nothing: insufficient stock → 400, no stock reserved
- One ALLOCATION transaction created per batch touched
- Quantities (available ↓, reserved ↑) correct after allocation
- Warehouse filter respected
- Concurrent allocations: only one wins when last unit is contested
- FEFO release: RELEASE transactions created, quantities restored
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import date, timedelta

import pytest
from freezegun import freeze_time
from httpx import AsyncClient
from sqlalchemy import select

from app.core.db import get_session_local
from app.models.user import User, UserRole

pytestmark = pytest.mark.asyncio(loop_scope="session")

_TODAY = date(2026, 6, 10)
_YESTERDAY = _TODAY - timedelta(days=1)
_SOON = _TODAY + timedelta(days=30)   # earlier expiry
_LATER = _TODAY + timedelta(days=90)  # later expiry
_FAR = date(2028, 12, 31)


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
    resp = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": "Pass1234"}
    )
    return resp.json()["data"]["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _inv_token(client: AsyncClient, suffix: str) -> str:
    return await _token_for_role(
        client, f"fefo_inv_{suffix}@example.com", UserRole.INVENTORY_MANAGER
    )


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


async def _create_batch(
    client: AsyncClient,
    token: str,
    medicine_id: str,
    warehouse_id: str,
    *,
    batch_number: str,
    expiry_date: str,
    initial_quantity: int = 0,
) -> dict:
    resp = await client.post(
        "/api/v1/inventory/batches",
        json={
            "medicine_id": medicine_id,
            "warehouse_id": warehouse_id,
            "batch_number": batch_number,
            "expiry_date": expiry_date,
            "initial_quantity": initial_quantity,
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


async def _fefo_allocate(
    client: AsyncClient,
    token: str,
    medicine_id: str,
    quantity: int,
    *,
    warehouse_id: str | None = None,
    reference_number: str | None = None,
) -> dict:
    body: dict = {"medicine_id": medicine_id, "quantity": quantity}
    if warehouse_id:
        body["warehouse_id"] = warehouse_id
    if reference_number:
        body["reference_number"] = reference_number
    return await client.post(
        "/api/v1/inventory/fefo/allocate",
        json=body,
        headers=_auth(token),
    )


# ── single-batch allocation ────────────────────────────────────────────────────


@freeze_time("2026-06-10")
async def test_fefo_allocates_from_single_batch(client: AsyncClient):
    token = await _inv_token(client, "single")
    mid = await _create_medicine(client, token, "FEFO-M-S1")
    wid = await _create_warehouse(client, token, "FEFO-W-S1")
    await _create_batch(
        client, token, mid, wid,
        batch_number="S1-BATCH", expiry_date=str(_FAR), initial_quantity=50
    )
    resp = await _fefo_allocate(client, token, mid, 20)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total_quantity_requested"] == 20
    assert data["total_quantity_allocated"] == 20
    assert len(data["allocations"]) == 1
    assert data["allocations"][0]["quantity_allocated"] == 20


# ── earliest expiry consumed first ────────────────────────────────────────────


@freeze_time("2026-06-10")
async def test_fefo_earliest_expiry_consumed_first(client: AsyncClient):
    """Two batches: batch with earlier expiry must be consumed before the later one."""
    token = await _inv_token(client, "fefo_order")
    mid = await _create_medicine(client, token, "FEFO-M-E1")
    wid = await _create_warehouse(client, token, "FEFO-W-E1")
    # Create LATER batch first (to ensure ordering is by expiry, not creation time)
    later = await _create_batch(
        client, token, mid, wid,
        batch_number="E1-LATER", expiry_date=str(_LATER), initial_quantity=20
    )
    soon = await _create_batch(
        client, token, mid, wid,
        batch_number="E1-SOON", expiry_date=str(_SOON), initial_quantity=20
    )

    resp = await _fefo_allocate(client, token, mid, 15)
    assert resp.status_code == 200
    allocs = resp.json()["data"]["allocations"]

    # Must allocate entirely from the earlier-expiry batch
    assert len(allocs) == 1
    assert allocs[0]["batch_id"] == soon["id"]
    assert allocs[0]["quantity_allocated"] == 15

    # The later batch must remain untouched
    later_resp = await client.get(
        f"/api/v1/inventory/batches/{later['id']}", headers=_auth(token)
    )
    assert later_resp.json()["data"]["quantity_available"] == 20
    assert later_resp.json()["data"]["quantity_reserved"] == 0


# ── partial fill spills to next batch ─────────────────────────────────────────


@freeze_time("2026-06-10")
async def test_fefo_partial_fill_spills_to_next_batch(client: AsyncClient):
    """First batch has 8 units; request 13 → 8 from first, 5 from second."""
    token = await _inv_token(client, "spill")
    mid = await _create_medicine(client, token, "FEFO-M-SP")
    wid = await _create_warehouse(client, token, "FEFO-W-SP")
    b1 = await _create_batch(
        client, token, mid, wid,
        batch_number="SP-BATCH1", expiry_date=str(_SOON), initial_quantity=8
    )
    b2 = await _create_batch(
        client, token, mid, wid,
        batch_number="SP-BATCH2", expiry_date=str(_LATER), initial_quantity=10
    )

    resp = await _fefo_allocate(client, token, mid, 13)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total_quantity_allocated"] == 13
    assert len(data["allocations"]) == 2

    alloc_map = {a["batch_id"]: a["quantity_allocated"] for a in data["allocations"]}
    assert alloc_map[b1["id"]] == 8
    assert alloc_map[b2["id"]] == 5


@freeze_time("2026-06-10")
async def test_fefo_three_batch_spill(client: AsyncClient):
    """Request spans all three batches in expiry order."""
    token = await _inv_token(client, "spill3")
    mid = await _create_medicine(client, token, "FEFO-M-SP3")
    wid = await _create_warehouse(client, token, "FEFO-W-SP3")
    exp1 = _TODAY + timedelta(days=10)
    exp2 = _TODAY + timedelta(days=20)
    exp3 = _TODAY + timedelta(days=30)
    b1 = await _create_batch(
        client, token, mid, wid,
        batch_number="SP3-B1", expiry_date=str(exp1), initial_quantity=5
    )
    b2 = await _create_batch(
        client, token, mid, wid,
        batch_number="SP3-B2", expiry_date=str(exp2), initial_quantity=5
    )
    b3 = await _create_batch(
        client, token, mid, wid,
        batch_number="SP3-B3", expiry_date=str(exp3), initial_quantity=5
    )

    resp = await _fefo_allocate(client, token, mid, 14)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total_quantity_allocated"] == 14
    assert len(data["allocations"]) == 3

    alloc_map = {a["batch_id"]: a["quantity_allocated"] for a in data["allocations"]}
    assert alloc_map[b1["id"]] == 5
    assert alloc_map[b2["id"]] == 5
    assert alloc_map[b3["id"]] == 4


# ── expired batches excluded ──────────────────────────────────────────────────


@freeze_time("2026-06-10")
async def test_fefo_skips_expired_batches(client: AsyncClient):
    """Expired batch has stock but must not be included in FEFO allocation."""
    token = await _inv_token(client, "skip_exp")
    mid = await _create_medicine(client, token, "FEFO-M-EX")
    wid = await _create_warehouse(client, token, "FEFO-W-EX")
    # Expired batch (plenty of stock)
    expired = await _create_batch(
        client, token, mid, wid,
        batch_number="EX-EXPIRED", expiry_date=str(_YESTERDAY), initial_quantity=100
    )
    # Valid batch (limited stock)
    valid = await _create_batch(
        client, token, mid, wid,
        batch_number="EX-VALID", expiry_date=str(_FAR), initial_quantity=10
    )

    resp = await _fefo_allocate(client, token, mid, 5)
    assert resp.status_code == 200
    allocs = resp.json()["data"]["allocations"]
    assert len(allocs) == 1
    assert allocs[0]["batch_id"] == valid["id"]

    # Expired batch must be untouched
    exp_resp = await client.get(
        f"/api/v1/inventory/batches/{expired['id']}", headers=_auth(token)
    )
    assert exp_resp.json()["data"]["quantity_reserved"] == 0


@freeze_time("2026-06-10")
async def test_fefo_all_stock_expired_returns_400(client: AsyncClient):
    """If all batches are expired, allocation fails with 400."""
    token = await _inv_token(client, "all_exp")
    mid = await _create_medicine(client, token, "FEFO-M-AE")
    wid = await _create_warehouse(client, token, "FEFO-W-AE")
    await _create_batch(
        client, token, mid, wid,
        batch_number="AE-BATCH", expiry_date=str(_YESTERDAY), initial_quantity=50
    )

    resp = await _fefo_allocate(client, token, mid, 1)
    assert resp.status_code == 400
    assert "insufficient" in resp.json()["message"].lower()


# ── insufficient stock ────────────────────────────────────────────────────────


@freeze_time("2026-06-10")
async def test_fefo_insufficient_stock_rejected(client: AsyncClient):
    """Request more than total available → 400, no stock reserved."""
    token = await _inv_token(client, "insuf")
    mid = await _create_medicine(client, token, "FEFO-M-IN")
    wid = await _create_warehouse(client, token, "FEFO-W-IN")
    batch = await _create_batch(
        client, token, mid, wid,
        batch_number="IN-BATCH", expiry_date=str(_FAR), initial_quantity=5
    )

    resp = await _fefo_allocate(client, token, mid, 10)
    assert resp.status_code == 400
    assert "insufficient" in resp.json()["message"].lower()

    # No stock must have been reserved
    batch_resp = await client.get(
        f"/api/v1/inventory/batches/{batch['id']}", headers=_auth(token)
    )
    assert batch_resp.json()["data"]["quantity_reserved"] == 0
    assert batch_resp.json()["data"]["quantity_available"] == 5


@freeze_time("2026-06-10")
async def test_fefo_no_batches_at_all_rejected(client: AsyncClient):
    """Medicine with no batches → 400."""
    token = await _inv_token(client, "no_batch")
    mid = await _create_medicine(client, token, "FEFO-M-NB")
    resp = await _fefo_allocate(client, token, mid, 1)
    assert resp.status_code == 400


# ── quantity correctness ──────────────────────────────────────────────────────


@freeze_time("2026-06-10")
async def test_fefo_quantities_correct_after_allocation(client: AsyncClient):
    """available decreases by allocated, reserved increases by allocated."""
    token = await _inv_token(client, "qty_correct")
    mid = await _create_medicine(client, token, "FEFO-M-QC")
    wid = await _create_warehouse(client, token, "FEFO-W-QC")
    batch = await _create_batch(
        client, token, mid, wid,
        batch_number="QC-BATCH", expiry_date=str(_FAR), initial_quantity=30
    )

    await _fefo_allocate(client, token, mid, 12)

    resp = await client.get(
        f"/api/v1/inventory/batches/{batch['id']}", headers=_auth(token)
    )
    data = resp.json()["data"]
    assert data["quantity_available"] == 18
    assert data["quantity_reserved"] == 12


# ── one ALLOCATION transaction per batch ──────────────────────────────────────


@freeze_time("2026-06-10")
async def test_fefo_creates_allocation_transactions_per_batch(client: AsyncClient):
    """FEFO touching 2 batches must create 2 ALLOCATION transactions."""
    token = await _inv_token(client, "txn_per_batch")
    mid = await _create_medicine(client, token, "FEFO-M-TP")
    wid = await _create_warehouse(client, token, "FEFO-W-TP")
    b1 = await _create_batch(
        client, token, mid, wid,
        batch_number="TP-B1", expiry_date=str(_SOON), initial_quantity=5
    )
    b2 = await _create_batch(
        client, token, mid, wid,
        batch_number="TP-B2", expiry_date=str(_LATER), initial_quantity=5
    )

    await _fefo_allocate(client, token, mid, 8)

    for bid, expected_qty in [(b1["id"], 5), (b2["id"], 3)]:
        txn_resp = await client.get(
            f"/api/v1/inventory/batches/{bid}/transactions",
            headers=_auth(token),
        )
        txns = txn_resp.json()["data"]
        alloc_txns = [t for t in txns if t["transaction_type"] == "allocation"]
        assert len(alloc_txns) == 1
        assert alloc_txns[0]["quantity"] == expected_qty


# ── warehouse filter ──────────────────────────────────────────────────────────


@freeze_time("2026-06-10")
async def test_fefo_respects_warehouse_filter(client: AsyncClient):
    """With warehouse_id specified, only batches from that warehouse are used."""
    token = await _inv_token(client, "wh_filter")
    mid = await _create_medicine(client, token, "FEFO-M-WF")
    wid_a = await _create_warehouse(client, token, "FEFO-WH-WF-A")
    wid_b = await _create_warehouse(client, token, "FEFO-WH-WF-B")
    await _create_batch(
        client, token, mid, wid_a,
        batch_number="WF-BATCH-A", expiry_date=str(_FAR), initial_quantity=10
    )
    b_b = await _create_batch(
        client, token, mid, wid_b,
        batch_number="WF-BATCH-B", expiry_date=str(_FAR), initial_quantity=10
    )

    # Request filtered to warehouse B only
    resp = await _fefo_allocate(client, token, mid, 5, warehouse_id=wid_b)
    assert resp.status_code == 200
    allocs = resp.json()["data"]["allocations"]
    assert len(allocs) == 1
    assert allocs[0]["batch_id"] == b_b["id"]


@freeze_time("2026-06-10")
async def test_fefo_warehouse_filter_insufficient_fails(client: AsyncClient):
    """Requesting more than available in the specified warehouse fails."""
    token = await _inv_token(client, "wh_insuf")
    mid = await _create_medicine(client, token, "FEFO-M-WI")
    wid_a = await _create_warehouse(client, token, "FEFO-WH-WI-A")
    wid_b = await _create_warehouse(client, token, "FEFO-WH-WI-B")
    # Lots of stock globally, but only 3 in warehouse A
    await _create_batch(
        client, token, mid, wid_a,
        batch_number="WI-BATCH-A", expiry_date=str(_FAR), initial_quantity=3
    )
    await _create_batch(
        client, token, mid, wid_b,
        batch_number="WI-BATCH-B", expiry_date=str(_FAR), initial_quantity=100
    )

    resp = await _fefo_allocate(client, token, mid, 10, warehouse_id=wid_a)
    assert resp.status_code == 400


# ── FEFO release ──────────────────────────────────────────────────────────────


@freeze_time("2026-06-10")
async def test_fefo_release_restores_quantities(client: AsyncClient):
    """After FEFO allocate then release, quantities return to original values."""
    token = await _inv_token(client, "release")
    mid = await _create_medicine(client, token, "FEFO-M-RL")
    wid = await _create_warehouse(client, token, "FEFO-W-RL")
    batch = await _create_batch(
        client, token, mid, wid,
        batch_number="RL-BATCH", expiry_date=str(_FAR), initial_quantity=20
    )

    alloc_resp = await _fefo_allocate(client, token, mid, 7)
    assert alloc_resp.status_code == 200
    allocs = alloc_resp.json()["data"]["allocations"]

    # Release the allocation
    release_body = {
        "allocations": [
            {"batch_id": a["batch_id"], "quantity": a["quantity_allocated"]}
            for a in allocs
        ],
        "reference_number": "CANCEL-001",
    }
    rel_resp = await client.post(
        "/api/v1/inventory/fefo/release",
        json=release_body,
        headers=_auth(token),
    )
    assert rel_resp.status_code == 204

    # Quantities fully restored
    batch_resp = await client.get(
        f"/api/v1/inventory/batches/{batch['id']}", headers=_auth(token)
    )
    data = batch_resp.json()["data"]
    assert data["quantity_available"] == 20
    assert data["quantity_reserved"] == 0


@freeze_time("2026-06-10")
async def test_fefo_release_creates_release_transactions(client: AsyncClient):
    """Release creates one RELEASE transaction per batch."""
    token = await _inv_token(client, "rel_txn")
    mid = await _create_medicine(client, token, "FEFO-M-RT")
    wid = await _create_warehouse(client, token, "FEFO-W-RT")
    b1 = await _create_batch(
        client, token, mid, wid,
        batch_number="RT-B1", expiry_date=str(_SOON), initial_quantity=5
    )
    b2 = await _create_batch(
        client, token, mid, wid,
        batch_number="RT-B2", expiry_date=str(_LATER), initial_quantity=5
    )

    alloc_resp = await _fefo_allocate(client, token, mid, 8)
    allocs = alloc_resp.json()["data"]["allocations"]

    await client.post(
        "/api/v1/inventory/fefo/release",
        json={"allocations": [
            {"batch_id": a["batch_id"], "quantity": a["quantity_allocated"]}
            for a in allocs
        ]},
        headers=_auth(token),
    )

    for bid in [b1["id"], b2["id"]]:
        txn_resp = await client.get(
            f"/api/v1/inventory/batches/{bid}/transactions",
            headers=_auth(token),
        )
        txns = txn_resp.json()["data"]
        rel_txns = [t for t in txns if t["transaction_type"] == "release"]
        assert len(rel_txns) == 1


@freeze_time("2026-06-10")
async def test_fefo_release_over_reserved_rejected(client: AsyncClient):
    """Cannot release more than is reserved."""
    token = await _inv_token(client, "rel_over")
    mid = await _create_medicine(client, token, "FEFO-M-RO")
    wid = await _create_warehouse(client, token, "FEFO-W-RO")
    batch = await _create_batch(
        client, token, mid, wid,
        batch_number="RO-BATCH", expiry_date=str(_FAR), initial_quantity=10
    )

    await _fefo_allocate(client, token, mid, 3)

    resp = await client.post(
        "/api/v1/inventory/fefo/release",
        json={"allocations": [{"batch_id": batch["id"], "quantity": 10}]},
        headers=_auth(token),
    )
    assert resp.status_code == 400


# ── concurrent FEFO allocation ────────────────────────────────────────────────


@freeze_time("2026-06-10")
async def test_fefo_concurrent_allocation_only_one_wins(client: AsyncClient):
    """Two simultaneous FEFO requests for the last unit: exactly one succeeds."""
    token = await _inv_token(client, "concurrent")
    mid = await _create_medicine(client, token, "FEFO-M-CC")
    wid = await _create_warehouse(client, token, "FEFO-W-CC")
    await _create_batch(
        client, token, mid, wid,
        batch_number="CC-BATCH", expiry_date=str(_FAR), initial_quantity=1
    )

    async def do_allocate() -> int:
        r = await _fefo_allocate(client, token, mid, 1)
        return r.status_code

    codes = await asyncio.gather(do_allocate(), do_allocate())
    assert sorted(codes) == [200, 400]


# ── auth / roles ──────────────────────────────────────────────────────────────


@freeze_time("2026-06-10")
async def test_sales_rep_cannot_fefo_allocate(client: AsyncClient):
    token = await _token_for_role(
        client, "sales_fefo@example.com", UserRole.SALES_REPRESENTATIVE
    )
    resp = await _fefo_allocate(client, token, str(uuid.uuid4()), 1)
    assert resp.status_code == 403


async def test_unauthenticated_cannot_fefo_allocate(client: AsyncClient):
    resp = await client.post(
        "/api/v1/inventory/fefo/allocate",
        json={"medicine_id": str(uuid.uuid4()), "quantity": 1},
    )
    assert resp.status_code == 401


async def test_fefo_zero_quantity_rejected(client: AsyncClient):
    token = await _inv_token(client, "zero_qty")
    resp = await client.post(
        "/api/v1/inventory/fefo/allocate",
        json={"medicine_id": str(uuid.uuid4()), "quantity": 0},
        headers=_auth(token),
    )
    assert resp.status_code == 422
