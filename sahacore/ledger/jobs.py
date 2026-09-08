"""Replay-job keys and the lag policy that classifies them.

Source: v39sEng2.xlsx.

  'IO · Lineage DataMap' row A22 (replay_job):
      Purpose:    "Bitemporal replay receipt and invalidation map"
      Core fields: "user_id, trigger_event_id, effective_at, knowledge_at,
                    checkpoint_id, replay_horizon, old_version_ids,
                    new_version_ids, status, reason"
      Versioning:  "one immutable receipt per replay attempt; retries linked"
      Validation:  "no active descendant retains a superseded parent"

  'Replay Contract' section A, step 11 (BUILD_LOCKED), verbatim:

      "Inside the configured fixed lag, use routine replay. Outside the lag,
       run an approved deep replay from a durable checkpoint or record
       CURRENT_TIME_ANCHOR_ONLY. Never silently replay E while leaving old
       M/W/signatures."
      Why: "Cost and validity must be explicit beyond the routine buffer."
      Acceptance test (G17): "ReplayJob records policy, approver/reason and
       horizon"

  'H · U-Ledger Fusion Rules' row A14 ("Late event outside lag"):
      prohibited: "Silent partial replay or mixing revised E with old M"
      why: "makes computational and clinical scope explicit"

  'Replay Contract' section F, RT-05 (RELEASE_BLOCKING): "Event beyond
  routine lag -> Deep replay or CURRENT_TIME_ANCHOR_ONLY recorded with
  reason". Failure meaning: "Silent partial replay".

THE CONFIGURED FIXED LAG is parameter 129 L_smooth on 'P1 Parameters 134+'
("Fixed-lag smoothing window -- Number of recent days re-estimated nightly
when delayed logs/labs arrive", days, range 7-14, tunable). Being a tunable,
it is read from engine_internal.replay_lag_policy and never written into
this file; `replay_policy` takes it as an argument so the pure decision is
testable without a database.
"""
import uuid
from datetime import datetime, timedelta
from uuid import UUID

ROUTINE = "ROUTINE"
DEEP_REPLAY = "DEEP_REPLAY"
CURRENT_TIME_ANCHOR_ONLY = "CURRENT_TIME_ANCHOR_ONLY"


def routine_lag_days(conn) -> float:
    """The active L_smooth window, in days, from the seeded policy row."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT l_smooth_days FROM engine_internal.replay_lag_policy "
            "WHERE status = 'ACTIVE'"
        )
        row = cur.fetchone()
    if row is None:
        raise LookupError(
            "no ACTIVE replay_lag_policy row: run "
            "`python -m sahacore.data.load_ledger_policy`. The routine lag is "
            "not defaulted in code -- an unconfigured engine must refuse to "
            "classify a replay rather than guess its scope."
        )
    return float(row["l_smooth_days"])


def replay_policy(
    *, lag_days: float, routine_lag_days: float, deep_replay_approved: bool = False
) -> str:
    """Step 11's three-way choice.

    Inside the window the replay is ROUTINE. Outside it there is no routine
    option at all: either a human has approved a deep replay from a durable
    checkpoint, or the engine records CURRENT_TIME_ANCHOR_ONLY -- an explicit
    statement that the past was NOT revised. The one outcome the sheet
    forbids is a quiet routine replay of stale history, so there is no
    branch here that returns ROUTINE for an out-of-lag event.
    """
    if lag_days <= routine_lag_days:
        return ROUTINE
    return DEEP_REPLAY if deep_replay_approved else CURRENT_TIME_ANCHOR_ONLY


_INSERT = """
INSERT INTO engine_internal.replay_job (
    replay_job_id, user_id, trigger_event_id, effective_at, knowledge_at,
    checkpoint_id, replay_horizon, policy, approver, reason,
    status, retry_of_replay_job_id
) VALUES (
    %(replay_job_id)s, %(user_id)s, %(trigger_event_id)s, %(effective_at)s,
    %(knowledge_at)s, %(checkpoint_id)s, %(replay_horizon)s, %(policy)s,
    %(approver)s, %(reason)s, 'PENDING', %(retry_of_replay_job_id)s
)
RETURNING replay_job_id
"""


def open_replay_job(
    conn,
    *,
    user_id: UUID,
    trigger_event_id: UUID,
    effective_at: datetime,
    knowledge_at: datetime,
    replay_horizon: timedelta,
    policy: str,
    checkpoint_id: UUID | None = None,
    approver: str | None = None,
    reason: str | None = None,
    retry_of_replay_job_id: UUID | None = None,
) -> UUID:
    """Open the receipt for one replay attempt and return its key.

    The receipt is written BEFORE the replay runs, so an attempt that
    crashes still leaves a record of what was attempted and under which
    policy -- "one immutable receipt per replay attempt". A retry is a new
    receipt pointing at this one, never a rewrite of it.

    The constraints that make G17 real (a non-ROUTINE job must carry a
    reason; a DEEP_REPLAY must carry an approver; anything that actually
    replays history must name its checkpoint) live in
    sql/009_ledger.sql, so they hold against every writer, not only this one.
    """
    replay_job_id = uuid.uuid4()
    with conn.cursor() as cur:
        cur.execute(
            _INSERT,
            {
                "replay_job_id": replay_job_id,
                "user_id": user_id,
                "trigger_event_id": trigger_event_id,
                "effective_at": effective_at,
                "knowledge_at": knowledge_at,
                "checkpoint_id": checkpoint_id,
                "replay_horizon": replay_horizon,
                "policy": policy,
                "approver": approver,
                "reason": reason,
                "retry_of_replay_job_id": retry_of_replay_job_id,
            },
        )
        return cur.fetchone()["replay_job_id"]


def close_replay_job(
    conn,
    replay_job_id: UUID,
    *,
    status: str,
    old_version_ids: list[str] | None = None,
    new_version_ids: list[str] | None = None,
) -> None:
    """Complete the receipt with the invalidation map: step 8's "one
    ReplayJob receipt mapping old versions to new versions"."""
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE engine_internal.replay_job
            SET status = %(status)s,
                old_version_ids = %(old_version_ids)s,
                new_version_ids = %(new_version_ids)s
            WHERE replay_job_id = %(replay_job_id)s
            """,
            {
                "replay_job_id": replay_job_id,
                "status": status,
                "old_version_ids": old_version_ids or [],
                "new_version_ids": new_version_ids or [],
            },
        )
