"""sahacore.ledger -- step 1 of '★ Build Guide Python'.

    Build task:  "Create ingestion and evidence ledger"
    Why:         "Preserves every raw event and prevents duplicates"
    Details:     "Implement raw_events, event_quality, controls_u,
                  measurements_y, bitemporal effective_at/knowledge_at,
                  checkpoints, lineage hashes and replay-job keys"
    Sheets:      "IO · Lineage DataMap; H · U-Ledger Fusion Rules;
                  Replay Contract"
    Acceptance:  "duplicate event no-op; late event replay"

'★ Signal Memory Bank' (B11) states the reason the ledger exists at all:

    "A raw event is NOT a latent state. A state is a sufficient summary of
     history for future prediction; the event ledger is the audit trail.
     Keep BOTH -- the ledger enables replay, late-arriving data, correction
     of mis-logged meals, and regulatory traceability. Summarising into a
     state must never delete the event."

Everything downstream of the ledger -- exposure_state, posterior_state,
m_state, signatures, warnings, decisions -- is derived and regenerable. The
rows in this package's tables are not: they are the only things in the system
that cannot be recomputed, which is why raw_events and checkpoint_state are
trigger-locked against UPDATE and DELETE in sql/009_ledger.sql.

WHAT IS DELIBERATELY NOT HERE. The Replay Contract names functions in
`sahacore.replay` (restore_checkpoint, replay_core, rebuild_downstream) and
`sahacore.uledger` (supersede_descendants); those orchestrate Layer E's
replay and belong to build step 5. This package owns the facts, the two
clocks, the lineage hashes, checkpoint SELECTION and the ReplayJob receipt --
the keys and evidence that a replay is driven from.
"""
from sahacore.ledger.bitemporal import best_current_history, history_known_at
from sahacore.ledger.checkpoints import (
    Checkpoint,
    NoEligibleCheckpoint,
    select_replay_checkpoint,
    write_checkpoint,
)
from sahacore.ledger.controls import (
    ControlVectorShapeError,
    ControlVersion,
    active_control_vector,
    write_control_vector,
)
from sahacore.ledger.ingest import (
    IngestResult,
    LEDGER_NAMESPACE,
    event_uuid_for,
    ingest_event,
)
from sahacore.ledger.jobs import (
    CURRENT_TIME_ANCHOR_ONLY,
    DEEP_REPLAY,
    ROUTINE,
    close_replay_job,
    open_replay_job,
    replay_policy,
    routine_lag_days,
)
from sahacore.ledger.lineage import canonical_json, lineage_hash
from sahacore.ledger.measurements import (
    SUPPORT_POINT,
    SUPPORT_WINDOWED,
    RecordedMeasurement,
    earliest_evidence_support_start,
    evidence_support_start,
    record_measurement,
    supersede_measurement,
)
from sahacore.ledger.quality import (
    QualityVerdict,
    active_event_quality,
    record_event_quality,
)
from sahacore.ledger.times import (
    ClockResolutionError,
    ResolvedTimes,
    lag,
    resolve_times,
)

__all__ = [
    "CURRENT_TIME_ANCHOR_ONLY",
    "DEEP_REPLAY",
    "LEDGER_NAMESPACE",
    "ROUTINE",
    "SUPPORT_POINT",
    "SUPPORT_WINDOWED",
    "Checkpoint",
    "ClockResolutionError",
    "ControlVectorShapeError",
    "ControlVersion",
    "IngestResult",
    "NoEligibleCheckpoint",
    "QualityVerdict",
    "RecordedMeasurement",
    "ResolvedTimes",
    "active_control_vector",
    "active_event_quality",
    "best_current_history",
    "canonical_json",
    "close_replay_job",
    "earliest_evidence_support_start",
    "event_uuid_for",
    "evidence_support_start",
    "history_known_at",
    "ingest_event",
    "lag",
    "lineage_hash",
    "open_replay_job",
    "record_event_quality",
    "record_measurement",
    "replay_policy",
    "resolve_times",
    "routine_lag_days",
    "select_replay_checkpoint",
    "supersede_measurement",
    "write_checkpoint",
    "write_control_vector",
]
