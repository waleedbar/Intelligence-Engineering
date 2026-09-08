"""Typed observations derived from admitted raw events.

Source: v39sEng2.xlsx, sheet 'IO · Lineage DataMap', row A6 (measurements_y):

    Purpose:    "Sensor/lab observations"
    Core fields: "type, value, unit, R_cov, effective_at, observed_at,
                  specimen_at, ingested_at, source_event_id"
    Produced by: "ledger observation adapter"   Consumed by: "Layer E"
    Versioning:  "each measurement versioned; effective_at=specimen_at for
                  labs, otherwise occurred_at/observed_at by adapter
                  contract; source ancestry retained"
    Validation:  "same source measurement applied once per active replay
                  lineage"

and sheet 'Replay Contract' step 3, which introduces the evidence-support
time this module has to compute:

    "Select the latest durable checkpoint strictly before the earliest
     evidence-support time. For point measurements this may equal
     effective_at; for E_WINDOWED measurements it precedes specimen_at."

That distinction is the whole reason support_class exists. An HbA1c is not
evidence about the morning it was drawn; it is evidence about the ~90 days
before it. Restoring a checkpoint at its specimen time would leave the
inferred history inside the window untouched by the very measurement that
describes it -- the sheet's own reason for step 3: "A checkpoint after any
time represented by the new observation already contains the wrong inferred
history."

The support window is a per-measurement-type property of the assay, not a
constant, so it is always passed in; nothing here carries a default window.
"""
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from sahacore.ledger.lineage import lineage_hash

SUPPORT_POINT = "POINT"
SUPPORT_WINDOWED = "E_WINDOWED"


class SupportWindowError(ValueError):
    """Raised when a windowed measurement is offered without the window that
    defines what it is evidence about."""


@dataclass(frozen=True)
class RecordedMeasurement:
    measurement_id: UUID
    measurement_version: int
    effective_at: datetime
    evidence_support_start: datetime
    support_class: str
    lineage_hash: str


def evidence_support_start(
    *,
    effective_at: datetime,
    support_class: str,
    support_window_days: float | None = None,
) -> datetime:
    """The earliest physiological time this measurement carries information
    about -- the quantity Replay Contract step 3 rewinds to.

    POINT      -> effective_at itself ("for point measurements this may equal
                  effective_at").
    E_WINDOWED -> effective_at minus the assay's integration window ("for
                  E_WINDOWED measurements it precedes specimen_at").
    """
    if support_class == SUPPORT_POINT:
        return effective_at
    if support_class != SUPPORT_WINDOWED:
        raise ValueError(f"unknown support_class {support_class!r}")
    if support_window_days is None or support_window_days <= 0.0:
        raise SupportWindowError(
            "an E_WINDOWED measurement needs a positive support_window_days; "
            "without it the replay cannot know how far back to rewind, and "
            "would silently leave the window it describes unrevised"
        )
    return effective_at - timedelta(days=support_window_days)


def earliest_evidence_support_start(measurements) -> datetime:
    """Step 3 rewinds to "the EARLIEST evidence-support time" across the
    evidence that triggered the replay, not to each measurement's own."""
    starts = [m.evidence_support_start for m in measurements]
    if not starts:
        raise ValueError("no measurements: there is no evidence-support time to rewind to")
    return min(starts)


_INSERT = """
INSERT INTO engine_internal.measurements_y (
    measurement_id, measurement_version, user_id, measurement_type, value, unit,
    r_cov, effective_at, observed_at, specimen_at, ingested_at, knowledge_at,
    source_event_id, is_lab, support_class, evidence_support_start,
    status, lineage_hash
) VALUES (
    %(measurement_id)s, %(measurement_version)s, %(user_id)s, %(measurement_type)s,
    %(value)s, %(unit)s, %(r_cov)s, %(effective_at)s, %(observed_at)s, %(specimen_at)s,
    %(ingested_at)s, %(knowledge_at)s, %(source_event_id)s, %(is_lab)s,
    %(support_class)s, %(evidence_support_start)s, 'ACTIVE', %(lineage_hash)s
)
RETURNING measurement_id, measurement_version, effective_at,
          evidence_support_start, support_class, lineage_hash
"""


def record_measurement(
    conn,
    *,
    user_id: UUID,
    measurement_type: str,
    value: float,
    unit: str,
    r_cov: float,
    source_event_id: UUID,
    effective_at: datetime,
    knowledge_at: datetime,
    ingested_at: datetime,
    parent_event_hash: str,
    observed_at: datetime | None = None,
    specimen_at: datetime | None = None,
    is_lab: bool = False,
    support_class: str = SUPPORT_POINT,
    support_window_days: float | None = None,
    measurement_version: int = 1,
) -> RecordedMeasurement:
    """Write one typed observation, descended from an already-admitted raw
    event.

    The database refuses a second ACTIVE row for the same
    (source_event_id, measurement_type) -- the DataMap's "same source
    measurement applied once per active replay lineage". Superseding the
    existing row (via `supersede_measurement`) is the only way to record a
    revised reading of the same source, which keeps the old interpretation
    auditable instead of overwritten.
    """
    support_start = evidence_support_start(
        effective_at=effective_at,
        support_class=support_class,
        support_window_days=support_window_days,
    )
    measurement_id = uuid.uuid4()
    row_hash = lineage_hash(
        {
            "measurement_id": measurement_id,
            "measurement_version": measurement_version,
            "user_id": user_id,
            "measurement_type": measurement_type,
            "value": value,
            "unit": unit,
            "r_cov": r_cov,
            "effective_at": effective_at,
            "evidence_support_start": support_start,
            "source_event_id": source_event_id,
        },
        parents=[parent_event_hash],
    )

    with conn.cursor() as cur:
        cur.execute(
            _INSERT,
            {
                "measurement_id": measurement_id,
                "measurement_version": measurement_version,
                "user_id": user_id,
                "measurement_type": measurement_type,
                "value": value,
                "unit": unit,
                "r_cov": r_cov,
                "effective_at": effective_at,
                "observed_at": observed_at,
                "specimen_at": specimen_at,
                "ingested_at": ingested_at,
                "knowledge_at": knowledge_at,
                "source_event_id": source_event_id,
                "is_lab": is_lab,
                "support_class": support_class,
                "evidence_support_start": support_start,
                "lineage_hash": row_hash,
            },
        )
        row = cur.fetchone()

    return RecordedMeasurement(
        measurement_id=row["measurement_id"],
        measurement_version=row["measurement_version"],
        effective_at=row["effective_at"],
        evidence_support_start=row["evidence_support_start"],
        support_class=row["support_class"],
        lineage_hash=row["lineage_hash"],
    )


def supersede_measurement(conn, measurement_id: UUID) -> None:
    """Mark a measurement version superseded. Replay Contract step 8:
    "Supersede and invalidate old derived descendants, but never delete
    them." The row stays queryable through the knowledge-time view; only its
    ACTIVE status is released, which frees the unique index for the revised
    version. Which replay did it is recorded on the ReplayJob receipt's
    old_version_ids, not on the packet."""
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE engine_internal.measurements_y SET status = 'SUPERSEDED' "
            "WHERE measurement_id = %s AND status = 'ACTIVE'",
            (measurement_id,),
        )
