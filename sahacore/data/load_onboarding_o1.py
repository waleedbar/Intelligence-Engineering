"""Seeds ONB-001's equations and parameters from onboarding_o1.json.
Requires sql/032_onboarding_o1.sql to already be applied.

    python -m sahacore.data.load_onboarding_o1
"""
import json
from pathlib import Path

from sahacore.db import get_connection

DATA_FILE = Path(__file__).parent / "onboarding_o1.json"

_EQUATION_COLUMNS = ["equation_id", "source_row", "name", "formula",
                     "variables", "units", "value_range",
                     "engine_target"]
_PARAMETER_COLUMNS = ["key", "name", "source_row", "value", "units", "source",
                      "calibration", "notes"]
_ELSEWHERE_COLUMNS = ["equation_id", "name", "formula", "units", "declared_by",
                      "absent_from_authority_sheet", "consumed_by"]


def _upsert(cur, table: str, columns: list[str], key: str, rows: list[dict]) -> None:
    placeholders = ", ".join(f"%({c})s" for c in columns)
    updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in columns if c != key)
    for row in rows:
        cur.execute(
            f"""
            INSERT INTO {table} ({", ".join(columns)})
            VALUES ({placeholders})
            ON CONFLICT ({key}) DO UPDATE SET {updates}
            """,
            {c: row[c] for c in columns},
        )


def load_onboarding_o1() -> dict[str, int]:
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    conn = get_connection()
    with conn.cursor() as cur:
        _upsert(cur, "engine_internal.onboarding_o1_equation",
                _EQUATION_COLUMNS, "equation_id", data["equations"])
        _upsert(cur, "engine_internal.onboarding_o1_parameter",
                _PARAMETER_COLUMNS, "key", data["parameters"])
        _upsert(cur, "engine_internal.onboarding_declared_elsewhere",
                _ELSEWHERE_COLUMNS, "equation_id", data["declared_elsewhere"])
    conn.commit()
    conn.close()
    return {"onboarding_o1_equation": len(data["equations"]),
            "onboarding_o1_parameter": len(data["parameters"]),
            "onboarding_declared_elsewhere": len(data["declared_elsewhere"])}


if __name__ == "__main__":
    for table, n in load_onboarding_o1().items():
        print(f"loaded {n} rows into engine_internal.{table}")
