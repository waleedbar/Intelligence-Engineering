"""Seeds ONB-006's equations, relative risks and pathway map from
onboarding_o6.json. Requires sql/040_onboarding_o6.sql to already be applied.

    python -m sahacore.data.load_onboarding_o6
"""
import json
from pathlib import Path

from sahacore.db import get_connection

DATA_FILE = Path(__file__).parent / "onboarding_o6.json"

_EQUATION_COLUMNS = ["equation_id", "source_row", "name", "formula",
                     "variables", "units", "value_range", "engine_target",
                     "indicator", "rr_in_formula", "log_in_formula",
                     "rr_in_variables"]
_CONDITION_COLUMNS = ["condition", "source_row", "relative_risk",
                      "log_relative_risk", "source", "z_pathways"]
_PATHWAY_COLUMNS = ["condition", "z_pathway"]


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
            """
            if updates else
            f"""
            INSERT INTO {table} ({", ".join(columns)})
            VALUES ({placeholders})
            ON CONFLICT ({key}) DO NOTHING
            """,
            {c: row[c] for c in columns},
        )


def load_onboarding_o6() -> dict[str, int]:
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    pathways = [{"condition": condition["condition"], "z_pathway": code}
                for condition in data["conditions"]
                for code in condition["z_pathway_codes"]]

    conn = get_connection()
    with conn.cursor() as cur:
        _upsert(cur, "engine_internal.onboarding_o6_equation",
                _EQUATION_COLUMNS, "equation_id", data["equations"])
        _upsert(cur, "engine_internal.onboarding_o6_condition",
                _CONDITION_COLUMNS, "condition", data["conditions"])
        _upsert(cur, "engine_internal.onboarding_o6_condition_pathway",
                _PATHWAY_COLUMNS, "condition, z_pathway", pathways)
    conn.commit()
    conn.close()
    return {"onboarding_o6_equation": len(data["equations"]),
            "onboarding_o6_condition": len(data["conditions"]),
            "onboarding_o6_condition_pathway": len(pathways)}


if __name__ == "__main__":
    for table, n in load_onboarding_o6().items():
        print(f"loaded {n} rows into engine_internal.{table}")
