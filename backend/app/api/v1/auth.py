from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.core.db import AsyncSession, get_db
from app.core.responses import success_envelope
from app.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    RegisterRequest,
)
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


def _svc(session: AsyncSession = Depends(get_db)) -> AuthService:
    return AuthService(session)


@router.post("/login", response_model=None)
async def login(
    request: Request,
    body: LoginRequest,
    svc: AuthService = Depends(_svc),
) -> dict[str, object]:
    try:
        result = await svc.login(body.email, body.password)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    return success_envelope(result.model_dump())


@router.post("/refresh", response_model=None)
async def refresh(
    body: RefreshRequest,
    svc: AuthService = Depends(_svc),
) -> dict[str, object]:
    try:
        result = await svc.refresh(body.refresh_token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    return success_envelope(result.model_dump())


@router.post("/logout", response_model=None)
async def logout(
    body: LogoutRequest,
    svc: AuthService = Depends(_svc),
) -> dict[str, object]:
    await svc.logout(body.refresh_token)
    return success_envelope({"message": "logged out"})


@router.post("/register", response_model=None, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    svc: AuthService = Depends(_svc),
) -> dict[str, object]:
    try:
        user_id = await svc.register(email=body.email, password=body.password)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return success_envelope({"user_id": str(user_id)})
