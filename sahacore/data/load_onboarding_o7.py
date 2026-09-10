"""Seeds ONB-007's equations and eight dietary patterns from onboarding_o7.json.
Requires sql/041_onboarding_o7.sql to already be applied.

    python -m sahacore.data.load_onboarding_o7

There is no prior table to load. O7.1 needs 8 x 81 x 2 = 1,296 numbers and
the workbook supplies none of them -- see the migration's header.
"""
import json
from pathlib import Path

from sahacore.db import get_connection

DATA_FILE = Path(__file__).parent / "onboarding_o7.json"

_EQUATION_COLUMNS = ["equation_id", "source_row", "name", "formula",
                     "variables", "units", "value_range", "engine_target"]
_PATTERN_COLUMNS = ["pattern", "source_row", "key_nutrient_shifts",
                    "typical_deficiencies", "ui_label", "ui_status"]
_UNCLAIMED_COLUMNS = ["ui_option"]


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


def load_onboarding_o7() -> dict[str, int]:
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    unclaimed = [{"ui_option": option}
                 for option in data["ui_options_no_pattern_claims"]]

    conn = get_connection()
    with conn.cursor() as cur:
        _upsert(cur, "engine_internal.onboarding_o7_equation",
                _EQUATION_COLUMNS, "equation_id", data["equations"])
        _upsert(cur, "engine_internal.onboarding_o7_pattern",
                _PATTERN_COLUMNS, "pattern", data["patterns"])
        _upsert(cur, "engine_internal.onboarding_o7_ui_option_unclaimed",
                _UNCLAIMED_COLUMNS, "ui_option", unclaimed)
    conn.commit()
    conn.close()
    return {"onboarding_o7_equation": len(data["equations"]),
            "onboarding_o7_pattern": len(data["patterns"]),
            "onboarding_o7_ui_option_unclaimed": len(unclaimed)}


if __name__ == "__main__":
    for table, n in load_onboarding_o7().items():
        print(f"loaded {n} rows into engine_internal.{table}")
