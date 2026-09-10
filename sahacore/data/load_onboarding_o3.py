"""Seeds ONB-003's equations from onboarding_o3.json.
Requires sql/036_onboarding_o3.sql to already be applied.

    python -m sahacore.data.load_onboarding_o3
"""
import json
from pathlib import Path

from sahacore.db import get_connection

DATA_FILE = Path(__file__).parent / "onboarding_o3.json"

_EQUATION_COLUMNS = ["equation_id", "source_row", "name", "formula",
                     "variables", "units", "value_range", "engine_target"]
_ORDINAL_COLUMNS = ["equation_id", "option", "score"]


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


def load_onboarding_o3() -> dict[str, int]:
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    ordinals = [{"equation_id": e["equation_id"], "option": o["option"],
                 "score": o["value"]}
                for e in data["equations"] for o in e["ordinal_scale"]]

    conn = get_connection()
    with conn.cursor() as cur:
        _upsert(cur, "engine_internal.onboarding_o3_equation",
                _EQUATION_COLUMNS, "equation_id", data["equations"])
        _upsert(cur, "engine_internal.onboarding_o3_ordinal",
                _ORDINAL_COLUMNS, "equation_id, option", ordinals)
    conn.commit()
    conn.close()
    return {"onboarding_o3_equation": len(data["equations"]),
            "onboarding_o3_ordinal": len(ordinals)}


if __name__ == "__main__":
    for table, n in load_onboarding_o3().items():
        print(f"loaded {n} rows into engine_internal.{table}")
