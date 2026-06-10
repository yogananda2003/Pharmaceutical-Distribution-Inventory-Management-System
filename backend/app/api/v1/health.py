from typing import Any

from fastapi import APIRouter

from app.core.responses import success_envelope

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict[str, Any]:
    return success_envelope({"status": "ok"})
