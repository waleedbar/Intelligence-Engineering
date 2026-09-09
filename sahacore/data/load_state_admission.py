"""Seeds the state-admission and behaviour-sidecar contract from
state_admission.json. Requires sql/024_state_admission.sql to be applied.

    python -m sahacore.data.load_state_admission
"""
import json
from pathlib import Path

from sahacore.db import get_connection

DATA_FILE = Path(__file__).parent / "state_admission.json"

_TABLES = {
    "gate_constants": ("engine_internal.state_admission_constant", "constant",
                       ["constant", "source_sheet", "source_row", "value",
                        "formula_or_source", "engineering_meaning", "owner"]),
    "candidates": ("engine_internal.state_admission_candidate", "candidate",
                   ["candidate", "source_row", "target_representation",
                    "necessity", "sidecar_adequate", "identifiable_observable",
                    "init_burden", "replay", "latency", "held_out_evidence"]),
    "admission_rules": ("engine_internal.state_admission_rule", "rule",
                        ["rule", "source_row", "formula_or_implementation",
                         "current_result", "notes"]),
    "sidecar_constants": ("engine_internal.behavior_sidecar_constant", "constant",
                          ["constant", "source_row", "value", "formula_or_note",
                           "purpose"]),
    "routing": ("engine_internal.behavior_sidecar_routing", "domain",
                ["domain", "source_row", "existing_core_states",
                 "sidecar_raw_feature", "routing"]),
    "derived_features": ("engine_internal.behavior_sidecar_feature", "feature",
                         ["feature", "source_row", "value", "formula_text",
                          "routing_meaning"]),
}


def load_state_admission() -> dict[str, int]:
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    conn = get_connection()
    loaded = {}
    with conn.cursor() as cur:
        for key, (table, pk, columns) in _TABLES.items():
            placeholders = ", ".join(f"%({c})s" for c in columns)
            update_clause = ", ".join(f"{c} = EXCLUDED.{c}" for c in columns if c != pk)
            for row in data[key]:
                cur.execute(
                    f"""
                    INSERT INTO {table} ({", ".join(columns)})
                    VALUES ({placeholders})
                    ON CONFLICT ({pk}) DO UPDATE SET {update_clause}
                    """,
                    {c: row[c] for c in columns},
                )
            loaded[key] = len(data[key])
    conn.commit()
    conn.close()
    return loaded


if __name__ == "__main__":
    n = load_state_admission()
    print("loaded " + ", ".join(f"{v} {k}" for k, v in n.items()))
