"""Seeds ONB-008's conditions, pathway links and compatibility rule.
Requires sql/042_onboarding_o8.sql to already be applied.

    python -m sahacore.data.load_onboarding_o8
"""
import json
from pathlib import Path

from sahacore.db import get_connection

DATA_FILE = Path(__file__).parent / "onboarding_o8.json"

_RULE_COLUMNS = ["name", "text"]
_CONDITION_COLUMNS = ["condition", "source_row", "modifier_text", "gate",
                      "bounded_absorption_effect", "target_adjustment",
                      "z_pathways_text", "evidence_role"]
_PATHWAY_COLUMNS = ["condition", "z_pathway", "factor"]


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


def load_onboarding_o8() -> dict[str, int]:
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))

    rules = [{"name": "scope", "text": data["scope"]},
             {"name": "compatibility_rule", "text": data["compatibility_rule"]}]

    # Every DECLARED link, with factor NULL where the sheet gives none. The
    # 11 nulls are the finding; collapsing them to 1.0 would erase it.
    pathways = []
    for condition in data["conditions"]:
        factors = {m["z_pathway"]: m["factor"] for m in condition["modifiers"]}
        for pathway in condition["z_pathways_declared"]:
            pathways.append({"condition": condition["condition"],
                             "z_pathway": pathway,
                             "factor": factors.get(pathway)})

    conn = get_connection()
    with conn.cursor() as cur:
        _upsert(cur, "engine_internal.onboarding_o8_rule",
                _RULE_COLUMNS, "name", rules)
        _upsert(cur, "engine_internal.onboarding_o8_condition",
                _CONDITION_COLUMNS, "condition", data["conditions"])
        _upsert(cur, "engine_internal.onboarding_o8_pathway",
                _PATHWAY_COLUMNS, "condition, z_pathway", pathways)
    conn.commit()
    conn.close()
    return {"onboarding_o8_rule": len(rules),
            "onboarding_o8_condition": len(data["conditions"]),
            "onboarding_o8_pathway": len(pathways)}


if __name__ == "__main__":
    for table, n in load_onboarding_o8().items():
        print(f"loaded {n} rows into engine_internal.{table}")
