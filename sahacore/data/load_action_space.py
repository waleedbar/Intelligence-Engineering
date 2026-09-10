"""Seeds the Layer H action space from action_space_127.json into
engine_internal.action_space, action_space_info and action_space_phase.
Requires sql/014_veto_action_space.sql to already be applied.

    python -m sahacore.data.load_action_space
"""
import json
from pathlib import Path

from sahacore.db import get_connection

DATA_FILE = Path(__file__).parent / "action_space_127.json"

_TABLES = {
    "actions": (
        "engine_internal.action_space", "action_id",
        ["action_id", "source_row", "category", "subcategory", "action",
         "magnitude_bin", "primary_target", "cluster_affected",
         "veto_cross_ref", "default_reward_prior", "policy_class",
         "online_exploration_rule", "physiological_uncertainty_rule",
         "required_evaluation", "activation_hold"],
    ),
    "info_actions": (
        "engine_internal.action_space_info", "info_id",
        ["info_id", "source_row", "information_action",
         "expected_information_gain", "user_burden", "eligibility",
         "voi_score", "state_or_output_affected", "safety_veto",
         "expiration", "policy_class", "exploration", "state_uncertainty",
         "evaluation"],
    ),
    "phases": (
        "engine_internal.action_space_phase", "phase",
        ["phase", "source_row", "trigger_condition", "new_arms_activated",
         "cumulative_arms", "active_categories", "sample_threshold",
         "convergence_criterion", "safety_notes"],
    ),
}


def load_action_space() -> dict[str, int]:
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
    counts = load_action_space()
    print(f"loaded {counts['actions']} rows into engine_internal.action_space, "
          f"{counts['info_actions']} into action_space_info, "
          f"{counts['phases']} into action_space_phase")
