"""Seeds engine_internal.veto_drug_nutrient from veto_drug_nutrient_339.json.
Requires sql/014_veto_action_space.sql to already be applied.

    python -m sahacore.data.load_veto_registry
"""
import json
from pathlib import Path

from sahacore.db import get_connection

DATA_FILE = Path(__file__).parent / "veto_drug_nutrient_339.json"

_COLUMNS = [
    "rule_id", "source_row", "drug_or_class", "nutrient_or_food",
    "engine_nutrient_id", "nutrient_category", "link_type", "severity",
    "action", "bandit_action", "message_id", "clinical_rationale", "k_ij",
    "source_rule_id",
]


def load_veto_registry() -> int:
    rows = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    placeholders = ", ".join(f"%({c})s" for c in _COLUMNS)
    update_clause = ", ".join(f"{c} = EXCLUDED.{c}" for c in _COLUMNS if c != "rule_id")

    conn = get_connection()
    with conn.cursor() as cur:
        for row in rows:
            cur.execute(
                f"""
                INSERT INTO engine_internal.veto_drug_nutrient ({", ".join(_COLUMNS)})
                VALUES ({placeholders})
                ON CONFLICT (rule_id) DO UPDATE SET {update_clause}
                """,
                {c: row[c] for c in _COLUMNS},
            )
    conn.commit()
    conn.close()
    return len(rows)


if __name__ == "__main__":
    n = load_veto_registry()
    print(f"loaded {n} rows into engine_internal.veto_drug_nutrient")
