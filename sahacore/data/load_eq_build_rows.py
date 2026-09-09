"""Seeds engine_internal.eq_build_rows and its input tokens from
eq_build_rows.json. Requires sql/013_eq_build_rows.sql to already be applied.

    python -m sahacore.data.load_eq_build_rows
"""
import json
from pathlib import Path

from sahacore.db import get_connection

DATA_FILE = Path(__file__).parent / "eq_build_rows.json"

_COLUMNS = [
    "source_row", "eq_id", "layer_module", "formula_or_rule", "inputs_verbatim",
    "outputs", "units", "cadence", "parameter_registry_ref",
    "python_module_function", "validation_test", "evidence_provenance",
    "production_status", "covers_fk_eq_ids",
]


def load_eq_build_rows() -> tuple[int, int]:
    rows = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    placeholders = ", ".join(f"%({c})s" for c in _COLUMNS)
    update_clause = ", ".join(f"{c} = EXCLUDED.{c}" for c in _COLUMNS if c != "source_row")

    conn = get_connection()
    tokens = 0
    with conn.cursor() as cur:
        for row in rows:
            cur.execute(
                f"""
                INSERT INTO engine_internal.eq_build_rows ({", ".join(_COLUMNS)})
                VALUES ({placeholders})
                ON CONFLICT (source_row) DO UPDATE SET {update_clause}
                """,
                {c: row[c] for c in _COLUMNS},
            )
            # Rebuilt wholesale so a token that stops being an input does not
            # linger as a stale row.
            cur.execute(
                "DELETE FROM engine_internal.eq_build_row_inputs WHERE source_row = %s",
                (row["source_row"],),
            )
            for i, tok in enumerate(row["input_tokens"]):
                cur.execute(
                    """
                    INSERT INTO engine_internal.eq_build_row_inputs
                        (source_row, token_order, token, kind, registry_symbol,
                         candidates)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (row["source_row"], i, tok["token"], tok["kind"],
                     tok["registry_symbol"], tok.get("candidates", [])),
                )
                tokens += 1
    conn.commit()
    conn.close()
    return len(rows), tokens


if __name__ == "__main__":
    n, t = load_eq_build_rows()
    print(f"loaded {n} rows into engine_internal.eq_build_rows ({t} input tokens)")
