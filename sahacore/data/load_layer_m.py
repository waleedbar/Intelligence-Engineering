"""Seeds layer_m_scarring_params from layer_m_scarring_params_12.json.
Requires sql/006_layer_m_scarring.sql to already be applied.

    python -m sahacore.data.load_layer_m
"""
import json
from pathlib import Path

from sahacore.db import get_connection

DATA_FILE = Path(__file__).parent / "layer_m_scarring_params_12.json"

_COLUMNS = [
    "cluster_id", "theta_elastic_au", "theta_elastic_evidence_tier",
    "gamma_scar", "max_alpha_beta_ratio", "bound_gamma_r",
]


def load_layer_m() -> int:
    rows = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    placeholders = ", ".join(f"%({c})s" for c in _COLUMNS)
    update_clause = ", ".join(f"{c} = EXCLUDED.{c}" for c in _COLUMNS if c != "cluster_id")

    conn = get_connection()
    with conn.cursor() as cur:
        for row in rows:
            cur.execute(
                f"""
                INSERT INTO layer_m_scarring_params ({", ".join(_COLUMNS)})
                VALUES ({placeholders})
                ON CONFLICT (cluster_id) DO UPDATE SET {update_clause}
                """,
                row,
            )
    conn.commit()
    conn.close()
    return len(rows)


if __name__ == "__main__":
    n = load_layer_m()
    print(f"loaded {n} rows into layer_m_scarring_params")
