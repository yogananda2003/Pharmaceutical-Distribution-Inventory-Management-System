from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, EmailStr

from app.models.user import UserRole


class UserRead(BaseModel):
    id: UUID
    email: str
    role: UserRole
    is_active: bool
    is_verified: bool
    tenant_id: UUID | None = None

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    is_active: bool | None = None
    role: UserRole | None = None


class UserUpdateMe(BaseModel):
    email: EmailStr | None = None
