-- The SIGDB governance contract: SIG-DB-v1.1, as of 2026-08-27.
--
-- Source: SahaPlusAI_MASTER_..._v39sEng2SIGDB.xlsx, sheets 12_STATE_BLOCKS,
-- 17_FIREWALL, 18_GAPS, 19_QA_GATES, 21_DECISIONS.
--
-- WHY THIS IS IN THE DATABASE AND NOT ONLY IN A DOCUMENT. Every other
-- registry here says what the engine computes. This one says what may LEAVE
-- it, and it is the only source that does. Its posture is "default deny /
-- explicit allowlist", and a posture is worth nothing as prose: FW01 has to
-- be answerable by a query before the first read endpoint is written, not
-- after somebody notices a leak.
--
-- WHAT IS STORED AND WHAT IS NOT. This migration stores the GOVERNANCE half
-- -- the state partition, the firewall controls, the audited gaps, the
-- release gates and the locked decisions, 145 rows. The signal catalogue,
-- the API allowlist and the endpoint list are the other half and a larger
-- job; they come next and reference these.
--
-- The rows are transcribed. Where a gap contradicts something this build
-- did, the gap is stored as the auditor wrote it and reported, rather than
-- argued with in a CHECK constraint.

CREATE TABLE IF NOT EXISTS engine_internal.sigdb_contract (
    -- One row. The identity a stored decision is binding UNDER; a successor
    -- contract must arrive as a new row, not as an edit to this one.
    contract_version  TEXT PRIMARY KEY,
    source_authority  TEXT NOT NULL,
    as_of             DATE NOT NULL,
    public_projection TEXT NOT NULL,
    server_state      TEXT NOT NULL,
    api_posture       TEXT NOT NULL,
    clinical_status   TEXT NOT NULL,

    CONSTRAINT sigdb_contract_version_is_canonical
        CHECK (contract_version ~ '^SIG-DB-v[0-9]+\.[0-9]+$'),
    -- The one line of it this build most depends on. If a future contract
    -- relaxes default-deny, that is not something to absorb silently.
    CONSTRAINT sigdb_contract_is_default_deny
        CHECK (api_posture ILIKE '%default deny%')
);

COMMENT ON TABLE engine_internal.sigdb_contract IS
    'Identity of the backend/API contract these governance rows belong to. '
    'A successor contract is a new row; decisions cite the version they lock under.';


-- The canonical 219-state partition, with each block's Rao-Blackwell class.
CREATE TABLE IF NOT EXISTS engine_internal.sigdb_state_block (
    block_id     TEXT PRIMARY KEY,
    source_row   INTEGER NOT NULL UNIQUE,

    block_name   TEXT NOT NULL,
    start_index  INTEGER NOT NULL,
    end_index    INTEGER NOT NULL,
    state_count  INTEGER NOT NULL,
    rb_partition TEXT NOT NULL,
    api_exposure TEXT NOT NULL,
    source_sheet TEXT NOT NULL,
    notes        TEXT,

    CONSTRAINT sigdb_state_block_id_is_canonical CHECK (block_id ~ '^SB[0-9]{2}$'),
    CONSTRAINT sigdb_state_block_is_inside_219 CHECK (
        start_index BETWEEN 1 AND 219 AND end_index BETWEEN 1 AND 219
    ),
    CONSTRAINT sigdb_state_block_is_ordered CHECK (start_index <= end_index),
    -- The count is not an independent fact; it is the span. Storing both and
    -- not checking them is how a partition silently stops summing to 219.
    CONSTRAINT sigdb_state_block_count_is_the_span CHECK (
        state_count = end_index - start_index + 1
    ),
    CONSTRAINT sigdb_state_block_rb_class_is_known CHECK (
        rb_partition IN ('LINEAR', 'NONLINEAR', 'MIXED')
    ),
    -- FW05: no 219-state vector, covariance or raw pool crosses the client
    -- boundary. Every block is HIDDEN, and the database refuses one that
    -- is not rather than leaving it to a serialiser to remember.
    CONSTRAINT sigdb_state_block_is_hidden CHECK (api_exposure = 'HIDDEN')
);

COMMENT ON TABLE engine_internal.sigdb_state_block IS
    'The canonical 219-state partition. Every block is HIDDEN by FW05.';


-- The 17 non-negotiable firewall controls.
CREATE TABLE IF NOT EXISTS engine_internal.sigdb_firewall_control (
    control_id           TEXT PRIMARY KEY,
    source_row           INTEGER NOT NULL UNIQUE,

    control_class        TEXT NOT NULL,
    rule                 TEXT NOT NULL,
    severity             TEXT NOT NULL,
    test                 TEXT NOT NULL,
    source               TEXT NOT NULL,
    -- NULL for FW15-FW17 only: the three appended under the v39w
    -- thin-client ruling left both columns empty. Stored as found.
    implementation_owner TEXT,
    status               TEXT,

    CONSTRAINT sigdb_firewall_id_is_canonical CHECK (control_id ~ '^FW[0-9]{2}$'),
    CONSTRAINT sigdb_firewall_severity_is_known CHECK (
        severity IN ('BLOCKER', 'HIGH')
    ),
    CONSTRAINT sigdb_firewall_status_is_known CHECK (
        status IS NULL OR status = 'REQUIRED'
    ),
    -- Owner and status travel together or neither does. A control with an
    -- owner and no status would be a third state nobody has described.
    CONSTRAINT sigdb_firewall_owner_and_status_agree CHECK (
        (implementation_owner IS NULL) = (status IS NULL)
    )
);

COMMENT ON COLUMN engine_internal.sigdb_firewall_control.status IS
    'NULL on FW15-FW17: three BLOCKER controls appended under the v39w '
    'thin-client ruling with no owner and no status. See docs/parameter-gaps.md.';


-- The 68 audited findings.
CREATE TABLE IF NOT EXISTS engine_internal.sigdb_gap (
    finding_id   TEXT PRIMARY KEY,
    source_row   INTEGER NOT NULL UNIQUE,

    product      TEXT NOT NULL,
    severity     TEXT NOT NULL,
    topic        TEXT NOT NULL,
    finding      TEXT NOT NULL,
    evidence     TEXT,
    decision     TEXT,
    release_gate TEXT,
    source_file  TEXT,
    status       TEXT,

    CONSTRAINT sigdb_gap_id_is_canonical CHECK (finding_id ~ '^GAP[0-9]{3}$'),
    CONSTRAINT sigdb_gap_severity_is_known CHECK (
        severity IN ('BLOCKER', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW')
    )
);


-- The 34 release gates.
CREATE TABLE IF NOT EXISTS engine_internal.sigdb_qa_gate (
    qa_id             TEXT PRIMARY KEY,
    source_row        INTEGER NOT NULL UNIQUE,

    severity          TEXT NOT NULL,
    rule              TEXT NOT NULL,
    -- TEXT on purpose. The sheet writes `expected` as text ("219", "100%",
    -- "1 Pulse / 0 Atlas") and computes `actual` separately, several by Excel
    -- formula. Coercing the first to a number would lose the gates that are
    -- not numbers, and silently agreeing them is what the extractor checks.
    expected          TEXT NOT NULL,
    actual_or_formula TEXT,
    excel_formula     TEXT,
    status_formula    TEXT,
    source            TEXT,
    status            TEXT,

    CONSTRAINT sigdb_qa_gate_id_is_canonical CHECK (qa_id ~ '^QA[0-9]{3}$'),
    CONSTRAINT sigdb_qa_gate_severity_is_known CHECK (
        severity IN ('BLOCKER', 'HIGH')
    )
);


-- The 16 locked adjudications.
CREATE TABLE IF NOT EXISTS engine_internal.sigdb_decision (
    decision_id        TEXT PRIMARY KEY,
    source_row         INTEGER NOT NULL UNIQUE,

    topic              TEXT NOT NULL,
    finding            TEXT NOT NULL,
    canonical_decision TEXT NOT NULL,
    rationale          TEXT NOT NULL,
    owner              TEXT NOT NULL,
    status             TEXT NOT NULL,
    effective_release  TEXT NOT NULL,

    CONSTRAINT sigdb_decision_id_is_canonical CHECK (decision_id ~ '^DEC[0-9]{2}$'),
    -- LOCKED_FOR_THIS_CONTRACT is what makes these binding rather than
    -- advisory. An unlocked row means the contract moved.
    CONSTRAINT sigdb_decision_is_locked CHECK (
        status = 'LOCKED_FOR_THIS_CONTRACT'
    )
);

COMMENT ON TABLE engine_internal.sigdb_decision IS
    'Adjudications the backend, data server and mobile must follow. '
    'Changing one requires an explicit successor contract version.';


-- --------------------------------------------------------------------------
-- What the contract is for: questions that must be answerable by a query.
-- --------------------------------------------------------------------------

-- The partition, proved rather than asserted. Empty means every one of the
-- 219 states is covered exactly once by exactly one HIDDEN block.
CREATE OR REPLACE VIEW engine_internal.sigdb_state_partition_break AS
    WITH ordered AS (
        SELECT block_id, start_index, end_index,
               lag(end_index) OVER (ORDER BY start_index) AS previous_end
        FROM engine_internal.sigdb_state_block
    )
    SELECT block_id, start_index, previous_end,
           CASE
               WHEN previous_end IS NULL AND start_index <> 1
                   THEN 'partition does not start at 1'
               WHEN previous_end IS NOT NULL AND start_index <> previous_end + 1
                   THEN 'gap or overlap before this block'
           END AS problem
    FROM ordered
    WHERE (previous_end IS NULL AND start_index <> 1)
       OR (previous_end IS NOT NULL AND start_index <> previous_end + 1);

COMMENT ON VIEW engine_internal.sigdb_state_partition_break IS
    'Empty is the healthy state: the 10 blocks tile 1..219 exactly once.';

-- The gaps that hold a release. BLOCKS_AFFECTED_FEATURE is the auditor's own
-- gate value, so this is their list and not a re-reading of it.
CREATE OR REPLACE VIEW engine_internal.sigdb_release_blocker AS
    SELECT finding_id, product, severity, topic, finding, decision, status
    FROM engine_internal.sigdb_gap
    WHERE release_gate = 'BLOCKS_AFFECTED_FEATURE'
      AND coalesce(status, '') NOT LIKE 'RESOLVED%'
    ORDER BY
        CASE severity WHEN 'BLOCKER' THEN 0 WHEN 'CRITICAL' THEN 1
                      WHEN 'HIGH' THEN 2 ELSE 3 END,
        finding_id;

-- Controls nobody has signed for. Three rows today, all BLOCKER.
CREATE OR REPLACE VIEW engine_internal.sigdb_unowned_control AS
    SELECT control_id, control_class, severity, rule, source
    FROM engine_internal.sigdb_firewall_control
    WHERE status IS NULL
    ORDER BY control_id;
