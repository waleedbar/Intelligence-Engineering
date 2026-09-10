"""Seeds ONB-010's goal areas, their pathways and the pi_k ladder.
Requires sql/044_onboarding_o10.sql to already be applied.

    python -m sahacore.data.load_onboarding_o10
"""
import json
from pathlib import Path

from sahacore.db import get_connection

DATA_FILE = Path(__file__).parent / "onboarding_o10.json"

_GOAL_COLUMNS = ["goal_area", "source_row", "weight", "priority_level",
                 "key_nutrient_targets", "z_pathways_text", "source",
                 "ui_status"]
_PATHWAY_COLUMNS = ["goal_area", "z_pathway"]
_RULE_COLUMNS = ["priority_level", "source_row", "weight", "assignment_rule",
                 "engine_equation"]


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


def load_onboarding_o10() -> dict[str, int]:
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    pathways = [{"goal_area": goal["goal_area"], "z_pathway": pathway}
                for goal in data["goals"] for pathway in goal["z_pathways"]]

    conn = get_connection()
    with conn.cursor() as cur:
        _upsert(cur, "engine_internal.onboarding_o10_goal",
                _GOAL_COLUMNS, "goal_area", data["goals"])
        _upsert(cur, "engine_internal.onboarding_o10_goal_pathway",
                _PATHWAY_COLUMNS, "goal_area, z_pathway", pathways)
        _upsert(cur, "engine_internal.onboarding_o10_weight_rule",
                _RULE_COLUMNS, "priority_level", data["rules"])
    conn.commit()
    conn.close()
    return {"onboarding_o10_goal": len(data["goals"]),
            "onboarding_o10_goal_pathway": len(pathways),
            "onboarding_o10_weight_rule": len(data["rules"])}


if __name__ == "__main__":
    for table, n in load_onboarding_o10().items():
        print(f"loaded {n} rows into engine_internal.{table}")
