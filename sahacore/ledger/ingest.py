"""Admitting a raw event, idempotently.

Source: v39sEng2.xlsx.

  'Replay Contract' section A, step 2 (BUILD_LOCKED), transcribed verbatim:

      "Deduplicate by adapter_source_id + source_event_id. A correction is a
       new event linked by correction_of_event_id; never overwrite the old
       fact."
      Why: "One physical observation must not update the filter twice."
      Objects preserved: "All original event rows."
      Owner / function: sahacore.ledger.ingest_event
      Acceptance test (G8): "duplicate delivery leaves active posterior
       unchanged"

  'H · U-Ledger Fusion Rules' row A10 (BUILD_LOCKED):

      Handoff: "Duplicate event" | Quantity: "Same source_event_id delivered
      twice" | Correct method: "Idempotent no-op on second delivery" |
      Explicitly prohibited: "Second Kalman update" | Why: "prevents
      duplicate evidence" | Validation: "posterior unchanged after duplicate"

  'IO · Lineage DataMap' row A3, validation cell: "duplicate delivery no-op;
  original fact is never overwritten".

  'Replay Contract' section F, RT-02 (RELEASE_BLOCKING): "Same lab delivered
  twice -> Second delivery is a no-op". Failure meaning: "Duplicate evidence
  stacking".

Three properties together make the no-op real rather than merely usual:

1. event_uuid is DERIVED from (adapter_source_id, source_event_id) as a
   UUIDv5, not generated at random. The same physical observation therefore
   maps to the same primary key on every delivery, in every process, and
   after a database rebuild from the same facts -- so a duplicate is
   detectable even across a replay that reconstructs the ledger.
2. The insert is ON CONFLICT DO NOTHING against the unique constraint the
   sheet names, so concurrent deliveries of the same fact race into one row
   rather than two: uniqueness is decided by the database, not by a
   check-then-insert window in application code.
3. On a duplicate this returns the STORED row, never the recomputed one.
   A second delivery carrying a different payload does not update anything
   and does not report the new payload back -- that is what "the original
   fact is never overwritten" means. A genuine change of fact is a
   correction: a NEW event carrying correction_of_event_id.
"""
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from psycopg.types.json import Jsonb

from sahacore.ledger.lineage import lineage_hash
from sahacore.ledger.times import resolve_times

# A fixed, self-describing namespace so event_uuid is reproducible from the
# source identifiers alone. Derived from a constant URL rather than written
# out as a magic literal, so the value can be re-derived and checked.
LEDGER_NAMESPACE = uuid.uuid5(uuid.NAMESPACE_URL, "https://sahacore/ledger/raw_events")

# Unit separator: cannot occur in a JSON-transported identifier, so
# ("a|b", "c") and ("a", "b|c") cannot collide onto one event_uuid.
_KEY_SEPARATOR = "\x1f"


@dataclass(frozen=True)
class IngestResult:
    """What the ledger holds for this fact after the call.

    On a duplicate every field describes the ORIGINAL admitted row, so a
    caller that logs or forwards this result cannot accidentally publish the
    rejected second payload as though it had been accepted.
    """

    event_uuid: UUID
    ingest_seq: int
    effective_at: datetime
    knowledge_at: datetime
    clock_quarantined: bool
    lineage_hash: str
    is_duplicate: bool


def event_uuid_for(adapter_source_id: str, source_event_id: str) -> UUID:
    """The deterministic event_uuid for one physical observation."""
    return uuid.uuid5(
        LEDGER_NAMESPACE, f"{adapter_source_id}{_KEY_SEPARATOR}{source_event_id}"
    )


_INSERT = """
INSERT INTO engine_internal.raw_events (
    event_uuid, adapter_source_id, source_event_id, user_id, event_type,
    effective_at, knowledge_at, occurred_at, specimen_at, observed_at,
    ingested_at, source_timezone, payload_json, quality,
    correction_of_event_id, clock_quarantined, lineage_hash
) VALUES (
    %(event_uuid)s, %(adapter_source_id)s, %(source_event_id)s, %(user_id)s, %(event_type)s,
    %(effective_at)s, %(knowledge_at)s, %(occurred_at)s, %(specimen_at)s, %(observed_at)s,
    %(ingested_at)s, %(source_timezone)s, %(payload_json)s, %(quality)s,
    %(correction_of_event_id)s, %(clock_quarantined)s, %(lineage_hash)s
)
ON CONFLICT (adapter_source_id, source_event_id) DO NOTHING
RETURNING event_uuid, ingest_seq, effective_at, knowledge_at,
          clock_quarantined, lineage_hash
"""

_SELECT_EXISTING = """
SELECT event_uuid, ingest_seq, effective_at, knowledge_at,
       clock_quarantined, lineage_hash
FROM engine_internal.raw_events
WHERE adapter_source_id = %(adapter_source_id)s
  AND source_event_id = %(source_event_id)s
"""


def ingest_event(
    conn,
    *,
    adapter_source_id: str,
    source_event_id: str,
    user_id: UUID,
    event_type: str,
    payload: dict[str, Any],
    ingested_at: datetime,
    occurred_at: datetime | None = None,
    specimen_at: datetime | None = None,
    observed_at: datetime | None = None,
    adapter_effective_at: datetime | None = None,
    accepted_at: datetime | None = None,
    source_timezone: str | None = None,
    quality: str | None = None,
    correction_of_event_id: UUID | None = None,
) -> IngestResult:
    """Admit one raw event. Delivering the same
    (adapter_source_id, source_event_id) again is a no-op that returns the
    original row with is_duplicate=True.

    A correction passes `correction_of_event_id`; it is admitted as its own
    new event with its own source_event_id, and the corrected event stays
    exactly as it was.
    """
    times = resolve_times(
        event_type=event_type,
        ingested_at=ingested_at,
        occurred_at=occurred_at,
        specimen_at=specimen_at,
        observed_at=observed_at,
        adapter_effective_at=adapter_effective_at,
        accepted_at=accepted_at,
    )
    event_uuid = event_uuid_for(adapter_source_id, source_event_id)

    # The hash covers the fact and its identity, not the ingestion
    # bookkeeping: replaying the same fact must reproduce the same hash.
    row_hash = lineage_hash(
        {
            "event_uuid": event_uuid,
            "adapter_source_id": adapter_source_id,
            "source_event_id": source_event_id,
            "user_id": user_id,
            "event_type": event_type,
            "effective_at": times.effective_at,
            "payload": payload,
            "correction_of_event_id": correction_of_event_id,
        }
    )

    params = {
        "event_uuid": event_uuid,
        "adapter_source_id": adapter_source_id,
        "source_event_id": source_event_id,
        "user_id": user_id,
        "event_type": event_type,
        "effective_at": times.effective_at,
        "knowledge_at": times.knowledge_at,
        "occurred_at": occurred_at,
        "specimen_at": specimen_at,
        "observed_at": observed_at,
        "ingested_at": ingested_at,
        "source_timezone": source_timezone,
        "payload_json": Jsonb(payload),
        "quality": quality,
        "correction_of_event_id": correction_of_event_id,
        "clock_quarantined": times.clock_quarantined,
        "lineage_hash": row_hash,
    }

    with conn.cursor() as cur:
        cur.execute(_INSERT, params)
        row = cur.fetchone()
        is_duplicate = row is None
        if is_duplicate:
            cur.execute(_SELECT_EXISTING, params)
            row = cur.fetchone()

    return IngestResult(
        event_uuid=row["event_uuid"],
        ingest_seq=row["ingest_seq"],
        effective_at=row["effective_at"],
        knowledge_at=row["knowledge_at"],
        clock_quarantined=row["clock_quarantined"],
        lineage_hash=row["lineage_hash"],
        is_duplicate=is_duplicate,
    )
