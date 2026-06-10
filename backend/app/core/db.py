from collections.abc import AsyncGenerator
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

__all__ = ["AsyncSession", "Base", "get_db", "get_engine", "get_session_local"]


class Base(DeclarativeBase):
    pass


@lru_cache
def get_engine() -> AsyncEngine:
    """Create the async engine once, lazily, so tests can override DATABASE_URL before first use."""
    return create_async_engine(get_settings().database_url, future=True)


@lru_cache
def get_session_local() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), expire_on_commit=False, autoflush=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with get_session_local()() as session:
        yield session
