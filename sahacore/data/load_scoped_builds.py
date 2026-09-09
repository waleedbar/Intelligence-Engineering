"""Seeds the scoped-build contracts from scoped_builds.json.
Requires sql/030_scoped_builds.sql to already be applied.

    python -m sahacore.data.load_scoped_builds
"""
import json
from pathlib import Path

from sahacore.db import get_connection

DATA_FILE = Path(__file__).parent / "scoped_builds.json"

_PREREQ_COLUMNS = ["number", "name", "source_row", "detail", "status",
                   "satisfied_by", "status_note"]
_ITEM_COLUMNS = ["item_id", "source_row", "title"]
_ATTRIBUTE_COLUMNS = ["item_id", "name", "source_row", "value"]
_NOTE_COLUMNS = ["item_id", "source_row", "text"]
_DECISION_COLUMNS = ["number", "source_row", "decision", "why_it_matters"]


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


def load_scoped_builds() -> dict[str, int]:
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))

    attributes = [{**a, "item_id": item["item_id"]}
                  for item in data["items"] for a in item["attributes"]]
    notes = [{**n, "item_id": item["item_id"]}
             for item in data["items"] for n in item["notes"]]

    conn = get_connection()
    with conn.cursor() as cur:
        _upsert(cur, "engine_internal.scoped_build_prerequisite",
                _PREREQ_COLUMNS, "number", data["prerequisites"])
        _upsert(cur, "engine_internal.scoped_build",
                _ITEM_COLUMNS, "item_id", data["items"])
        _upsert(cur, "engine_internal.scoped_build_attribute",
                _ATTRIBUTE_COLUMNS, "item_id, name", attributes)
        _upsert(cur, "engine_internal.scoped_build_note",
                _NOTE_COLUMNS, "item_id, source_row", notes)
        _upsert(cur, "engine_internal.founder_decision",
                _DECISION_COLUMNS, "number", data["open_decisions"])
    conn.commit()
    conn.close()
    return {
        "scoped_build_prerequisite": len(data["prerequisites"]),
        "scoped_build": len(data["items"]),
        "scoped_build_attribute": len(attributes),
        "scoped_build_note": len(notes),
        "founder_decision": len(data["open_decisions"]),
    }


if __name__ == "__main__":
    for table, n in load_scoped_builds().items():
        print(f"loaded {n} rows into engine_internal.{table}")
