"""Seeds ONB-005's equations and answer encodings from onboarding_o5.json.
Requires sql/039_onboarding_o5.sql to already be applied.

    python -m sahacore.data.load_onboarding_o5
"""
import json
from pathlib import Path

from sahacore.db import get_connection

DATA_FILE = Path(__file__).parent / "onboarding_o5.json"

_EQUATION_COLUMNS = ["equation_id", "source_row", "name", "formula",
                     "variables", "units", "value_range", "engine_target"]
_ENCODING_COLUMNS = ["equation_id", "encodes", "ordinal_position", "option",
                     "value"]


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


def load_onboarding_o5() -> dict[str, int]:
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))

    conn = get_connection()
    with conn.cursor() as cur:
        _upsert(cur, "engine_internal.onboarding_o5_equation",
                _EQUATION_COLUMNS, "equation_id", data["equations"])
        _upsert(cur, "engine_internal.onboarding_o5_encoding",
                _ENCODING_COLUMNS, "encodes, ordinal_position",
                data["encodings"])
    conn.commit()
    conn.close()
    return {"onboarding_o5_equation": len(data["equations"]),
            "onboarding_o5_encoding": len(data["encodings"])}


if __name__ == "__main__":
    for table, n in load_onboarding_o5().items():
        print(f"loaded {n} rows into engine_internal.{table}")
