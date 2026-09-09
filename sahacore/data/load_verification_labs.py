"""Seeds the 'Live Verification Lab' tables from verification_labs.json.
Requires sql/028_verification_labs.sql to already be applied.

    python -m sahacore.data.load_verification_labs

Order matters: the labs are written before their quantities, which reference
them, and sql/027 must already have loaded the bistability caps that the
demo_point_outside_admitted_region view joins against.
"""
import json
from pathlib import Path

from sahacore.db import get_connection

DATA_FILE = Path(__file__).parent / "verification_labs.json"

_LAB_COLUMNS = ["lab_id", "source_row", "title", "side_table"]
_QUANTITY_COLUMNS = ["lab_id", "source_row", "name", "role", "formula",
                     "value_num", "value_text"]
_GAMMA_COLUMNS = ["driver_cluster", "target_cluster", "weight", "source_row"]
_ZOH_COLUMNS = ["dt_days", "source_row", "analytic_gain", "euler_gain",
                "relative_error"]
_TOPO_COLUMNS = ["component", "source_row", "tau_reference", "tau_now",
                 "difference"]
_RULE_COLUMNS = ["name", "source_row", "statement"]
_DEMO_COLUMNS = ["s_t", "z_t", "theta_elastic", "alpha_scar_per_day",
                 "beta_autophagy_per_day", "gamma_scar", "dt_days", "vmax_base"]


def _upsert(cur, table: str, columns: list[str], key: str, rows: list[dict]) -> None:
    placeholders = ", ".join(f"%({c})s" for c in columns)
    updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in columns
                        if c not in key.split(", "))
    for row in rows:
        cur.execute(
            f"""
            INSERT INTO {table} ({", ".join(columns)})
            VALUES ({placeholders})
            ON CONFLICT ({key}) DO UPDATE SET {updates}
            """,
            {c: row[c] for c in columns},
        )


def load_verification_labs() -> dict[str, int]:
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))

    quantities = [{**q, "lab_id": lab["lab_id"]}
                  for lab in data["labs"] for q in lab["quantities"]]

    matrix = data["gamma_matrix"]
    gamma = [{
        "driver_cluster": row["driver"],
        "target_cluster": matrix["clusters"][i],
        "weight": weight,
        "source_row": row["source_row"],
    } for row in matrix["rows"] for i, weight in enumerate(row["weights"])]

    demo = {c: data["layer_m_demo_point"][c] for c in _DEMO_COLUMNS}

    conn = get_connection()
    with conn.cursor() as cur:
        _upsert(cur, "engine_internal.verification_lab",
                _LAB_COLUMNS, "lab_id", data["labs"])
        _upsert(cur, "engine_internal.verification_lab_quantity",
                _QUANTITY_COLUMNS, "lab_id, name", quantities)
        _upsert(cur, "engine_internal.cluster_coupling_gamma",
                _GAMMA_COLUMNS, "driver_cluster, target_cluster", gamma)
        _upsert(cur, "engine_internal.verification_zoh_gain",
                _ZOH_COLUMNS, "dt_days", data["zoh_grid"])
        _upsert(cur, "engine_internal.verification_topology_vector",
                _TOPO_COLUMNS, "component", data["topology_vectors"])
        _upsert(cur, "engine_internal.layer_m_rule",
                _RULE_COLUMNS, "name", data["layer_m_rules"])
        cur.execute(
            f"""
            INSERT INTO engine_internal.layer_m_demo_point
                (only_row, {", ".join(_DEMO_COLUMNS)})
            VALUES (TRUE, {", ".join(f"%({c})s" for c in _DEMO_COLUMNS)})
            ON CONFLICT (only_row) DO UPDATE SET
                {", ".join(f"{c} = EXCLUDED.{c}" for c in _DEMO_COLUMNS)}
            """,
            demo,
        )
    conn.commit()
    conn.close()
    return {
        "verification_lab": len(data["labs"]),
        "verification_lab_quantity": len(quantities),
        "cluster_coupling_gamma": len(gamma),
        "verification_zoh_gain": len(data["zoh_grid"]),
        "verification_topology_vector": len(data["topology_vectors"]),
        "layer_m_rule": len(data["layer_m_rules"]),
        "layer_m_demo_point": 1,
    }


if __name__ == "__main__":
    for table, n in load_verification_labs().items():
        print(f"loaded {n} rows into engine_internal.{table}")
