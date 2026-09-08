"""Per-event quality and uncertainty verdicts.

Source: v39sEng2.xlsx, sheet 'IO · Lineage DataMap', row A4 (event_quality):

    Purpose:     "Quality and uncertainty metadata for each event"
    Core fields: "source_type, device_model, confidence, CV, missingness,
                  outlier_flag"
    Produced by: "ingest pipeline"
    Consumed by: "Layer E, U-Ledger, UI confidence"
    Versioning:  "updates create new quality version"
    Validation:  "uncertain photo portions widen input noise"

The verdict is stored apart from the fact for a reason the append-only rule
makes unavoidable: raw_events is immutable, so a re-scored photo or a
recalibrated device cannot edit the event it describes. It writes a NEW
quality version instead, and the previous verdict is superseded rather than
lost -- which keeps "what did the engine think of this reading when it acted
on it?" answerable after the re-score.

That validation cell is a Layer E instruction, not a Layer E implementation:
this module records confidence, CV and missingness; the mapping from them
into a widened R is Layer E's, in build step 5.
"""
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sahacore.ledger.lineage import lineage_hash


@dataclass(frozen=True)
class QualityVerdict:
    event_uuid: UUID
    quality_version: int
    lineage_hash: str


_SUPERSEDE_ACTIVE = """
UPDATE engine_internal.event_quality
SET status = 'SUPERSEDED'
WHERE event_uuid = %(event_uuid)s AND status = 'ACTIVE'
RETURNING quality_version
"""

_INSERT = """
INSERT INTO engine_internal.event_quality (
    event_uuid, quality_version, source_type, device_model, confidence, cv,
    missingness, outlier_flag, status, knowledge_at, lineage_hash
) VALUES (
    %(event_uuid)s, %(quality_version)s, %(source_type)s, %(device_model)s,
    %(confidence)s, %(cv)s, %(missingness)s, %(outlier_flag)s, 'ACTIVE',
    %(knowledge_at)s, %(lineage_hash)s
)
RETURNING event_uuid, quality_version, lineage_hash
"""


def record_event_quality(
    conn,
    *,
    event_uuid: UUID,
    source_type: str,
    knowledge_at: datetime,
    parent_event_hash: str,
    device_model: str | None = None,
    confidence: float | None = None,
    cv: float | None = None,
    missingness: float | None = None,
    outlier_flag: bool = False,
) -> QualityVerdict:
    """Write a new ACTIVE quality verdict for one admitted event,
    superseding any earlier verdict on it."""
    with conn.cursor() as cur:
        cur.execute(_SUPERSEDE_ACTIVE, {"event_uuid": event_uuid})
        superseded = cur.fetchone()
        quality_version = 1 if superseded is None else superseded["quality_version"] + 1

        row_hash = lineage_hash(
            {
                "event_uuid": event_uuid,
                "quality_version": quality_version,
                "source_type": source_type,
                "device_model": device_model,
                "confidence": confidence,
                "cv": cv,
                "missingness": missingness,
                "outlier_flag": outlier_flag,
            },
            parents=[parent_event_hash],
        )

        cur.execute(
            _INSERT,
            {
                "event_uuid": event_uuid,
                "quality_version": quality_version,
                "source_type": source_type,
                "device_model": device_model,
                "confidence": confidence,
                "cv": cv,
                "missingness": missingness,
                "outlier_flag": outlier_flag,
                "knowledge_at": knowledge_at,
                "lineage_hash": row_hash,
            },
        )
        row = cur.fetchone()

    return QualityVerdict(
        event_uuid=row["event_uuid"],
        quality_version=row["quality_version"],
        lineage_hash=row["lineage_hash"],
    )


def active_event_quality(conn, event_uuid: UUID) -> dict | None:
    """The verdict currently in force for this event, or None if the ingest
    pipeline recorded none."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT * FROM engine_internal.event_quality "
            "WHERE event_uuid = %s AND status = 'ACTIVE'",
            (event_uuid,),
        )
        return cur.fetchone()
