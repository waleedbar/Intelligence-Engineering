"""Seeds ONB-002's equations, its input encoding, and the MET catalogue.
Requires sql/033_onboarding_o2_activities.sql to already be applied.

    python -m sahacore.data.load_onboarding_o2
"""
import json
from pathlib import Path

from sahacore.db import get_connection

DATA_DIR = Path(__file__).parent

_EQUATION_COLUMNS = ["equation_id", "source_row", "name", "formula",
                     "variables", "units", "value_range", "computable",
                     "missing_symbol", "unresolved_note"]
_ENCODING_COLUMNS = ["field", "option", "source_row", "ui_selection",
                     "mapped_value", "numeric_value", "variable", "source"]
_ACTIVITY_COLUMNS = ["activity_id", "number", "source_row", "name", "met",
                     "intensity", "typical_duration", "duration_unit"]
_IMPACT_COLUMNS = ["activity_id", "cluster_id", "impact"]
_DISAGREEMENT_COLUMNS = ["activity_id", "met", "sheet_intensity",
                         "compendium_intensity"]


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


def load_onboarding_o2() -> dict[str, int]:
    o2 = json.loads((DATA_DIR / "onboarding_o2.json").read_text(encoding="utf-8"))
    activities = json.loads(
        (DATA_DIR / "activities_50.json").read_text(encoding="utf-8"))

    equations = [{
        **{c: e.get(c) for c in _EQUATION_COLUMNS if c in e},
        "missing_symbol": (e["unresolved"] or {}).get("missing_symbol"),
        "unresolved_note": (e["unresolved"] or {}).get("reason"),
    } for e in o2["equations"]]

    impacts = [{"activity_id": a["activity_id"], "cluster_id": cluster,
                "impact": value}
               for a in activities["activities"]
               for cluster, value in a["cluster_impact"].items()]

    conn = get_connection()
    with conn.cursor() as cur:
        _upsert(cur, "engine_internal.onboarding_o2_equation",
                _EQUATION_COLUMNS, "equation_id", equations)
        _upsert(cur, "engine_internal.onboarding_o2_encoding",
                _ENCODING_COLUMNS, "field, option", o2["input_encoding"])
        _upsert(cur, "engine_internal.activity_catalogue",
                _ACTIVITY_COLUMNS, "activity_id", activities["activities"])
        _upsert(cur, "engine_internal.activity_cluster_impact",
                _IMPACT_COLUMNS, "activity_id, cluster_id", impacts)
        _upsert(cur, "engine_internal.activity_intensity_disagreement",
                _DISAGREEMENT_COLUMNS, "activity_id",
                activities["outside_compendium_bands"])
    conn.commit()
    conn.close()
    return {
        "onboarding_o2_equation": len(equations),
        "onboarding_o2_encoding": len(o2["input_encoding"]),
        "activity_catalogue": len(activities["activities"]),
        "activity_cluster_impact": len(impacts),
        "activity_intensity_disagreement": len(activities["outside_compendium_bands"]),
    }


if __name__ == "__main__":
    for table, n in load_onboarding_o2().items():
        print(f"loaded {n} rows into engine_internal.{table}")
