from typing import Any

from pydantic import BaseModel


class SuccessEnvelope[T](BaseModel):
    success: bool = True
    data: T


class ErrorEnvelope(BaseModel):
    success: bool = False
    message: str


def success_envelope(data: Any) -> dict[str, Any]:
    return {"success": True, "data": data}


def error_envelope(message: str) -> dict[str, Any]:
    return {"success": False, "message": message}
