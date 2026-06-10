from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.db import AsyncSession, get_db
from app.core.deps import CurrentUser, require_roles
from app.core.responses import success_envelope
from app.models.user import UserRole
from app.schemas.user import UserRead, UserUpdate, UserUpdateMe
from app.services.user import UserService

router = APIRouter(prefix="/users", tags=["users"])


def _svc(session: AsyncSession = Depends(get_db)) -> UserService:
    return UserService(session)


# ── self ──────────────────────────────────────────────────────────────────────


@router.get("/me", response_model=None)
async def get_me(current_user: CurrentUser) -> dict[str, object]:
    return success_envelope(UserRead.model_validate(current_user).model_dump())


@router.put("/me", response_model=None)
async def update_me(
    body: UserUpdateMe,
    current_user: CurrentUser,
    svc: UserService = Depends(_svc),
) -> dict[str, object]:
    try:
        user = await svc.update_me(current_user.id, body)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return success_envelope(UserRead.model_validate(user).model_dump())


# ── admin CRUD ────────────────────────────────────────────────────────────────


@router.get(
    "",
    response_model=None,
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
async def list_users(
    limit: int = 100,
    offset: int = 0,
    svc: UserService = Depends(_svc),
) -> dict[str, object]:
    users = await svc.list_users(limit=limit, offset=offset)
    return success_envelope([UserRead.model_validate(u).model_dump() for u in users])


@router.get(
    "/{user_id}",
    response_model=None,
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
async def get_user(user_id: UUID, svc: UserService = Depends(_svc)) -> dict[str, object]:
    try:
        user = await svc.get_user(user_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return success_envelope(UserRead.model_validate(user).model_dump())


@router.put(
    "/{user_id}",
    response_model=None,
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
async def update_user(
    user_id: UUID,
    body: UserUpdate,
    svc: UserService = Depends(_svc),
) -> dict[str, object]:
    try:
        user = await svc.update_user(user_id, body)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT
            if "email" in str(exc)
            else status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc
    return success_envelope(UserRead.model_validate(user).model_dump())


@router.delete(
    "/{user_id}",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_roles(UserRole.ADMIN))],
)
async def delete_user(user_id: UUID, svc: UserService = Depends(_svc)) -> None:
    try:
        await svc.delete_user(user_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
