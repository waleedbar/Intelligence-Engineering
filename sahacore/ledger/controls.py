"""Versioned control vectors rolled up from immutable events.

Source: v39sEng2.xlsx, sheet 'IO · Lineage DataMap', row A5 (controls_u):

    Purpose:    "Control inputs from food/activity/sleep/stress/logged
                 behavior"
    Core fields: "dose_vector_81, MVPA, sleep, stress, hydration, med_flags,
                  context, parent_event_ids, as_of_effective_time"
    Produced by: "ledger rollup"        Consumed by: "Layer A/B/C/E"
    Versioning:  "versioned and recomputed from immutable events on replay;
                  parent_event_ids and lineage_hash retained"
    Validation:  "81 nutrient doses present; controls are never treated as
                  measurements"

"Controls are never treated as measurements" is a structural rule, not a
warning: controls_u carries no R_cov column at all, so there is nowhere for
a control to acquire observation noise and be fed to Layer E's update step.
A control enters the dynamics as u(t); only measurements_y enters as y.

SCOPE OF THIS MODULE. Persisting, versioning and superseding a control
vector is step 1's job, and is what is implemented here. Computing the 81
doses FROM meal payloads is not: that arithmetic needs the nutrient registry
and the food-composition mapping loaded in step 2 ('Load registries'), so
the vector is supplied by the caller and this module refuses to invent one.
`parent_event_ids` is required for the same reason -- a control vector that
cannot name the immutable events it was rolled up from cannot be
"recomputed from immutable events on replay", which is the whole contract.
"""
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from psycopg.types.json import Jsonb

from sahacore.ledger.lineage import lineage_hash

NUTRIENT_COUNT = 81


class ControlVectorShapeError(ValueError):
    """Raised when the dose vector is not exactly 81 long.

    Replay Contract section E, correction "Nutrient count": "Some contracts
    still used 80 doses/exposure states ... 81 nutrient doses; exposure_state
    has 81 fast + 81 slow states" (status PATCHED). An 80-long vector is the
    named pre-nitrate defect, so it is rejected in Python as well as by the
    table's CHECK constraint -- a caller gets the diagnosis rather than a
    constraint violation.
    """


@dataclass(frozen=True)
class ControlVersion:
    user_id: UUID
    effective_time: datetime
    control_version: int
    lineage_hash: str


_SUPERSEDE_ACTIVE = """
UPDATE engine_internal.controls_u
SET status = 'SUPERSEDED'
WHERE user_id = %(user_id)s
  AND effective_time = %(effective_time)s
  AND status = 'ACTIVE'
RETURNING control_version
"""

_INSERT = """
INSERT INTO engine_internal.controls_u (
    user_id, effective_time, control_version, dose_vector_81, mvpa_min,
    sleep_h, stress, hydration_ml, med_flags, context, parent_event_ids,
    as_of_effective_time, as_of_knowledge_time, status, lineage_hash,
    replay_job_id
) VALUES (
    %(user_id)s, %(effective_time)s, %(control_version)s, %(dose_vector_81)s,
    %(mvpa_min)s, %(sleep_h)s, %(stress)s, %(hydration_ml)s, %(med_flags)s,
    %(context)s, %(parent_event_ids)s, %(as_of_effective_time)s,
    %(as_of_knowledge_time)s, 'ACTIVE', %(lineage_hash)s, %(replay_job_id)s
)
RETURNING user_id, effective_time, control_version, lineage_hash
"""


def write_control_vector(
    conn,
    *,
    user_id: UUID,
    effective_time: datetime,
    dose_vector_81: list[float],
    parent_event_ids: list[UUID],
    as_of_effective_time: datetime,
    as_of_knowledge_time: datetime,
    parent_event_hashes: list[str],
    mvpa_min: float | None = None,
    sleep_h: float | None = None,
    stress: float | None = None,
    hydration_ml: float | None = None,
    med_flags: list[str] | None = None,
    context: dict[str, Any] | None = None,
    replay_job_id: UUID | None = None,
) -> ControlVersion:
    """Write a new ACTIVE control version, superseding any existing one at
    the same (user_id, effective_time).

    This is the shape of "recomputed from immutable events on replay": the
    old version is marked SUPERSEDED rather than deleted, so what the engine
    previously believed the user consumed at that time stays auditable, and
    the new version's lineage_hash descends from the hashes of the events it
    was rolled up from.
    """
    if len(dose_vector_81) != NUTRIENT_COUNT:
        raise ControlVectorShapeError(
            f"dose vector has {len(dose_vector_81)} entries, not {NUTRIENT_COUNT}"
        )
    if not parent_event_ids:
        raise ValueError(
            "a control vector must name the immutable events it was rolled up "
            "from; without them it cannot be recomputed on replay"
        )

    with conn.cursor() as cur:
        cur.execute(_SUPERSEDE_ACTIVE, {"user_id": user_id, "effective_time": effective_time})
        superseded = cur.fetchone()
        control_version = 1 if superseded is None else superseded["control_version"] + 1

        row_hash = lineage_hash(
            {
                "user_id": user_id,
                "effective_time": effective_time,
                "control_version": control_version,
                "dose_vector_81": list(dose_vector_81),
                "mvpa_min": mvpa_min,
                "sleep_h": sleep_h,
                "stress": stress,
                "hydration_ml": hydration_ml,
                "med_flags": sorted(med_flags or []),
                "context": context or {},
                "as_of_effective_time": as_of_effective_time,
                "as_of_knowledge_time": as_of_knowledge_time,
            },
            parents=parent_event_hashes,
        )

        cur.execute(
            _INSERT,
            {
                "user_id": user_id,
                "effective_time": effective_time,
                "control_version": control_version,
                "dose_vector_81": list(dose_vector_81),
                "mvpa_min": mvpa_min,
                "sleep_h": sleep_h,
                "stress": stress,
                "hydration_ml": hydration_ml,
                "med_flags": med_flags or [],
                "context": Jsonb(context or {}),
                "parent_event_ids": list(parent_event_ids),
                "as_of_effective_time": as_of_effective_time,
                "as_of_knowledge_time": as_of_knowledge_time,
                "lineage_hash": row_hash,
                "replay_job_id": replay_job_id,
            },
        )
        row = cur.fetchone()

    return ControlVersion(
        user_id=row["user_id"],
        effective_time=row["effective_time"],
        control_version=row["control_version"],
        lineage_hash=row["lineage_hash"],
    )


def active_control_vector(conn, *, user_id: UUID, effective_time: datetime) -> dict | None:
    """The single ACTIVE control version at this time, or None. The partial
    unique index in sql/009_ledger.sql guarantees there is at most one."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT * FROM engine_internal.controls_u
            WHERE user_id = %s AND effective_time = %s AND status = 'ACTIVE'
            """,
            (user_id, effective_time),
        )
        return cur.fetchone()
