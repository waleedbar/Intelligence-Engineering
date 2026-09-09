"""Seeds the '★ Scarring Bistability Guard' tables from bistability_guard.json.
Requires sql/027_bistability_guard.sql to already be applied.

    python -m sahacore.data.load_bistability_guard

The caps table merges the sheet's section 3 with its section 8 verification
receipt. The extractor has already required the two to agree cluster by
cluster, so merging loses nothing; keeping them apart in the database would
invite a join that could only ever return equality.
"""
import json
from pathlib import Path

from sahacore.db import get_connection

DATA_FILE = Path(__file__).parent / "bistability_guard.json"

_CAP_COLUMNS = ["cluster_id", "cluster_name", "source_row", "tau_dam_days",
                "tau_heal_days", "v_repair", "cap_gamma_r", "gamma_scar",
                "max_alpha_beta_ratio", "f_prime_min_at_cap", "receipt_agrees"]
_GUARD_COLUMNS = ["guard_id", "source_row", "name", "specification", "placement"]
_DECISION_COLUMNS = ["option", "source_row", "meaning", "status"]
_RANGE_COLUMNS = ["quantity", "source_row", "value", "consequence"]


def _upsert(cur, table: str, columns: list[str], key: str, rows: list[dict]) -> None:
    placeholders = ", ".join(f"%({c})s" for c in columns)
    updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in columns if c != key)
    for row in rows:
        cur.execute(
            f"""
            INSERT INTO {table} ({", ".join(columns)})
            VALUES ({placeholders})
            ON CONFLICT ({key}) DO UPDATE SET {updates}
            """,
            {c: row[c] for c in columns},
        )


def load_bistability_guard() -> dict[str, int]:
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))

    receipt = {row["cluster_id"]: row for row in data["receipt"]}
    caps = []
    for cap in data["caps"]:
        got = receipt[cap["cluster_id"]]
        caps.append({**cap,
                     "f_prime_min_at_cap": got["f_prime_min_at_cap"],
                     "receipt_agrees": got["agrees"]})

    conn = get_connection()
    with conn.cursor() as cur:
        _upsert(cur, "engine_internal.bistability_cap",
                _CAP_COLUMNS, "cluster_id", caps)
        _upsert(cur, "engine_internal.bistability_probabilistic_guard",
                _GUARD_COLUMNS, "guard_id", data["probabilistic_guards"])
        _upsert(cur, "engine_internal.bistability_decision",
                _DECISION_COLUMNS, "option", data["founder_decision"])
        _upsert(cur, "engine_internal.bistability_unconstrained_range",
                _RANGE_COLUMNS, "quantity", data["unconstrained_ranges"])
    conn.commit()
    conn.close()
    return {
        "bistability_cap": len(caps),
        "bistability_probabilistic_guard": len(data["probabilistic_guards"]),
        "bistability_decision": len(data["founder_decision"]),
        "bistability_unconstrained_range": len(data["unconstrained_ranges"]),
    }


if __name__ == "__main__":
    for table, n in load_bistability_guard().items():
        print(f"loaded {n} rows into engine_internal.{table}")
