"""Seeds ONB-004's PSS-10 items, equations and bands from onboarding_o4.json.
Requires sql/037_onboarding_o4.sql to already be applied.

    python -m sahacore.data.load_onboarding_o4
"""
import json
from pathlib import Path

from sahacore.db import get_connection

DATA_FILE = Path(__file__).parent / "onboarding_o4.json"

_ITEM_COLUMNS = ["item_number", "source_row", "question", "scale", "scoring",
                 "reverse_scored"]
_EQUATION_COLUMNS = ["equation_id", "source_row", "name", "formula",
                     "variables", "units", "value_range", "engine_target"]
_BAND_COLUMNS = ["score_min", "score_max", "source_row", "score_range",
                 "stress_level", "cortisol_impact", "system_response"]


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


def load_onboarding_o4() -> dict[str, int]:
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))

    conn = get_connection()
    with conn.cursor() as cur:
        _upsert(cur, "engine_internal.onboarding_o4_item",
                _ITEM_COLUMNS, "item_number", data["items"])
        _upsert(cur, "engine_internal.onboarding_o4_equation",
                _EQUATION_COLUMNS, "equation_id", data["equations"])
        _upsert(cur, "engine_internal.onboarding_o4_band",
                _BAND_COLUMNS, "score_min", data["bands"])
    conn.commit()
    conn.close()
    return {"onboarding_o4_item": len(data["items"]),
            "onboarding_o4_equation": len(data["equations"]),
            "onboarding_o4_band": len(data["bands"])}


if __name__ == "__main__":
    for table, n in load_onboarding_o4().items():
        print(f"loaded {n} rows into engine_internal.{table}")
