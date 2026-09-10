"""Seeds the fifteen TVMCD pathways and their cluster membership.
Requires sql/034_tvmcd_pathways.sql to already be applied.

    python -m sahacore.data.load_tvmcd_pathways
"""
import json
from pathlib import Path

from sahacore.db import get_connection

DATA_FILE = Path(__file__).parent / "tvmcd_pathways_build.json"

_PATHWAY_COLUMNS = ["pathway_id", "source_row", "biological_meaning",
                    "state_variable", "ode", "inputs", "parameters",
                    "integration_cadence", "numerical_method", "bounds",
                    "initialization", "uncertainty_treatment",
                    "validation_scenario"]
_OUTPUT_COLUMNS = ["pathway_id", "cluster_id", "list_position"]


def _upsert(cur, table: str, columns: list[str], key: str, rows: list[dict]) -> None:
    keys = {k.strip() for k in key.split(",")}
    placeholders = ", ".join(f"%({c})s" for c in columns)
    updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in columns if c not in keys)
    for row in rows:
        cur.execute(
            f"""
            INSERT INTO {table} ({", ".join(columns)})
            VALUES ({placeholders})
            ON CONFLICT ({key}) DO UPDATE SET {updates}
            """,
            {c: row[c] for c in columns},
        )


def load_tvmcd_pathways() -> dict[str, int]:
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    outputs = [{"pathway_id": p["pathway_id"], "cluster_id": cluster,
                "list_position": position}
               for p in data["pathways"]
               for position, cluster in enumerate(p["cluster_outputs"])]

    conn = get_connection()
    with conn.cursor() as cur:
        _upsert(cur, "engine_internal.tvmcd_pathway",
                _PATHWAY_COLUMNS, "pathway_id", data["pathways"])
        _upsert(cur, "engine_internal.tvmcd_cluster_output",
                _OUTPUT_COLUMNS, "pathway_id, cluster_id", outputs)
    conn.commit()
    conn.close()
    return {"tvmcd_pathway": len(data["pathways"]),
            "tvmcd_cluster_output": len(outputs)}


if __name__ == "__main__":
    for table, n in load_tvmcd_pathways().items():
        print(f"loaded {n} rows into engine_internal.{table}")
