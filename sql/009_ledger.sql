-- Step 1 of '★ Build Guide Python' (row A3): "Create ingestion and evidence
-- ledger -- preserves every raw event and prevents duplicates".
--
-- Authoritative sheets, as named by that row:
--   * 'IO · Lineage DataMap'        -- table/PK/field/versioning contract
--   * 'H · U-Ledger Fusion Rules'   -- dedupe and late-event semantics
--   * 'Replay Contract'             -- the two clocks, checkpoints, ReplayJob
-- plus '13_DB_TABLES' in the SIGDB workbook, which places every one of these
-- under the `engine_internal` schema and classifies them INTERNAL.
--
-- Only the four ingest tables plus checkpoint_state and replay_job are built
-- here -- exactly the set step 1's own "implementation details" cell names
-- ("raw_events, event_quality, controls_u, measurements_y, bitemporal
-- effective_at/knowledge_at, checkpoints, lineage hashes and replay-job
-- keys"). The derived packets in the same DataMap (exposure_state,
-- posterior_state, m_state, ...) belong to their own layers' build steps and
-- are deliberately absent rather than stubbed.

CREATE SCHEMA IF NOT EXISTS engine_internal;


-- === raw_events (DataMap A3 / SIGDB TBL001) ===============================
-- "Immutable fact store for meals, activity, sleep, mood, stress, meds,
-- supplements, wearables, labs and corrections."
-- Versioning/lineage: "immutable append-only; dedupe on
-- adapter_source_id+source_event_id; a correction is a new event linked by
-- correction_of_event_id".
-- Validation: "duplicate delivery no-op; original fact is never overwritten".

CREATE TABLE IF NOT EXISTS engine_internal.raw_events (
    event_uuid              UUID        PRIMARY KEY,
    ingest_seq              BIGSERIAL   NOT NULL UNIQUE,

    adapter_source_id       TEXT        NOT NULL,
    source_event_id         TEXT        NOT NULL,
    user_id                 UUID        NOT NULL,
    event_type              TEXT        NOT NULL,

    -- the two clocks plus the raw source stamps they are resolved from
    -- ('Replay Contract' section B)
    effective_at            TIMESTAMPTZ NOT NULL,
    knowledge_at            TIMESTAMPTZ NOT NULL,
    occurred_at             TIMESTAMPTZ,
    specimen_at             TIMESTAMPTZ,
    observed_at             TIMESTAMPTZ,
    ingested_at             TIMESTAMPTZ NOT NULL,

    source_timezone         TEXT,
    payload_json            JSONB       NOT NULL,
    quality                 TEXT,
    correction_of_event_id  UUID        REFERENCES engine_internal.raw_events (event_uuid),
    clock_quarantined       BOOLEAN     NOT NULL DEFAULT FALSE,
    lineage_hash            TEXT        NOT NULL,

    -- G3: "dedupe on adapter_source_id+source_event_id". This constraint IS
    -- the duplicate no-op (U-Ledger A10, Replay Contract step 2, RT-02):
    -- ingest_event inserts ON CONFLICT DO NOTHING against it.
    CONSTRAINT raw_events_source_is_unique
        UNIQUE (adapter_source_id, source_event_id),

    -- event_type domain: the ten kinds named in DataMap C3, plus hydration,
    -- onboarding (SIGDB '05_INPUT_EVENTS' INP0028/INP0029) and feedback
    -- (SIGDB '20_LINEAGE' LIN08, "user interaction -> raw_events").
    CONSTRAINT raw_events_type_is_known CHECK (event_type IN (
        'meal', 'activity', 'sleep', 'mood', 'stress', 'medication',
        'supplement', 'wearable', 'lab', 'correction',
        'hydration', 'onboarding', 'feedback'
    )),

    -- Replay Contract F21: effective_at is "not after knowledge_at except
    -- clock-error quarantine". The escape is explicit, never silent.
    CONSTRAINT raw_events_effective_at_not_after_knowledge_at
        CHECK (effective_at <= knowledge_at OR clock_quarantined),

    -- B21: "Laboratory default: specimen_at."
    CONSTRAINT raw_events_lab_uses_specimen_at CHECK (
        event_type <> 'lab'
        OR (specimen_at IS NOT NULL AND effective_at = specimen_at)
    ),

    -- A8: "A correction is a new event"; it cannot be its own correction.
    CONSTRAINT raw_events_correction_is_a_different_event
        CHECK (correction_of_event_id IS NULL OR correction_of_event_id <> event_uuid)
);

-- Replay Contract step 4 orders replay "by effective_at, then ingestion
-- sequence as the tie-breaker" -- this index serves exactly that scan.
CREATE INDEX IF NOT EXISTS raw_events_replay_order
    ON engine_internal.raw_events (user_id, effective_at, ingest_seq);
CREATE INDEX IF NOT EXISTS raw_events_knowledge_order
    ON engine_internal.raw_events (user_id, knowledge_at);
CREATE INDEX IF NOT EXISTS raw_events_correction_chain
    ON engine_internal.raw_events (correction_of_event_id)
    WHERE correction_of_event_id IS NOT NULL;

-- "IMMUTABLE -- append-only" ('★ Signal Memory Bank' B6) and "the original
-- fact is never overwritten" (DataMap I3) are enforced by the database, not
-- only by convention: no code path, migration or console session can rewrite
-- an admitted fact.
CREATE OR REPLACE FUNCTION engine_internal.reject_mutation()
RETURNS TRIGGER LANGUAGE plpgsql AS $reject_mutation$
BEGIN
    RAISE EXCEPTION
        'table %.% is append-only (Replay Contract: immutable historical fact); % rejected',
        TG_TABLE_SCHEMA, TG_TABLE_NAME, TG_OP;
END;
$reject_mutation$;

DROP TRIGGER IF EXISTS raw_events_is_append_only ON engine_internal.raw_events;
CREATE TRIGGER raw_events_is_append_only
    BEFORE UPDATE OR DELETE ON engine_internal.raw_events
    FOR EACH ROW EXECUTE FUNCTION engine_internal.reject_mutation();


-- === event_quality (DataMap A4 / SIGDB TBL002) ============================
-- "Quality and uncertainty metadata for each event." Consumed by Layer E,
-- the U-Ledger and UI confidence; I4: "uncertain photo portions widen input
-- noise".
--
-- PK RECONCILIATION: the DataMap's PK cell says `event_uuid`, but the same
-- row's versioning cell says "updates create new quality version". Both are
-- kept: the stored key is (event_uuid, quality_version), and the partial
-- unique index below makes `event_uuid` the key of the ACTIVE verdict, which
-- is the row every consumer resolves.

CREATE TABLE IF NOT EXISTS engine_internal.event_quality (
    event_uuid      UUID             NOT NULL REFERENCES engine_internal.raw_events (event_uuid),
    quality_version INTEGER          NOT NULL,

    source_type     TEXT             NOT NULL,
    device_model    TEXT,
    confidence      DOUBLE PRECISION,
    cv              DOUBLE PRECISION,
    missingness     DOUBLE PRECISION,
    outlier_flag    BOOLEAN          NOT NULL DEFAULT FALSE,

    status          TEXT             NOT NULL DEFAULT 'ACTIVE',
    knowledge_at    TIMESTAMPTZ      NOT NULL,
    lineage_hash    TEXT             NOT NULL,

    PRIMARY KEY (event_uuid, quality_version),
    CONSTRAINT event_quality_version_is_positive CHECK (quality_version >= 1),
    CONSTRAINT event_quality_confidence_is_a_probability
        CHECK (confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)),
    CONSTRAINT event_quality_cv_is_nonnegative
        CHECK (cv IS NULL OR cv >= 0.0),
    CONSTRAINT event_quality_missingness_is_a_fraction
        CHECK (missingness IS NULL OR (missingness >= 0.0 AND missingness <= 1.0)),
    CONSTRAINT event_quality_status_is_known
        CHECK (status IN ('ACTIVE', 'SUPERSEDED', 'INVALIDATED'))
);

CREATE UNIQUE INDEX IF NOT EXISTS event_quality_one_active_verdict
    ON engine_internal.event_quality (event_uuid)
    WHERE status = 'ACTIVE';


-- === controls_u (DataMap A5 / SIGDB TBL003) ===============================
-- "Control inputs from food/activity/sleep/stress/logged behavior", produced
-- by the ledger rollup and consumed by Layers A/B/C/E.
-- G5: "versioned and recomputed from immutable events on replay;
-- parent_event_ids and lineage_hash retained".
-- I5: "81 nutrient doses present; controls are never treated as
-- measurements" -- hence the array-length check, and hence controls_u has no
-- R_cov column at all: only measurements_y carries observation noise.
--
-- PK RECONCILIATION: same shape as event_quality. The DataMap's PK cell says
-- `user_id,time`; its versioning cell requires versions, and exposure_state
-- (A7) names `parent_control_version` as a parent. Stored key carries the
-- version; the partial unique index keeps (user_id, effective_time) the key
-- of the ACTIVE control vector.

CREATE TABLE IF NOT EXISTS engine_internal.controls_u (
    user_id              UUID               NOT NULL,
    effective_time       TIMESTAMPTZ        NOT NULL,
    control_version      INTEGER            NOT NULL,

    dose_vector_81       DOUBLE PRECISION[] NOT NULL,
    mvpa_min             DOUBLE PRECISION,
    sleep_h              DOUBLE PRECISION,
    stress               DOUBLE PRECISION,
    hydration_ml         DOUBLE PRECISION,
    med_flags            TEXT[]             NOT NULL DEFAULT '{}',
    context              JSONB              NOT NULL DEFAULT '{}'::jsonb,

    parent_event_ids     UUID[]             NOT NULL,
    as_of_effective_time TIMESTAMPTZ        NOT NULL,
    as_of_knowledge_time TIMESTAMPTZ        NOT NULL,
    status               TEXT               NOT NULL DEFAULT 'ACTIVE',
    lineage_hash         TEXT               NOT NULL,
    replay_job_id        UUID,

    PRIMARY KEY (user_id, effective_time, control_version),
    CONSTRAINT controls_u_version_is_positive CHECK (control_version >= 1),
    CONSTRAINT controls_u_has_81_nutrient_doses
        CHECK (array_length(dose_vector_81, 1) = 81),
    CONSTRAINT controls_u_doses_are_nonnegative
        CHECK (0.0 <= ALL (dose_vector_81)),
    CONSTRAINT controls_u_status_is_known
        CHECK (status IN ('ACTIVE', 'SUPERSEDED', 'INVALIDATED')),
    CONSTRAINT controls_u_derives_from_at_least_one_event
        CHECK (array_length(parent_event_ids, 1) >= 1)
);

CREATE UNIQUE INDEX IF NOT EXISTS controls_u_one_active_version
    ON engine_internal.controls_u (user_id, effective_time)
    WHERE status = 'ACTIVE';


-- === measurements_y (DataMap A6 / SIGDB TBL004) ===========================
-- "Sensor/lab observations", produced by the ledger observation adapter and
-- consumed by Layer E.
-- G6: "each measurement versioned; effective_at=specimen_at for labs,
-- otherwise occurred_at/observed_at by adapter contract; source ancestry
-- retained".
-- I6: "same source measurement applied once per active replay lineage".

CREATE TABLE IF NOT EXISTS engine_internal.measurements_y (
    measurement_id         UUID             PRIMARY KEY,
    measurement_version    INTEGER          NOT NULL,

    user_id                UUID             NOT NULL,
    measurement_type       TEXT             NOT NULL,
    value                  DOUBLE PRECISION NOT NULL,
    unit                   TEXT             NOT NULL,
    r_cov                  DOUBLE PRECISION NOT NULL,

    effective_at           TIMESTAMPTZ      NOT NULL,
    observed_at            TIMESTAMPTZ,
    specimen_at            TIMESTAMPTZ,
    ingested_at            TIMESTAMPTZ      NOT NULL,
    knowledge_at           TIMESTAMPTZ      NOT NULL,

    source_event_id        UUID             NOT NULL REFERENCES engine_internal.raw_events (event_uuid),
    is_lab                 BOOLEAN          NOT NULL DEFAULT FALSE,

    -- Replay Contract step 3 selects the checkpoint "strictly before the
    -- earliest evidence-support time. For point measurements this may equal
    -- effective_at; for E_WINDOWED measurements it precedes specimen_at."
    -- E_WINDOWED is the sheet's own token; POINT names the complementary
    -- case it describes as "point measurements".
    support_class          TEXT             NOT NULL DEFAULT 'POINT',
    evidence_support_start TIMESTAMPTZ      NOT NULL,

    status                 TEXT             NOT NULL DEFAULT 'ACTIVE',
    lineage_hash           TEXT             NOT NULL,

    CONSTRAINT measurements_y_version_is_positive CHECK (measurement_version >= 1),
    -- R is an observation-noise covariance: a zero would claim a perfect
    -- sensor and make Layer E's gain singular.
    CONSTRAINT measurements_y_r_cov_is_positive CHECK (r_cov > 0.0),
    CONSTRAINT measurements_y_status_is_known
        CHECK (status IN ('ACTIVE', 'SUPERSEDED', 'INVALIDATED')),
    CONSTRAINT measurements_y_support_class_is_known
        CHECK (support_class IN ('POINT', 'E_WINDOWED')),
    CONSTRAINT measurements_y_lab_uses_specimen_at CHECK (
        NOT is_lab OR (specimen_at IS NOT NULL AND effective_at = specimen_at)
    ),
    CONSTRAINT measurements_y_support_starts_no_later_than_effective_at
        CHECK (evidence_support_start <= effective_at),
    -- A windowed measurement's support genuinely precedes its specimen time;
    -- a point measurement's does not extend backwards.
    CONSTRAINT measurements_y_point_support_is_instantaneous CHECK (
        support_class <> 'POINT' OR evidence_support_start = effective_at
    ),
    CONSTRAINT measurements_y_windowed_support_precedes_effective_at CHECK (
        support_class <> 'E_WINDOWED' OR evidence_support_start < effective_at
    )
);

-- I6: one active application of a given source measurement per lineage.
CREATE UNIQUE INDEX IF NOT EXISTS measurements_y_one_active_use_per_source
    ON engine_internal.measurements_y (source_event_id, measurement_type)
    WHERE status = 'ACTIVE';

CREATE INDEX IF NOT EXISTS measurements_y_replay_order
    ON engine_internal.measurements_y (user_id, effective_at);


-- === checkpoint_state (DataMap A19 / SIGDB TBL016) ========================
-- "Durable replay start point ... immutable checkpoint; newer checkpoint
-- never mutates older one" (G19), "checkpoint strictly precedes replay
-- effective_at" (I19 -- enforced by the selection query in
-- sahacore.ledger.checkpoints, since it is a property of a replay, not of a
-- stored row).

CREATE TABLE IF NOT EXISTS engine_internal.checkpoint_state (
    checkpoint_id       UUID        PRIMARY KEY,
    user_id             UUID        NOT NULL,

    effective_at        TIMESTAMPTZ NOT NULL,
    knowledge_at        TIMESTAMPTZ NOT NULL,

    model_shape_version TEXT        NOT NULL,
    posterior_version   TEXT,
    exposure_version    TEXT,
    m_version           TEXT,
    signature_version   TEXT,
    warning_version     TEXT,

    -- Replay Contract step 3 selects "the latest DURABLE checkpoint".
    durable             BOOLEAN     NOT NULL DEFAULT TRUE,
    lineage_hash        TEXT        NOT NULL,

    CONSTRAINT checkpoint_state_effective_at_not_after_knowledge_at
        CHECK (effective_at <= knowledge_at)
);

CREATE INDEX IF NOT EXISTS checkpoint_state_selection
    ON engine_internal.checkpoint_state (user_id, effective_at DESC, knowledge_at DESC)
    WHERE durable;

DROP TRIGGER IF EXISTS checkpoint_state_is_append_only ON engine_internal.checkpoint_state;
CREATE TRIGGER checkpoint_state_is_append_only
    BEFORE UPDATE OR DELETE ON engine_internal.checkpoint_state
    FOR EACH ROW EXECUTE FUNCTION engine_internal.reject_mutation();


-- === replay_job (DataMap A22 / SIGDB TBL019) ==============================
-- "Bitemporal replay receipt and invalidation map ... one immutable receipt
-- per replay attempt; retries linked" (G22).
-- Replay Contract step 11 / U-Ledger A14: inside the configured fixed lag a
-- replay is ROUTINE; outside it, it must be an approved DEEP_REPLAY or be
-- recorded as CURRENT_TIME_ANCHOR_ONLY -- G17: "ReplayJob records policy,
-- approver/reason and horizon".
--
-- Unlike raw_events and checkpoint_state this table is NOT trigger-locked:
-- the receipt is one row per attempt whose status advances as that attempt
-- runs. Immutability here means a new attempt writes a NEW receipt linked by
-- retry_of_replay_job_id, never a rewrite of an earlier one.

CREATE TABLE IF NOT EXISTS engine_internal.replay_job (
    replay_job_id          UUID        PRIMARY KEY,
    user_id                UUID        NOT NULL,

    trigger_event_id       UUID        NOT NULL REFERENCES engine_internal.raw_events (event_uuid),
    effective_at           TIMESTAMPTZ NOT NULL,
    knowledge_at           TIMESTAMPTZ NOT NULL,
    checkpoint_id          UUID        REFERENCES engine_internal.checkpoint_state (checkpoint_id),
    replay_horizon         INTERVAL    NOT NULL,

    policy                 TEXT        NOT NULL,
    approver               TEXT,
    reason                 TEXT,

    old_version_ids        TEXT[]      NOT NULL DEFAULT '{}',
    new_version_ids        TEXT[]      NOT NULL DEFAULT '{}',
    status                 TEXT        NOT NULL DEFAULT 'PENDING',
    retry_of_replay_job_id UUID        REFERENCES engine_internal.replay_job (replay_job_id),

    created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT replay_job_policy_is_known CHECK (
        policy IN ('ROUTINE', 'DEEP_REPLAY', 'CURRENT_TIME_ANCHOR_ONLY')
    ),
    -- status has no domain declared on the DataMap row; these four are this
    -- build's declared lifecycle for a receipt, not sheet-named tokens.
    CONSTRAINT replay_job_status_is_known CHECK (
        status IN ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED')
    ),
    -- Replay Contract step 11 G17 + U-Ledger A14: outside the routine lag the
    -- computational and clinical scope must be explicit, never silent.
    CONSTRAINT replay_job_non_routine_records_its_reason CHECK (
        policy = 'ROUTINE' OR reason IS NOT NULL
    ),
    -- Step 11 B17: a deep replay is an APPROVED deep replay.
    CONSTRAINT replay_job_deep_replay_is_approved CHECK (
        policy <> 'DEEP_REPLAY' OR approver IS NOT NULL
    ),
    -- Step 3 B9 + I19: the replay must start from a checkpoint. Only a
    -- current-time anchor -- which explicitly declines to replay history --
    -- may have none.
    CONSTRAINT replay_job_replay_starts_from_a_checkpoint CHECK (
        policy = 'CURRENT_TIME_ANCHOR_ONLY' OR checkpoint_id IS NOT NULL
    ),
    CONSTRAINT replay_job_horizon_is_positive CHECK (replay_horizon > INTERVAL '0'),
    CONSTRAINT replay_job_retry_is_a_different_job CHECK (
        retry_of_replay_job_id IS NULL OR retry_of_replay_job_id <> replay_job_id
    )
);

CREATE INDEX IF NOT EXISTS replay_job_by_user
    ON engine_internal.replay_job (user_id, knowledge_at DESC);


-- === replay_lag_policy ====================================================
-- The "configured fixed lag" of Replay Contract step 11 is parameter 129
-- L_smooth on 'P1 Parameters 134+': "Fixed-lag smoothing window -- Number of
-- recent days re-estimated nightly when delayed logs/labs arrive", unit days,
-- range 7-14, tunable ("Tune against latency and retrospective accuracy").
--
-- It is a tunable, so it lives here and is seeded from
-- sahacore/data/ledger_replay_policy.json -- never hardcoded in a .py file.

CREATE TABLE IF NOT EXISTS engine_internal.replay_lag_policy (
    policy_id          TEXT             PRIMARY KEY,
    l_smooth_days      DOUBLE PRECISION NOT NULL,
    l_smooth_min_days  DOUBLE PRECISION NOT NULL,
    l_smooth_max_days  DOUBLE PRECISION NOT NULL,
    param_row          TEXT             NOT NULL,
    source_sheet       TEXT             NOT NULL,
    status             TEXT             NOT NULL DEFAULT 'ACTIVE',

    CONSTRAINT replay_lag_policy_window_is_positive CHECK (l_smooth_days > 0.0),
    CONSTRAINT replay_lag_policy_window_is_in_range CHECK (
        l_smooth_days >= l_smooth_min_days AND l_smooth_days <= l_smooth_max_days
    ),
    CONSTRAINT replay_lag_policy_range_is_ordered CHECK (
        l_smooth_min_days <= l_smooth_max_days
    ),
    CONSTRAINT replay_lag_policy_status_is_known
        CHECK (status IN ('ACTIVE', 'SUPERSEDED'))
);

CREATE UNIQUE INDEX IF NOT EXISTS replay_lag_policy_one_active
    ON engine_internal.replay_lag_policy ((TRUE))
    WHERE status = 'ACTIVE';
