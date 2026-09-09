"""Seeds engine_internal.nutrient_class and nutrient_class_assignment from
nutrient_classes.json. Requires sql/018_nutrient_classes.sql to be applied.

    python -m sahacore.data.load_nutrient_classes
"""
import json
from pathlib import Path

from sahacore.db import get_connection

DATA_FILE = Path(__file__).parent / "nutrient_classes.json"

_TABLES = {
    "classes": ("engine_internal.nutrient_class", "class_code",
                ["class_code", "source_row", "name", "kinetic_character",
                 "modelling_consequence"]),
    "nutrients": ("engine_internal.nutrient_class_assignment", "nutrient_code",
                  ["nutrient_code", "source_row", "num", "class_code",
                   "observation_anchor", "endogenous_dominant"]),
}


def load_nutrient_classes() -> dict[str, int]:
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    conn = get_connection()
    loaded = {}
    with conn.cursor() as cur:
        # Classes first: the assignments reference them.
        for key in ("classes", "nutrients"):
            table, pk, columns = _TABLES[key]
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
    n = load_nutrient_classes()
    print(f"loaded {n['classes']} kinetic classes and {n['nutrients']} "
          "nutrient assignments")
