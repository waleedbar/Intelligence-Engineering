"""Seeds the validation battery from validation_battery.json.
Requires sql/029_validation_battery.sql to already be applied.

    python -m sahacore.data.load_validation_battery
"""
import json
from pathlib import Path

from sahacore.db import get_connection

DATA_FILE = Path(__file__).parent / "validation_battery.json"

_TEST_COLUMNS = ["test_id", "source_row", "section", "target", "method",
                 "pass_criterion", "gate", "coverage", "enforced_by",
                 "coverage_note"]
_SECTION_COLUMNS = ["source_row", "heading"]


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


def load_validation_battery() -> dict[str, int]:
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    conn = get_connection()
    with conn.cursor() as cur:
        _upsert(cur, "engine_internal.validation_section",
                _SECTION_COLUMNS, "source_row", data["sections"])
        _upsert(cur, "engine_internal.validation_test",
                _TEST_COLUMNS, "test_id", data["tests"])
    conn.commit()
    conn.close()
    return {
        "validation_section": len(data["sections"]),
        "validation_test": len(data["tests"]),
    }


if __name__ == "__main__":
    for table, n in load_validation_battery().items():
        print(f"loaded {n} rows into engine_internal.{table}")
