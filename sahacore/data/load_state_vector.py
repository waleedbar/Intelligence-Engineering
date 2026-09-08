"""Seeds the Layer 0 `state_vector` table from state_vector_219.json.
Requires sql/002_layer0_registries.sql and sql/003_state_vector.sql to
already be applied, and the `nutrients` table to already be loaded
(state_vector.nutrient_code is a foreign key into it).

    python -m sahacore.data.load_state_vector
"""
import json
from pathlib import Path

from sahacore.db import get_connection

DATA_FILE = Path(__file__).parent / "state_vector_219.json"

_COLUMNS = ["idx", "block", "symbol", "name", "unit", "is_nonlinear", "nutrient_code", "cluster_id", "side"]


def load_state_vector() -> int:
    states = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    placeholders = ", ".join(f"%({c})s" for c in _COLUMNS)
    update_clause = ", ".join(f"{c} = EXCLUDED.{c}" for c in _COLUMNS if c != "idx")

    conn = get_connection()
    with conn.cursor() as cur:
        for state in states:
            cur.execute(
                f"""
                INSERT INTO engine_internal.state_vector ({", ".join(_COLUMNS)})
                VALUES ({placeholders})
                ON CONFLICT (idx) DO UPDATE SET {update_clause}
                """,
                state,
            )
    conn.commit()
    conn.close()
    return len(states)


if __name__ == "__main__":
    n = load_state_vector()
    print(f"loaded {n} state vector entries")
