"""Seeds engine_internal.veto_message from veto_messages.json.
Requires sql/025_veto_messages.sql to already be applied.

    python -m sahacore.data.load_veto_messages
"""
import json
from pathlib import Path

from sahacore.db import get_connection

DATA_FILE = Path(__file__).parent / "veto_messages.json"

_COLUMNS = ["message_id", "source_row", "severity", "action", "title",
            "body_template", "cta"]


def load_veto_messages() -> int:
    rows = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    placeholders = ", ".join(f"%({c})s" for c in _COLUMNS)
    update_clause = ", ".join(f"{c} = EXCLUDED.{c}" for c in _COLUMNS if c != "message_id")

    conn = get_connection()
    with conn.cursor() as cur:
        for row in rows:
            cur.execute(
                f"""
                INSERT INTO engine_internal.veto_message ({", ".join(_COLUMNS)})
                VALUES ({placeholders})
                ON CONFLICT (message_id) DO UPDATE SET {update_clause}
                """,
                {c: row[c] for c in _COLUMNS},
            )
    conn.commit()
    conn.close()
    return len(rows)


if __name__ == "__main__":
    n = load_veto_messages()
    print(f"loaded {n} rows into engine_internal.veto_message")
