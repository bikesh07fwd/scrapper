"""
database.py — SQLAlchemy async engine, session factory, and declarative base.

Using SQLAlchemy's asyncio extension with asyncpg as the PostgreSQL driver.
The application never interacts with the database directly — it always goes
through the ORM layer, which keeps us database-agnostic (swapping the
DATABASE_URL is all that's needed to change backends).
"""

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from config import settings

# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------
# echo=False — SQL statements are not logged to stdout in production.
# Set echo=True temporarily when debugging query issues.
#
# pool_pre_ping=True — before lending a connection from the pool, SQLAlchemy
# sends a lightweight "SELECT 1" to confirm the connection is still alive.
# This prevents stale connections after Neon's idle-connection timeout.
# ---------------------------------------------------------------------------
engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
)

# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------
# expire_on_commit=False — prevents SQLAlchemy from expiring ORM attributes
# immediately after a commit. Without this, accessing an attribute after
# commit raises a lazy-load error in async context.
# ---------------------------------------------------------------------------
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ---------------------------------------------------------------------------
# Declarative base — all ORM models inherit from this
# ---------------------------------------------------------------------------
class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Dependency for FastAPI route handlers
# ---------------------------------------------------------------------------
async def get_db() -> AsyncSession:
    """
    Yields an async database session scoped to a single request.
    Used as a FastAPI dependency: `db: AsyncSession = Depends(get_db)`.
    The session is automatically closed when the request finishes.
    """
    async with AsyncSessionLocal() as session:
        yield session
