"""Applies pending SQL migrations from sql/*.sql in order, tracking what has
already run in a `schema_migrations` table so re-running is always safe and
nothing is silently skipped or double-applied.

    python -m sahacore.migrate          # apply all pending migrations
    python -m sahacore.migrate --status # list applied/pending, apply nothing
"""
import sys
from pathlib import Path

from sahacore.db import get_connection

SQL_DIR = Path(__file__).parent.parent / "sql"

_CREATE_TRACKING_TABLE = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version     TEXT PRIMARY KEY,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


def _migration_files() -> list[Path]:
    return sorted(SQL_DIR.glob("*.sql"), key=lambda p: p.name)


def _applied_versions(conn) -> set[str]:
    with conn.cursor() as cur:
        cur.execute(_CREATE_TRACKING_TABLE)
        conn.commit()
        cur.execute("SELECT version FROM schema_migrations")
        return {row["version"] for row in cur.fetchall()}


def status() -> None:
    conn = get_connection()
    applied = _applied_versions(conn)
    conn.close()
    for f in _migration_files():
        marker = "applied" if f.name in applied else "pending"
        print(f"[{marker}] {f.name}")


def apply_pending() -> list[str]:
    conn = get_connection()
    applied = _applied_versions(conn)
    newly_applied = []
    for f in _migration_files():
        if f.name in applied:
            continue
        sql = f.read_text(encoding="utf-8")
        try:
            with conn.cursor() as cur:
                cur.execute(sql)
                cur.execute(
                    "INSERT INTO schema_migrations (version) VALUES (%s)", (f.name,)
                )
            conn.commit()
        except Exception:
            conn.rollback()
            conn.close()
            print(f"FAILED applying {f.name} -- rolled back, stopping", file=sys.stderr)
            raise
        newly_applied.append(f.name)
        print(f"applied {f.name}")
    conn.close()
    if not newly_applied:
        print("no pending migrations")
    return newly_applied


if __name__ == "__main__":
    if "--status" in sys.argv:
        status()
    else:
        apply_pending()
