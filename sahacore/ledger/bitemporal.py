"""The two query views.

Source: v39sEng2.xlsx, sheet 'Replay Contract', section A, step 10
(BUILD_LOCKED), verbatim:

    "Maintain two query views: best-current physiological history by
     effective time, and what-the-engine-knew-then history by
     knowledge/system time."
    Why: "Both scientific correction and honest audit history are needed."
    Owner / function: sahacore.lineage.bitemporal_view
    Acceptance test (G16): "the two views differ appropriately for a late
     lab"

and section F, AUD-01 (RELEASE_BLOCKING):

    "Query what engine knew before late result -> System-time view returns
     old decision context; event-time current view returns revised
     physiology"
    Failure meaning: "Bitemporal audit collapsed"

The two views over raw_events differ in exactly one way, and it is the point
of the whole design: `best_current_history` asks "what do we now believe
happened in this window?" and so filters on effective_at, admitting a lab
drawn last week but received today. `history_known_at` asks "what had the
engine actually been told by this moment?" and so filters on knowledge_at,
which excludes that same lab from every reconstruction of a decision made
before it arrived. A warning served before the lab landed must be explicable
from the second view alone -- otherwise the audit trail claims the engine
knew something it did not.
"""
from datetime import datetime
from uuid import UUID

_BEST_CURRENT = """
SELECT event_uuid, ingest_seq, adapter_source_id, source_event_id, event_type,
       effective_at, knowledge_at, payload_json, correction_of_event_id,
       lineage_hash
FROM engine_internal.raw_events
WHERE user_id = %(user_id)s
  AND effective_at >= %(effective_from)s
  AND effective_at < %(effective_to)s
ORDER BY effective_at, ingest_seq
"""

_KNOWN_AT = """
SELECT event_uuid, ingest_seq, adapter_source_id, source_event_id, event_type,
       effective_at, knowledge_at, payload_json, correction_of_event_id,
       lineage_hash
FROM engine_internal.raw_events
WHERE user_id = %(user_id)s
  AND knowledge_at <= %(knowledge_cutoff)s
  AND effective_at >= %(effective_from)s
  AND effective_at < %(effective_to)s
ORDER BY effective_at, ingest_seq
"""


def best_current_history(
    conn, *, user_id: UUID, effective_from: datetime, effective_to: datetime
) -> list[dict]:
    """Event-time view: everything the engine now believes about this
    physiological window, however late it was learned.

    Ordered by (effective_at, ingest_seq) -- Replay Contract step 4's
    "ordered by effective_at, then ingestion sequence as the tie-breaker" --
    so a replay driven from this view is deterministic even when two events
    share an instant.
    """
    with conn.cursor() as cur:
        cur.execute(
            _BEST_CURRENT,
            {
                "user_id": user_id,
                "effective_from": effective_from,
                "effective_to": effective_to,
            },
        )
        return cur.fetchall()


def history_known_at(
    conn,
    *,
    user_id: UUID,
    knowledge_cutoff: datetime,
    effective_from: datetime,
    effective_to: datetime,
) -> list[dict]:
    """System-time view: the same physiological window as the engine saw it
    at `knowledge_cutoff`, with facts that arrived afterwards excluded.

    This is what reconstructs the context of a decision that was actually
    served, and it is why a late lab may never be back-dated into an old
    warning: step 9's "Replay may create a revised/counterfactual decision,
    not a fake past delivery."
    """
    with conn.cursor() as cur:
        cur.execute(
            _KNOWN_AT,
            {
                "user_id": user_id,
                "knowledge_cutoff": knowledge_cutoff,
                "effective_from": effective_from,
                "effective_to": effective_to,
            },
        )
        return cur.fetchall()
