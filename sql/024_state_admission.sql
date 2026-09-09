-- The contract that stops the state vector growing.
--
-- Sources: v39sEng2.xlsx, sheets '03_STATE_ADMISSION_GATES' and
-- '04_BEHAVIOR_SIDECAR'. '01_IMPORT_MANIFEST' orders 198 and 199. These are
-- the last two registries '★ Build Guide Python' step 2 names.
--
-- WHAT THEY ARE FOR. Every request to model a new behavioural quantity is
-- answered here, and answered no, with a reason and an alternative. The
-- constants state it directly:
--
--   state_delta            0     "Sidecar never changes x_t."
--   nonlinear_delta        0     "No new sigma branches."
--   baseline_state_n       219   "Do not expand x_t for behavioral categories."
--   lifestyle_state_slots  24    at 187:210, "already fully allocated"
--
-- This is a rule an implementer breaks by being helpful. Mood clearly
-- matters, so mood becomes a state, the vector becomes 223, and every stored
-- posterior, checkpoint and replay from before that moment is a different
-- shape -- which is what RUNTIME-001 means by "one inference version may not
-- mix vector shapes". Loading the answer before the layers exist puts it in
-- the database rather than in whoever last read the sheet.
--
-- The four STATE_CANDIDATE verdicts are the requests already refused: the 50
-- activity IDs as states, an extra sleep-regularity state, four stress
-- states, four mood states. Each has a stated alternative route.
--
-- Rows 14-19 of the sidecar sheet are six example events (ex_sleep, ex_sed,
-- ...) illustrating the event shape. They are documentation and are not
-- loaded: fictional activity events do not belong in a table beside real
-- ones.

CREATE TABLE IF NOT EXISTS engine_internal.state_admission_constant (
    constant            TEXT PRIMARY KEY,
    source_sheet        TEXT NOT NULL,
    source_row          INTEGER NOT NULL,
    value               TEXT NOT NULL,
    formula_or_source   TEXT,
    engineering_meaning TEXT,
    owner               TEXT,

    UNIQUE (source_sheet, source_row)
);

COMMENT ON TABLE engine_internal.state_admission_constant IS
    'The baseline shape constants: 219 states, 47961 covariance cells '
    '(=219^2), 55 nonlinear, 111 sigma branches, 24 lifestyle slots. A third '
    'independent sheet agreeing with ''★ State Vector v33'' and '
    '''00_ENGINEER_START''.';

CREATE TABLE IF NOT EXISTS engine_internal.state_admission_candidate (
    candidate               TEXT PRIMARY KEY,
    source_row              INTEGER NOT NULL UNIQUE,
    -- STATE_CANDIDATE (refused), CORE_INPUT, DERIVED_FEATURE,
    -- SIDECAR_SHADOW, EXISTING_STATE -- where the quantity actually goes.
    target_representation   TEXT NOT NULL,
    necessity               TEXT,
    sidecar_adequate        TEXT,
    identifiable_observable TEXT,
    init_burden             TEXT,
    replay                  TEXT,
    latency                 TEXT,
    held_out_evidence       TEXT
);

COMMENT ON TABLE engine_internal.state_admission_candidate IS
    'Behavioural quantities considered as new states, with the verdict and '
    'the route each was given instead. Four carry STATE_CANDIDATE, which the '
    'admission rules refuse.';

CREATE TABLE IF NOT EXISTS engine_internal.state_admission_rule (
    rule                      TEXT PRIMARY KEY,
    source_row                INTEGER NOT NULL UNIQUE,
    formula_or_implementation TEXT,
    current_result            TEXT NOT NULL,
    notes                     TEXT
);

CREATE TABLE IF NOT EXISTS engine_internal.behavior_sidecar_constant (
    constant        TEXT PRIMARY KEY,
    source_row      INTEGER NOT NULL UNIQUE,
    value           TEXT NOT NULL,
    formula_or_note TEXT,
    purpose         TEXT
);

CREATE TABLE IF NOT EXISTS engine_internal.behavior_sidecar_routing (
    domain               TEXT PRIMARY KEY,
    source_row           INTEGER NOT NULL UNIQUE,
    -- Which of the 219 states this domain's information reaches. It reaches
    -- them; it does not add to them.
    existing_core_states TEXT,
    sidecar_raw_feature  TEXT,
    routing              TEXT
);

COMMENT ON TABLE engine_internal.behavior_sidecar_routing IS
    'Where each behavioural domain''s information goes: into an existing '
    'state, a control input, or a downstream predictor. Never into a new '
    'state.';

CREATE TABLE IF NOT EXISTS engine_internal.behavior_sidecar_feature (
    feature         TEXT PRIMARY KEY,
    source_row      INTEGER NOT NULL UNIQUE,
    value           TEXT,
    formula_text    TEXT,
    routing_meaning TEXT
);

-- The four requests already refused, with the route each was given instead.
-- Read this before proposing a new state.
CREATE OR REPLACE VIEW engine_internal.refused_state_candidates AS
    SELECT candidate, necessity, sidecar_adequate, identifiable_observable,
           held_out_evidence
    FROM engine_internal.state_admission_candidate
    WHERE target_representation = 'STATE_CANDIDATE'
    ORDER BY source_row;

COMMENT ON VIEW engine_internal.refused_state_candidates IS
    'Behavioural quantities proposed as states and refused. The admission '
    'rules record the current result as PASS: no state expansion admitted.';
