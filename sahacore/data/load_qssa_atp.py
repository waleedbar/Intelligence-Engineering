"""Seeds qssa_atp_complexes from qssa_atp_complexes_5.json.
Requires sql/007_qssa_atp.sql to already be applied.

    python -m sahacore.data.load_qssa_atp
"""
import json
from pathlib import Path

from sahacore.db import get_connection

DATA_FILE = Path(__file__).parent / "qssa_atp_complexes_5.json"

_COLUMNS = ["complex_id", "name", "substrate", "km_um", "vmax_relative", "source"]


def load_qssa_atp() -> int:
    rows = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    placeholders = ", ".join(f"%({c})s" for c in _COLUMNS)
    update_clause = ", ".join(f"{c} = EXCLUDED.{c}" for c in _COLUMNS if c != "complex_id")

    conn = get_connection()
    with conn.cursor() as cur:
        for row in rows:
            cur.execute(
                f"""
                INSERT INTO qssa_atp_complexes ({", ".join(_COLUMNS)})
                VALUES ({placeholders})
                ON CONFLICT (complex_id) DO UPDATE SET {update_clause}
                """,
                row,
            )
    conn.commit()
    conn.close()
    return len(rows)


if __name__ == "__main__":
    n = load_qssa_atp()
    print(f"loaded {n} rows into qssa_atp_complexes")
