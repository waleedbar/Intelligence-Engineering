"""Seeds engine_internal.parameter_registry from parameter_registry_192.json.
Requires sql/011_parameter_registry.sql to already be applied.

    python -m sahacore.data.load_parameter_registry
"""
import json
from pathlib import Path

from sahacore.db import get_connection

DATA_FILE = Path(__file__).parent / "parameter_registry_192.json"

_COLUMNS = [
    "param_no", "symbol", "layer", "equations", "full_name", "description",
    "units", "default_or_range", "value_kind", "weight", "calibration_method",
    "verification_source", "resolved_by",
]


def load_parameter_registry() -> int:
    rows = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    placeholders = ", ".join(f"%({c})s" for c in _COLUMNS)
    update_clause = ", ".join(f"{c} = EXCLUDED.{c}" for c in _COLUMNS if c != "param_no")

    conn = get_connection()
    with conn.cursor() as cur:
        for row in rows:
            cur.execute(
                f"""
                INSERT INTO engine_internal.parameter_registry ({", ".join(_COLUMNS)})
                VALUES ({placeholders})
                ON CONFLICT (param_no) DO UPDATE SET {update_clause}
                """,
                {c: row.get(c) for c in _COLUMNS},
            )
    conn.commit()
    conn.close()
    return len(rows)


if __name__ == "__main__":
    n = load_parameter_registry()
    print(f"loaded {n} rows into engine_internal.parameter_registry")
