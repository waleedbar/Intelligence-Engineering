"""Seeds engine_internal.runtime_invariant from runtime_invariants.json.
Requires sql/016_runtime_invariants.sql to already be applied.

    python -m sahacore.data.load_runtime_invariants
"""
import json
from pathlib import Path

from sahacore.db import get_connection

DATA_FILE = Path(__file__).parent / "runtime_invariants.json"

_COLUMNS = [
    "source_row", "invariant", "value", "engineering_meaning",
    "backend_owner", "frontend_owner", "data_server_owner", "gate",
    "enforced_by",
]


def load_runtime_invariants() -> int:
    rows = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    placeholders = ", ".join(f"%({c})s" for c in _COLUMNS)
    update_clause = ", ".join(f"{c} = EXCLUDED.{c}" for c in _COLUMNS if c != "source_row")

    conn = get_connection()
    with conn.cursor() as cur:
        for row in rows:
            cur.execute(
                f"""
                INSERT INTO engine_internal.runtime_invariant ({", ".join(_COLUMNS)})
                VALUES ({placeholders})
                ON CONFLICT (source_row) DO UPDATE SET {update_clause}
                """,
                {c: row[c] for c in _COLUMNS},
            )
    conn.commit()
    conn.close()
    return len(rows)


if __name__ == "__main__":
    n = load_runtime_invariants()
    print(f"loaded {n} rows into engine_internal.runtime_invariant")
