"""Seeds engine_internal.eq_param_fk and its resolution table from
eq_param_fk.json. Requires sql/012_eq_param_fk.sql to already be applied.

    python -m sahacore.data.load_eq_param_fk
"""
import json
from pathlib import Path

from sahacore.db import get_connection

DATA_FILE = Path(__file__).parent / "eq_param_fk.json"

_COLUMNS = [
    "source_row", "eq_id", "keys_are_explicit", "consumes_keys", "authoritative_sheets",
    "loaded_registries", "all_authorities_loaded", "backend_object",
    "validation_rule",
]


def load_eq_param_fk() -> tuple[int, int]:
    rows = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    placeholders = ", ".join(f"%({c})s" for c in _COLUMNS)
    update_clause = ", ".join(f"{c} = EXCLUDED.{c}" for c in _COLUMNS if c != "source_row")

    conn = get_connection()
    resolutions = 0
    with conn.cursor() as cur:
        for row in rows:
            cur.execute(
                f"""
                INSERT INTO engine_internal.eq_param_fk ({", ".join(_COLUMNS)})
                VALUES ({placeholders})
                ON CONFLICT (source_row) DO UPDATE SET {update_clause}
                """,
                {c: row[c] for c in _COLUMNS},
            )
            # The resolution set is rebuilt wholesale: a key that stops being
            # consumed must not linger as a stale row.
            cur.execute(
                "DELETE FROM engine_internal.eq_param_fk_resolution WHERE source_row = %s",
                (row["source_row"],),
            )
            for key, res in row["key_resolution"].items():
                cur.execute(
                    """
                    INSERT INTO engine_internal.eq_param_fk_resolution
                        (source_row, eq_id, param_key, status, resolved_in)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (row["source_row"], row["eq_id"], key,
                     res["status"], res["resolved_in"]),
                )
                resolutions += 1
    conn.commit()
    conn.close()
    return len(rows), resolutions


if __name__ == "__main__":
    n, r = load_eq_param_fk()
    print(f"loaded {n} rows into engine_internal.eq_param_fk ({r} key resolutions)")
