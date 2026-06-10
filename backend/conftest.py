import os
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


def pytest_configure(config: pytest.Config) -> None:
    """Set test DATABASE_URL before any app module is imported (engine is lazy)."""
    os.environ.setdefault(
        "DATABASE_URL",
        "postgresql+asyncpg://postgres:BYogi%40634668@localhost:5432/pharma_test",
    )


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def _prepare_database() -> AsyncGenerator[None, None]:
    """Create all tables once for the test session, tear down afterwards.

    Imported late (inside the fixture) so the lazy engine picks up the test URL
    set by pytest_configure before any app module's top-level code runs.
    Tests that don't use db_session or client never trigger this fixture.
    """
    import app.models  # noqa: F401 — registers all ORM classes with Base.metadata
    from app.core.db import Base, get_engine

    engine = get_engine()
    async with engine.begin() as conn:
        # Drop first so a previous crashed run can't leave stale rows that
        # cause unique-constraint errors in this session.
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(loop_scope="session")
async def db_session(_prepare_database: None) -> AsyncGenerator[AsyncSession, None]:
    """Function-scoped async session.

    Repos only ever call session.flush(), never session.commit(), so all test data
    stays within the implicit transaction started on first SQL.  We roll back at the
    end which cleans up every row the test touched — no SAVEPOINT needed (and
    SAVEPOINTs are unreliable on Windows IocpProactor with asyncpg).
    """
    from app.core.db import get_session_local

    async with get_session_local()() as session:
        try:
            yield session
        finally:
            await session.rollback()


@pytest_asyncio.fixture(loop_scope="session")
async def client(_prepare_database: None) -> AsyncGenerator[AsyncClient, None]:
    """ASGI test client. Depends on _prepare_database so API tests that hit the DB
    get the schema created first.
    """
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
