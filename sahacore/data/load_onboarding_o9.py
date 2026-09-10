"""Seeds ONB-009's drug-nutrient rows and its disagreements with the VETO
registry. Requires sql/043_onboarding_o9.sql to already be applied.

    python -m sahacore.data.load_onboarding_o9
"""
import json
from pathlib import Path

from sahacore.db import get_connection

DATA_FILE = Path(__file__).parent / "onboarding_o9.json"

_INTERACTION_COLUMNS = ["source_row", "drug", "nutrient", "rule_text",
                        "legacy_multiplier", "delta_logit_abs",
                        "mechanism_class", "severity", "production_target"]
_DISAGREEMENT_COLUMNS = ["drug", "veto_rule_id", "o9_nutrient", "o9_severity",
                         "o9_rule", "o9_production_target", "veto_nutrient",
                         "veto_severity", "veto_action"]


def _upsert(cur, table: str, columns: list[str], key: str, rows: list[dict]) -> None:
    keys = {k.strip() for k in key.split(",")}
    placeholders = ", ".join(f"%({c})s" for c in columns)
    updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in columns if c not in keys)
    for row in rows:
        cur.execute(
            f"""
            INSERT INTO {table} ({", ".join(columns)})
            VALUES ({placeholders})
            ON CONFLICT ({key}) DO UPDATE SET {updates}
            """,
            {c: row[c] for c in columns},
        )


def load_onboarding_o9() -> dict[str, int]:
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))

    conn = get_connection()
    with conn.cursor() as cur:
        _upsert(cur, "engine_internal.onboarding_o9_interaction",
                _INTERACTION_COLUMNS, "source_row", data["interactions"])
        _upsert(cur, "engine_internal.onboarding_o9_severity_disagreement",
                _DISAGREEMENT_COLUMNS, "drug, veto_rule_id",
                data["severity_disagreements"])
    conn.commit()
    conn.close()
    return {"onboarding_o9_interaction": len(data["interactions"]),
            "onboarding_o9_severity_disagreement":
                len(data["severity_disagreements"])}


if __name__ == "__main__":
    for table, n in load_onboarding_o9().items():
        print(f"loaded {n} rows into engine_internal.{table}")
