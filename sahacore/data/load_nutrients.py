"""Seeds the Layer 0 `nutrients` table from the canonical 81-nutrient registry
(sourced from Dr. Ali's P1 Nutrients 81 sheet, v39sEng2). Run once against a
fresh database, after applying sql/002_layer0_registries.sql.

    python -m sahacore.data.load_nutrients
"""
import json
from pathlib import Path

from sahacore.db import get_connection

DATA_FILE = Path(__file__).parent / "nutrients_81.json"

# JSON field name -> nutrients column name, in insertion order.
_FIELD_TO_COLUMN = {
    "id": "code",
    "num": "num",
    "name": "name",
    "category": "category",
    "unit": "unit",
    "is_nitrate": "is_nitrate",
    "state_semantics": "state_semantics",
    "canonical_state_unit": "canonical_state_unit",
    "gamma_k_shape": "gamma_k_shape",
    "gamma_theta_min": "gamma_theta_min",
    "lambda_per_min": "lambda_per_min",
    "kappa_fast": "kappa_fast",
    "kappa_slow": "kappa_slow",
    "w_fast": "w_fast",
    "half_life_fast_d": "half_life_fast_d",
    "half_life_slow_d": "half_life_slow_d",
    "v_f_dl": "v_f_dl",
    "f_max": "f_max",
    "s_hi_log": "s_hi_log",
    "s_lo_log": "s_lo_log",
    "evidence_prior": "evidence_prior",
}


def _normalize(record: dict) -> dict:
    """Map JSON field names to column names, converting the registry's
    '—' placeholder (no slow pool) to SQL NULL."""
    row = {col: record[field] for field, col in _FIELD_TO_COLUMN.items()}
    if row["half_life_slow_d"] == "—":
        row["half_life_slow_d"] = None
    return row


def load_nutrients() -> int:
    records = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    rows = [_normalize(r) for r in records]
    columns = list(_FIELD_TO_COLUMN.values())
    placeholders = ", ".join(f"%({c})s" for c in columns)
    update_clause = ", ".join(f"{c} = EXCLUDED.{c}" for c in columns if c != "code")

    conn = get_connection()
    with conn.cursor() as cur:
        for row in rows:
            cur.execute(
                f"""
                INSERT INTO engine_internal.nutrients ({", ".join(columns)})
                VALUES ({placeholders})
                ON CONFLICT (code) DO UPDATE SET {update_clause}
                """,
                row,
            )
    conn.commit()
    conn.close()
    return len(rows)


if __name__ == "__main__":
    n = load_nutrients()
    print(f"loaded {n} nutrients")
