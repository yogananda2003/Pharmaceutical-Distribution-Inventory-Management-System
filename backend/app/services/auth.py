from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.repositories.refresh_token import RefreshTokenRepository
from app.repositories.user import UserRepository
from app.schemas.auth import LoginResponse

logger = get_logger(__name__)


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._users = UserRepository(session)
        self._tokens = RefreshTokenRepository(session)

    async def login(self, email: str, password: str) -> LoginResponse:
        user = await self._users.get_by_email(email)
        if not user or not verify_password(password, user.password_hash):
            raise ValueError("invalid credentials")
        if not user.is_active:
            raise ValueError("account is disabled")

        raw_refresh, expires_at = create_refresh_token(user.id)
        await self._tokens.create(
            user_id=user.id,
            token_hash=hash_token(raw_refresh),
            expires_at=expires_at,
        )
        await self._session.commit()

        access = create_access_token(user.id, user.role.value)
        logger.info("user_login", user_id=str(user.id), email=email)
        return LoginResponse(
            access_token=access,
            refresh_token=raw_refresh,
            user_id=user.id,
            role=user.role.value,
        )

    async def refresh(self, raw_refresh: str) -> LoginResponse:
        from app.core.security import decode_refresh_token

        try:
            payload = decode_refresh_token(raw_refresh)
        except ValueError as exc:
            raise ValueError("invalid refresh token") from exc

        user_id = UUID(str(payload["sub"]))
        stored = await self._tokens.get_by_hash(hash_token(raw_refresh))
        if not stored:
            raise ValueError("token not found or expired")

        user = await self._users.get_by_id_active(user_id)
        if not user:
            raise ValueError("user not found")

        await self._tokens.revoke(stored)
        new_raw, expires_at = create_refresh_token(user.id)
        await self._tokens.create(
            user_id=user.id,
            token_hash=hash_token(new_raw),
            expires_at=expires_at,
        )
        await self._session.commit()

        access = create_access_token(user.id, user.role.value)
        return LoginResponse(
            access_token=access,
            refresh_token=new_raw,
            user_id=user.id,
            role=user.role.value,
        )

    async def logout(self, raw_refresh: str) -> None:
        stored = await self._tokens.get_by_hash(hash_token(raw_refresh))
        if stored:
            await self._tokens.revoke(stored)
            await self._session.commit()

    async def logout_all(self, user_id: UUID) -> None:
        await self._tokens.revoke_all_for_user(user_id)
        await self._session.commit()

    async def register(
        self,
        *,
        email: str,
        password: str,
        role: str = "customer",
        tenant_id: UUID | None = None,
    ) -> UUID:
        existing = await self._users.get_by_email(email)
        if existing:
            raise ValueError("email already registered")
        user = await self._users.create(
            email=email,
            password_hash=hash_password(password),
            role=role,
            tenant_id=tenant_id,
        )
        await self._session.commit()
        logger.info("user_registered", user_id=str(user.id), email=email)
        return user.id
