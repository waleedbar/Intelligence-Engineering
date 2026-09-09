"""Seeds engine_internal.datamap_variable and datamap_onboarding_field from
datamap.json. Requires sql/022_datamap.sql to already be applied.

    python -m sahacore.data.load_datamap
"""
import json
from pathlib import Path

from sahacore.db import get_connection

DATA_FILE = Path(__file__).parent / "datamap.json"

_TABLES = {
    "variables": ("engine_internal.datamap_variable",
                  ["source_row", "variable", "layer", "equations",
                   "full_description", "physiological_meaning", "units",
                   "typical_range", "data_source", "specific_source",
                   "update_frequency"]),
    "onboarding_fields": ("engine_internal.datamap_onboarding_field",
                          ["source_row", "step", "screen", "field_name",
                           "input_type", "engine_variable", "target_layer",
                           "equations", "mapping_logic", "default_if_missing",
                           "priority"]),
}


def load_datamap() -> dict[str, int]:
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    conn = get_connection()
    loaded = {}
    with conn.cursor() as cur:
        for key, (table, columns) in _TABLES.items():
            placeholders = ", ".join(f"%({c})s" for c in columns)
            update_clause = ", ".join(
                f"{c} = EXCLUDED.{c}" for c in columns if c != "source_row")
            for row in data[key]:
                cur.execute(
                    f"""
                    INSERT INTO {table} ({", ".join(columns)})
                    VALUES ({placeholders})
                    ON CONFLICT (source_row) DO UPDATE SET {update_clause}
                    """,
                    {c: row[c] for c in columns},
                )
            loaded[key] = len(data[key])
    conn.commit()
    conn.close()
    return loaded


if __name__ == "__main__":
    n = load_datamap()
    print(f"loaded {n['variables']} engine variables and "
          f"{n['onboarding_fields']} onboarding fields")
