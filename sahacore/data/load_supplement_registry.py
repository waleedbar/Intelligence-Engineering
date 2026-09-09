"""Seeds engine_internal.supplement_registry from supplement_registry.json.
Requires sql/019_supplement_registry.sql to already be applied.

    python -m sahacore.data.load_supplement_registry
"""
import json
from pathlib import Path

from sahacore.db import get_connection

DATA_FILE = Path(__file__).parent / "supplement_registry.json"

_COLUMNS = ["supplement", "source_row", "maps_to_canonical", "mapping_kind",
            "maps_to_nutrients", "effect_cap", "evidence_position",
            "cluster_effect_permitted", "is_complete"]


def load_supplement_registry() -> int:
    rows = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    placeholders = ", ".join(f"%({c})s" for c in _COLUMNS)
    update_clause = ", ".join(f"{c} = EXCLUDED.{c}" for c in _COLUMNS if c != "supplement")

    conn = get_connection()
    with conn.cursor() as cur:
        for row in rows:
            cur.execute(
                f"""
                INSERT INTO engine_internal.supplement_registry ({", ".join(_COLUMNS)})
                VALUES ({placeholders})
                ON CONFLICT (supplement) DO UPDATE SET {update_clause}
                """,
                {c: row[c] for c in _COLUMNS},
            )
    conn.commit()
    conn.close()
    return len(rows)


if __name__ == "__main__":
    n = load_supplement_registry()
    print(f"loaded {n} rows into engine_internal.supplement_registry")
