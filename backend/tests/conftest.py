"""
tests/conftest.py — Shared pytest configuration and fixtures.

Phase 2 tests (fetcher, adapters) do not touch the database.
However, importing config.py requires DATABASE_URL because pydantic-settings
validates all required fields at import time.

We set a placeholder value here — before any application module is imported —
so that config.py can be loaded without a real database URL.

The placeholder is never used to open a connection in Phase 2 tests.
"""

import os

# Must be set before any application imports so pydantic-settings
# finds the value during Settings() construction.
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://test:test@localhost:5432/testdb",
)
