"""Seeds engine_internal.parameter_registry_ext20 from param_registry_ext20.json.
Requires sql/017_param_registry_ext20.sql to already be applied.

    python -m sahacore.data.load_param_registry_ext20
"""
import json
from pathlib import Path

from sahacore.db import get_connection

DATA_FILE = Path(__file__).parent / "param_registry_ext20.json"

_COLUMNS = ["source_row", "parameter", "symbol", "unit", "default_or_range",
            "calibration_source"]


def load_param_registry_ext20() -> int:
    rows = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    placeholders = ", ".join(f"%({c})s" for c in _COLUMNS)
    update_clause = ", ".join(f"{c} = EXCLUDED.{c}" for c in _COLUMNS if c != "source_row")

    conn = get_connection()
    with conn.cursor() as cur:
        for row in rows:
            cur.execute(
                f"""
                INSERT INTO engine_internal.parameter_registry_ext20 ({", ".join(_COLUMNS)})
                VALUES ({placeholders})
                ON CONFLICT (source_row) DO UPDATE SET {update_clause}
                """,
                {c: row[c] for c in _COLUMNS},
            )
    conn.commit()
    conn.close()
    return len(rows)


if __name__ == "__main__":
    n = load_param_registry_ext20()
    print(f"loaded {n} rows into engine_internal.parameter_registry_ext20")
