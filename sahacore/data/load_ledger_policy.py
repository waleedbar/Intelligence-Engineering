"""Seeds engine_internal.replay_lag_policy from ledger_replay_policy.json.
Requires sql/009_ledger.sql to already be applied.

    python -m sahacore.data.load_ledger_policy
"""
import json
from pathlib import Path

from sahacore.db import get_connection

DATA_FILE = Path(__file__).parent / "ledger_replay_policy.json"

_COLUMNS = [
    "policy_id", "l_smooth_days", "l_smooth_min_days", "l_smooth_max_days",
    "param_row", "source_sheet", "status",
]


def load_ledger_policy() -> int:
    rows = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    placeholders = ", ".join(f"%({c})s" for c in _COLUMNS)
    update_clause = ", ".join(f"{c} = EXCLUDED.{c}" for c in _COLUMNS if c != "policy_id")

    conn = get_connection()
    with conn.cursor() as cur:
        for row in rows:
            cur.execute(
                f"""
                INSERT INTO engine_internal.replay_lag_policy ({", ".join(_COLUMNS)})
                VALUES ({placeholders})
                ON CONFLICT (policy_id) DO UPDATE SET {update_clause}
                """,
                row,
            )
    conn.commit()
    conn.close()
    return len(rows)


if __name__ == "__main__":
    n = load_ledger_policy()
    print(f"loaded {n} rows into engine_internal.replay_lag_policy")
