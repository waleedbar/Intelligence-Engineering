"""Seeds engine_internal.veto_message from veto_messages.json.
Requires sql/025_veto_messages.sql and sql/045_veto_message_override.sql to
already be applied.

    python -m sahacore.data.load_veto_messages

The last five columns carry the one authorised change to a regulated message
-- see sahacore/data/build_veto_messages.py. They are loaded like any other
column rather than applied here: the decision belongs in the build, and a row
that reached the database without its attribution would be exactly the thing
the columns exist to make impossible.
"""
import json
from pathlib import Path

from sahacore.db import get_connection

DATA_FILE = Path(__file__).parent / "veto_messages.json"

_COLUMNS = ["message_id", "source_row", "severity", "action", "title",
            "body_template", "cta",
            "source_body_template", "overridden_field", "overridden_by",
            "overridden_on", "override_reason"]


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
