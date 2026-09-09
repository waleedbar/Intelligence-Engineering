"""Seeds Layer 0's build contract from onboarding_canonical.json.
Requires sql/031_onboarding_canonical.sql to already be applied.

    python -m sahacore.data.load_onboarding_canonical
"""
import json
from pathlib import Path

from sahacore.db import get_connection

DATA_FILE = Path(__file__).parent / "onboarding_canonical.json"

_STEP_COLUMNS = ["step_id", "source_row", "authority_sheets",
                 "operational_equation", "inputs", "outputs", "parameter_refs",
                 "python_function", "validation_qa", "blocked_by"]
_BLOCK_COLUMNS = ["registry_block", "sheet_name", "first_index", "last_index"]


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


def load_onboarding_canonical() -> dict[str, int]:
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    conn = get_connection()
    with conn.cursor() as cur:
        _upsert(cur, "engine_internal.onboarding_step",
                _STEP_COLUMNS, "step_id", data["steps"])
        _upsert(cur, "engine_internal.onboarding_state_block",
                _BLOCK_COLUMNS, "registry_block", data["declared_blocks"])
    conn.commit()
    conn.close()
    return {"onboarding_step": len(data["steps"]),
            "onboarding_state_block": len(data["declared_blocks"])}


if __name__ == "__main__":
    for table, n in load_onboarding_canonical().items():
        print(f"loaded {n} rows into engine_internal.{table}")
