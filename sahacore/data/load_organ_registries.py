"""Seeds the organ systems, organ-pathway weights and nutrient targets from
organ_registries.json. Requires sql/026_organ_registries.sql to be applied.

    python -m sahacore.data.load_organ_registries
"""
import json
from pathlib import Path

from sahacore.db import get_connection

DATA_FILE = Path(__file__).parent / "organ_registries.json"

_TABLES = {
    "sys_registry": ("engine_internal.organ_system", "sys_code",
                     ["sys_code", "source_row", "organ_system",
                      "process_cluster", "note"]),
    "organ_pathway": ("engine_internal.organ_pathway_weight", "source_row",
                      ["source_row", "organ_id", "organ_node", "pathway_id",
                       "weight"]),
    "targets": ("engine_internal.nutrient_target", "variable_key",
                ["variable_key", "source_row", "display_name", "unit",
                 "daily_target", "upper_limit", "basis_source", "version"]),
}


def load_organ_registries() -> dict[str, int]:
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
    n = load_organ_registries()
    print("loaded " + ", ".join(f"{v} {k}" for k, v in n.items()))
