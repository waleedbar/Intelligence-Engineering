"""Seeds the Layer 0 `nutrients` table from the canonical 81-nutrient registry
(sourced from Dr. Ali's P1 Nutrients 81 sheet, v39sEng2). Run once against a
fresh database, after applying sql/002_layer0_registries.sql.

    python -m sahacore.data.load_nutrients
"""
import json
from pathlib import Path

from sahacore.db import get_connection

DATA_FILE = Path(__file__).parent / "nutrients_81.json"


def load_nutrients() -> int:
    records = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    conn = get_connection()
    with conn.cursor() as cur:
        for rec in records:
            cur.execute(
                """
                INSERT INTO nutrients (code, name, unit, is_nitrate)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (code) DO UPDATE SET
                    name = EXCLUDED.name,
                    unit = EXCLUDED.unit,
                    is_nitrate = EXCLUDED.is_nitrate
                """,
                (rec["id"], rec["name"], rec["unit"], rec["is_nitrate"]),
            )
    conn.commit()
    conn.close()
    return len(records)


if __name__ == "__main__":
    n = load_nutrients()
    print(f"loaded {n} nutrients")
