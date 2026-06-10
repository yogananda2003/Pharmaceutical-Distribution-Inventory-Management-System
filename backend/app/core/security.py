from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from uuid import UUID

import bcrypt
from jose import JWTError, jwt

from app.core.config import get_settings


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


def hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


def create_access_token(subject: UUID, role: str) -> str:
    settings = get_settings()
    expire = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    payload: dict[str, object] = {
        "sub": str(subject),
        "role": role,
        "exp": expire,
        "iat": datetime.now(UTC),
        "type": "access",
    }
    return str(jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm))


def create_refresh_token(subject: UUID) -> tuple[str, datetime]:
    settings = get_settings()
    expire = datetime.now(UTC) + timedelta(days=settings.refresh_token_expire_days)
    payload: dict[str, object] = {
        "sub": str(subject),
        "jti": str(uuid.uuid4()),  # guarantees uniqueness even within the same second
        "exp": expire,
        "iat": datetime.now(UTC),
        "type": "refresh",
    }
    raw = str(jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm))
    return raw, expire


def decode_access_token(token: str) -> dict[str, object]:
    settings = get_settings()
    try:
        payload: dict[str, object] = jwt.decode(
            token, settings.secret_key, algorithms=[settings.jwt_algorithm]
        )
        if payload.get("type") != "access":
            raise JWTError("wrong token type")
        return payload
    except JWTError as exc:
        raise ValueError(str(exc)) from exc


def decode_refresh_token(token: str) -> dict[str, object]:
    settings = get_settings()
    try:
        payload: dict[str, object] = jwt.decode(
            token, settings.secret_key, algorithms=[settings.jwt_algorithm]
        )
        if payload.get("type") != "refresh":
            raise JWTError("wrong token type")
        return payload
    except JWTError as exc:
        raise ValueError(str(exc)) from exc
