import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_health_check_returns_success_envelope(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")

    assert response.status_code == 200
    body = response.json()
    assert body == {"success": True, "data": {"status": "ok"}}


async def test_health_check_includes_request_id_header(client: AsyncClient) -> None:
    response = await client.get("/api/v1/health")

    assert "X-Request-ID" in response.headers
