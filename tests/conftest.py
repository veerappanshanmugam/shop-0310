"""Shared test fixtures for the e-commerce test suite."""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from ecommerce.main import app
from ecommerce.database import get_session

# In-memory SQLite engine shared across the test session
test_engine = create_async_engine(
    "sqlite+aiosqlite://",
    echo=False,
)

TestSessionFactory = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def override_get_session():
    """Dependency override that yields a test session."""
    async with TestSessionFactory() as session:
        yield session


@pytest.fixture()
async def client():
    """Async HTTP client with per-test table creation and teardown."""
    # Create all tables
    async with test_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    # Override the get_session dependency
    app.dependency_overrides[get_session] = override_get_session

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    # Drop all tables for isolation
    async with test_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)

    app.dependency_overrides.clear()
