"""
tests/conftest.py — Shared pytest configuration, database fixtures, and settings overrides.
"""

import os
import inspect
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

# Set placeholder DATABASE_URL before importing config to satisfy settings validation.
# This placeholder is never used to connect to any database.
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://test:test@localhost:5432/testdb",
)

from database import Base


def pytest_collection_modifyitems(items):
    """
    Hook to dynamically mark all async tests with loop_scope="session".
    This ensures that all tests and fixtures share the same session-scoped event loop,
    preventing loop mismatch errors without needing a deprecated custom event_loop fixture.
    """
    for item in items:
        # Check if the test is a coroutine function
        if item.obj and (inspect.iscoroutinefunction(item.obj) or inspect.isgeneratorfunction(item.obj)):
            marker = item.get_closest_marker("asyncio")
            if marker:
                marker.kwargs["loop_scope"] = "session"
            else:
                item.add_marker(pytest.mark.asyncio(loop_scope="session"))


@pytest.fixture(scope="session")
def test_db_url():
    """
    Retrieves the isolated test database URL from the environment.
    If missing, skips the dependent test cleanly.
    """
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip(
            "TEST_DATABASE_URL environment variable is missing. "
            "Skipping database integration tests. To run them, configure an isolated database URL."
        )

    # Safety Check: Prevent running tests against production Neon storage
    prod_url = os.getenv("DATABASE_URL")
    if url == prod_url:
        pytest.fail(
            "TEST_DATABASE_URL cannot be identical to the production DATABASE_URL "
            "to prevent accidental data modification or table truncation on production database."
        )
    return url


@pytest.fixture(scope="session")
async def test_engine(test_db_url):
    """
    Creates an async engine and initializes tables for the test session.
    """
    from config import settings
    # Override settings URL so modules importing settings use the test database
    settings.database_url = test_db_url

    engine = create_async_engine(test_db_url, echo=False)

    # Initialize DB tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Drop tables on cleanup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture
async def db_session(test_engine):
    """
    Yields an async session. Each test gets a fresh session; rollback on teardown.
    """
    AsyncSessionLocal = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with AsyncSessionLocal() as session:
        yield session
        await session.rollback()


@pytest.fixture(autouse=True)
async def clean_database(db_session):
    """
    Truncates all tables before each test to prevent cross-test data pollution.
    """
    from sqlalchemy import delete
    from models import Job, IngestionRun, AdapterHealth

    await db_session.execute(delete(Job))
    await db_session.execute(delete(IngestionRun))
    await db_session.execute(delete(AdapterHealth))
    await db_session.commit()
