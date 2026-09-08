"""Durable replay start points.

Source: v39sEng2.xlsx.

  'IO · Lineage DataMap' row A19 (checkpoint_state):
      Purpose:    "Durable replay start point"
      Core fields: "user_id, effective_at, knowledge_at, model_shape_version,
                    posterior_version, exposure_version, m_version,
                    signature_version, warning_version, lineage_hash"
      Versioning:  "immutable checkpoint; newer checkpoint never mutates
                    older one"
      Validation:  "checkpoint strictly precedes replay effective_at"

  'Replay Contract' section A, step 3 (BUILD_LOCKED), verbatim:

      "Select the latest durable checkpoint strictly before the earliest
       evidence-support time. For point measurements this may equal
       effective_at; for E_WINDOWED measurements it precedes specimen_at.
       The checkpoint declares model shape, registries and parent versions."
      Why: "A checkpoint after any time represented by the new observation
       already contains the wrong inferred history."
      Acceptance test (G9): "checkpoint.as_of_effective_time <
       evidence_support_start and no later eligible checkpoint exists"

The DataMap calls the column `effective_at` and the acceptance test calls the
same clock `as_of_effective_time`; they are the one physiological time the
checkpoint was taken at.

Selecting the checkpoint is this module's job (a key/lookup concern the
ledger owns). RESTORING the state it points at is
`sahacore.replay.restore_checkpoint`, which belongs to Layer E's build step.
"""
import uuid
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sahacore.ledger.lineage import lineage_hash


class NoEligibleCheckpoint(LookupError):
    """Raised when no durable checkpoint precedes the evidence-support time.

    This is not a recoverable default: replaying from a checkpoint taken
    after the evidence starts would carry forward exactly the wrong inferred
    history that step 3 exists to discard. The correct handling is the
    Replay Contract's step 11 escape -- an approved deep replay from an
    earlier durable checkpoint, or an explicitly recorded
    CURRENT_TIME_ANCHOR_ONLY -- both of which are decisions with an owner,
    not a silent fallback.
    """


@dataclass(frozen=True)
class Checkpoint:
    checkpoint_id: UUID
    user_id: UUID
    effective_at: datetime
    knowledge_at: datetime
    model_shape_version: str
    posterior_version: str | None
    exposure_version: str | None
    m_version: str | None
    signature_version: str | None
    warning_version: str | None
    lineage_hash: str


_SELECT_LATEST_ELIGIBLE = """
SELECT checkpoint_id, user_id, effective_at, knowledge_at, model_shape_version,
       posterior_version, exposure_version, m_version, signature_version,
       warning_version, lineage_hash
FROM engine_internal.checkpoint_state
WHERE user_id = %(user_id)s
  AND durable
  AND effective_at < %(evidence_support_start)s
ORDER BY effective_at DESC, knowledge_at DESC
LIMIT 1
"""


def select_replay_checkpoint(
    conn, *, user_id: UUID, evidence_support_start: datetime
) -> Checkpoint:
    """Step 3, as one query.

    `effective_at < evidence_support_start` is the sheet's "strictly before"
    -- a checkpoint taken at the exact instant the evidence begins is NOT
    eligible, because it already contains inferred history for that instant.
    `ORDER BY effective_at DESC ... LIMIT 1` is its "no later eligible
    checkpoint exists".
    """
    with conn.cursor() as cur:
        cur.execute(
            _SELECT_LATEST_ELIGIBLE,
            {"user_id": user_id, "evidence_support_start": evidence_support_start},
        )
        row = cur.fetchone()

    if row is None:
        raise NoEligibleCheckpoint(
            f"no durable checkpoint for user {user_id} strictly precedes "
            f"{evidence_support_start.isoformat()}"
        )
    return Checkpoint(**row)


_INSERT = """
INSERT INTO engine_internal.checkpoint_state (
    checkpoint_id, user_id, effective_at, knowledge_at, model_shape_version,
    posterior_version, exposure_version, m_version, signature_version,
    warning_version, durable, lineage_hash
) VALUES (
    %(checkpoint_id)s, %(user_id)s, %(effective_at)s, %(knowledge_at)s,
    %(model_shape_version)s, %(posterior_version)s, %(exposure_version)s,
    %(m_version)s, %(signature_version)s, %(warning_version)s, %(durable)s,
    %(lineage_hash)s
)
RETURNING checkpoint_id
"""


def write_checkpoint(
    conn,
    *,
    user_id: UUID,
    effective_at: datetime,
    knowledge_at: datetime,
    model_shape_version: str,
    posterior_version: str | None = None,
    exposure_version: str | None = None,
    m_version: str | None = None,
    signature_version: str | None = None,
    warning_version: str | None = None,
    durable: bool = True,
) -> UUID:
    """Record a checkpoint. The row is trigger-locked against UPDATE and
    DELETE in sql/009_ledger.sql, which is G19's "newer checkpoint never
    mutates older one" enforced by the database rather than by convention.

    The checkpoint "declares model shape, registries and parent versions", so
    every declared version is folded into its lineage_hash: two checkpoints
    at the same instant under different model shapes are different objects
    and must not share a hash.
    """
    checkpoint_id = uuid.uuid4()
    row_hash = lineage_hash(
        {
            "checkpoint_id": checkpoint_id,
            "user_id": user_id,
            "effective_at": effective_at,
            "knowledge_at": knowledge_at,
            "model_shape_version": model_shape_version,
            "posterior_version": posterior_version,
            "exposure_version": exposure_version,
            "m_version": m_version,
            "signature_version": signature_version,
            "warning_version": warning_version,
        }
    )
    with conn.cursor() as cur:
        cur.execute(
            _INSERT,
            {
                "checkpoint_id": checkpoint_id,
                "user_id": user_id,
                "effective_at": effective_at,
                "knowledge_at": knowledge_at,
                "model_shape_version": model_shape_version,
                "posterior_version": posterior_version,
                "exposure_version": exposure_version,
                "m_version": m_version,
                "signature_version": signature_version,
                "warning_version": warning_version,
                "durable": durable,
                "lineage_hash": row_hash,
            },
        )
        return cur.fetchone()["checkpoint_id"]
