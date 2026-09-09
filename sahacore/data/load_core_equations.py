"""Seeds engine_internal.core_equation from core_equations.json.
Requires sql/023_core_equations.sql to already be applied.

    python -m sahacore.data.load_core_equations
"""
import json
from pathlib import Path

from sahacore.db import get_connection

DATA_FILE = Path(__file__).parent / "core_equations.json"

_COLUMNS = ["eq_id", "source_row", "layer", "name", "formula", "inputs",
            "outputs", "units", "correction_applied"]


def load_core_equations() -> int:
    rows = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    placeholders = ", ".join(f"%({c})s" for c in _COLUMNS)
    update_clause = ", ".join(f"{c} = EXCLUDED.{c}" for c in _COLUMNS if c != "eq_id")

    conn = get_connection()
    with conn.cursor() as cur:
        for row in rows:
            cur.execute(
                f"""
                INSERT INTO engine_internal.core_equation ({", ".join(_COLUMNS)})
                VALUES ({placeholders})
                ON CONFLICT (eq_id) DO UPDATE SET {update_clause}
                """,
                {c: row[c] for c in _COLUMNS},
            )
    conn.commit()
    conn.close()
    return len(rows)


if __name__ == "__main__":
    n = load_core_equations()
    print(f"loaded {n} rows into engine_internal.core_equation")
