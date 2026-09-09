-- The engine's canonical invariants and fail-closed safety gates.
--
-- Source: v39sEng2.xlsx, sheet '00_ENGINEER_START' -- "SahaPlusAI v39w —
-- Thin-Client Signal-Contract Engineer Handoff", which calls itself the
-- "Current engineer source of truth". 23 invariants, 18 carrying a gate name.
--
-- WHY THESE ARE IN THE DATABASE AND NOT IN A SETTINGS FILE. Most are not
-- choices. They are positions the workbook takes and expects the engine to
-- fail closed on, in its own words:
--
--     Layer T           OFF                     research-only until
--                                               block-bootstrap and held-out
--                                               superiority gates pass
--     Open Ear          BLOCKED                 no audio/raw mic persistence
--     D14/D15           GLOBAL_MODIFIER_PENDING "No invented organ weights.
--                                               Fail closed until
--                                               evidence-locked mapping is
--                                               signed off."
--     Cluster coupling  OFF (ETA=0)             numeric Gamma edges remain
--                                               hypotheses
--     Actions           127 / 126 activatable   "Do not force 127 active arms."
--
-- Each is a rule a layer could break by being reasonable -- switching on a
-- coupling term because the matrix is right there, or activating the 127th
-- arm because 126 looks like an off-by-one. Putting them here, before the
-- layers, means the position outlives whoever last read the sheet.
--
-- Two of these the build has already met independently, which is worth noting
-- because it is corroboration rather than coincidence: the action space
-- carries 127 arms with exactly one activation_hold (migration 014), and
-- parameter #138 eta_net states its own default as "0 production; any
-- non-zero value is shadow/data-derived". The gates and the registries agree.

CREATE TABLE IF NOT EXISTS engine_internal.runtime_invariant (
    source_row          INTEGER PRIMARY KEY,

    invariant           TEXT NOT NULL,
    value               TEXT NOT NULL,
    engineering_meaning TEXT NOT NULL,

    backend_owner       TEXT,
    frontend_owner      TEXT,
    data_server_owner   TEXT,

    -- The sheet's own machine-readable gate name, or NULL. Five rows -- the
    -- behavioural sidecar rules -- carry no gate, and are stored with NULL
    -- rather than given an invented name: a gate name implies something can
    -- check it.
    gate                TEXT,

    -- THIS BUILD'S column, not the sheet's, in the same sense as
    -- parameter_registry.resolved_by: the test that actually executes this
    -- gate against what the repo contains, or NULL when the gate is recorded
    -- and not yet executable because its layer does not exist.
    enforced_by         TEXT,

    -- A row cannot claim enforcement without a gate to enforce.
    CONSTRAINT runtime_invariant_enforcement_needs_a_gate CHECK (
        enforced_by IS NULL OR gate IS NOT NULL
    )
);

-- Gate names are unique where present.
CREATE UNIQUE INDEX IF NOT EXISTS runtime_invariant_gate_is_unique
    ON engine_internal.runtime_invariant (gate)
    WHERE gate IS NOT NULL;

COMMENT ON TABLE engine_internal.runtime_invariant IS
    'Canonical invariants and fail-closed gates from 00_ENGINEER_START, the '
    'workbook''s stated "Current engineer source of truth". A layer reads '
    'these before deciding anything a gate covers.';

COMMENT ON COLUMN engine_internal.runtime_invariant.enforced_by IS
    'The test in this repo that executes the gate, or NULL when the gate is '
    'recorded but its layer is unwritten. NULL is not permission to ignore '
    'it -- the position still holds when that layer is built.';

-- The gates nothing yet checks. Not a backlog to clear before shipping: most
-- wait on layers that do not exist. It is the list to consult when one of
-- those layers is written, so a position taken in the workbook is not
-- rediscovered by breaking it.
CREATE OR REPLACE VIEW engine_internal.unenforced_gates AS
    SELECT gate, value, invariant, engineering_meaning, backend_owner
    FROM engine_internal.runtime_invariant
    WHERE gate IS NOT NULL AND enforced_by IS NULL
    ORDER BY gate;

COMMENT ON VIEW engine_internal.unenforced_gates IS
    'Gates declared by 00_ENGINEER_START that this build does not yet '
    'execute. Read this before writing any new layer.';
