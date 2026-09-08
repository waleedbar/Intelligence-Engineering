"""Shared fixtures.

The engine's equation layers are pure functions and their tests need no
database. The ledger is the opposite: its contract IS database behaviour --
"duplicate delivery no-op", "the original fact is never overwritten",
"81 nutrient doses present" -- and a mock cannot fail a UNIQUE constraint or
refuse an UPDATE. So the ledger tests run against a real PostgreSQL when
DATABASE_URL is configured, and are skipped, not faked, when it is not.
"""
import os

import pytest


def _database_url() -> str | None:
    url = os.environ.get("DATABASE_URL")
    return url or None


@pytest.fixture(scope="session")
def migrated_database() -> str:
    """A PostgreSQL with every migration applied and the ledger's policy row
    seeded. Applies them here rather than assuming an externally prepared
    database, so `pytest` alone is enough to run the ledger tests against a
    scratch instance."""
    url = _database_url()
    if url is None:
        pytest.skip("DATABASE_URL is not set; ledger tests need a real PostgreSQL")

    from sahacore.data.load_ledger_policy import load_ledger_policy
    from sahacore.migrate import apply_pending

    apply_pending()
    load_ledger_policy()
    return url


@pytest.fixture
def ledger_db(migrated_database):
    """A connection whose work is rolled back afterwards, so each test sees a
    ledger containing only what it wrote itself."""
    from sahacore.db import get_connection

    conn = get_connection()
    try:
        yield conn
    finally:
        conn.rollback()
        conn.close()
