"""Seeds cluster_scoring_params, nutrient_cluster_weights, and
damage_registry_canonical from their JSON seed files. Requires
sql/004_layer_c_d_registries.sql to already be applied, and `nutrients`
to already be loaded (both tables here have a nutrient_id foreign key).

    python -m sahacore.data.load_layer_c_d
"""
import json
from pathlib import Path

from sahacore.db import get_connection

DATA_DIR = Path(__file__).parent


def _load(conn, filename: str, table: str, columns: list[str], conflict_key: str) -> int:
    records = json.loads((DATA_DIR / filename).read_text(encoding="utf-8"))
    placeholders = ", ".join(f"%({c})s" for c in columns)
    update_clause = ", ".join(f"{c} = EXCLUDED.{c}" for c in columns if c not in conflict_key)
    with conn.cursor() as cur:
        for rec in records:
            cur.execute(
                f"""
                INSERT INTO {table} ({", ".join(columns)})
                VALUES ({placeholders})
                ON CONFLICT ({conflict_key}) DO UPDATE SET {update_clause}
                """,
                rec,
            )
    conn.commit()
    return len(records)


def load_layer_c_d() -> dict:
    conn = get_connection()
    counts = {
        "cluster_scoring_params": _load(
            conn, "cluster_scoring_params_12.json", "engine_internal.cluster_scoring_params",
            ["cluster_id", "a_k", "b_k", "tau_dam_days", "rho_k"], "cluster_id",
        ),
        "nutrient_cluster_weights": _load(
            conn, "nutrient_cluster_weights.json", "engine_internal.nutrient_cluster_weights",
            ["nutrient_id", "cluster_id", "weight"], "nutrient_id, cluster_id",
        ),
        "damage_registry_canonical": _load(
            conn, "damage_registry_canonical.json", "engine_internal.damage_registry_canonical",
            ["cluster_id", "nutrient_id", "weight_pct", "tau_damage_days", "tau_heal_days",
             "eta_hi", "eta_lo", "theta_hi", "theta_lo", "threshold_unit", "note"],
            "cluster_id, nutrient_id",
        ),
    }
    conn.close()
    return counts


if __name__ == "__main__":
    counts = load_layer_c_d()
    for table, n in counts.items():
        print(f"loaded {n} rows into {table}")
