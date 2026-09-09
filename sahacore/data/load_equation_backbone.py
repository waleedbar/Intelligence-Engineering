"""Seeds engine_internal.equation_backbone from equation_backbone.json.
Requires sql/020_equation_backbone.sql to already be applied.

    python -m sahacore.data.load_equation_backbone
"""
import json
from pathlib import Path

from sahacore.db import get_connection

DATA_FILE = Path(__file__).parent / "equation_backbone.json"

_COLUMNS = ["source_row", "eq_id", "layer", "name", "formula", "inputs",
            "outputs", "cadence"]


def load_equation_backbone() -> int:
    rows = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    placeholders = ", ".join(f"%({c})s" for c in _COLUMNS)
    update_clause = ", ".join(f"{c} = EXCLUDED.{c}" for c in _COLUMNS if c != "source_row")

    conn = get_connection()
    with conn.cursor() as cur:
        for row in rows:
            cur.execute(
                f"""
                INSERT INTO engine_internal.equation_backbone ({", ".join(_COLUMNS)})
                VALUES ({placeholders})
                ON CONFLICT (source_row) DO UPDATE SET {update_clause}
                """,
                {c: row[c] for c in _COLUMNS},
            )
    conn.commit()
    conn.close()
    return len(rows)


if __name__ == "__main__":
    n = load_equation_backbone()
    print(f"loaded {n} rows into engine_internal.equation_backbone")
