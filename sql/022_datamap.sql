-- The engine's variable dictionary, and the onboarding field mapping.
--
-- Source: v39sEng2.xlsx, sheet 'P1 DataMap', sections A and B.
-- '01_IMPORT_MANIFEST' order 25, role CORE_ENGINE, import YES, backend Yes.
--
-- WHY THE data_source COLUMN EARNS THE IMPORT. It separates 'Parameter' and
-- 'Parameter Table' from 'Computed', 'Input', 'Diet Logging' and
-- 'Onboarding' -- for every engine variable at once. This build reported CL
-- as a missing parameter when B4 computes it; that mistake was possible
-- because nothing in the loaded data said which variables are looked up and
-- which are derived. Now something does.
--
-- Sections C, D and E of the same sheet are deliberately not imported. D
-- restates the action space, loaded from 'Action_Space' itself; E restates
-- the backbone's inputs and outputs columns, loaded from '★ Equation
-- Backbone'. A second copy of either is a second thing to keep in agreement.

CREATE TABLE IF NOT EXISTS engine_internal.datamap_variable (
    source_row            INTEGER PRIMARY KEY,

    -- Null on exactly one row: r8 describes the gamma shape parameter and
    -- leaves the symbol cell empty. Filling it in would be a guess, so it
    -- stays null and datamap_unnamed_variable reports it.
    variable              TEXT,
    layer                 TEXT NOT NULL,
    equations             TEXT,
    full_description      TEXT,
    physiological_meaning TEXT,
    units                 TEXT,
    typical_range         TEXT,

    -- 'Parameter', 'Parameter Table', 'Computed', 'Input', 'Diet Logging',
    -- 'Onboarding', 'Registry', ... Verbatim: the vocabulary is the sheet's.
    data_source           TEXT,
    specific_source       TEXT,
    update_frequency      TEXT
);

CREATE INDEX IF NOT EXISTS datamap_variable_by_source
    ON engine_internal.datamap_variable (data_source);
CREATE INDEX IF NOT EXISTS datamap_variable_by_layer
    ON engine_internal.datamap_variable (layer);

COMMENT ON TABLE engine_internal.datamap_variable IS
    'Section A of ''P1 DataMap'': every engine variable with its units, '
    'typical range and -- the useful part -- whether it is a stored '
    'parameter or something an equation computes.';

CREATE TABLE IF NOT EXISTS engine_internal.datamap_onboarding_field (
    source_row         INTEGER PRIMARY KEY,

    step               TEXT,
    screen             TEXT NOT NULL,
    field_name         TEXT NOT NULL,
    input_type         TEXT,

    -- The engine variable this field sets, and where it lands.
    engine_variable    TEXT NOT NULL,
    target_layer       TEXT,
    equations          TEXT,
    mapping_logic      TEXT,

    -- What Layer 0 must do when the user does not answer. Never null: a
    -- blank here is a default chosen silently by whoever writes the code.
    default_if_missing TEXT NOT NULL,
    priority           TEXT,

    CONSTRAINT datamap_onboarding_priority_is_known CHECK (
        priority IS NULL OR priority LIKE 'P0%' OR priority IN ('P1', 'P2')
    )
);

COMMENT ON TABLE engine_internal.datamap_onboarding_field IS
    'Section B of ''P1 DataMap'': each onboarding screen field mapped to the '
    'engine variable it sets, with its mapping logic and its behaviour when '
    'the user skips it. This is the input contract for Build Guide step 3, '
    'sahacore.onboarding.';

-- The variables an equation computes. Reading this before reporting a
-- parameter missing is the cheapest way not to repeat the CL mistake.
CREATE OR REPLACE VIEW engine_internal.datamap_computed AS
    SELECT variable, layer, equations, units, full_description
    FROM engine_internal.datamap_variable
    WHERE data_source = 'Computed'
    ORDER BY layer, source_row;

COMMENT ON VIEW engine_internal.datamap_computed IS
    'Variables the DataMap marks as computed rather than stored. A key here '
    'has no value to look up and is not a missing parameter.';

-- The onboarding fields the engine cannot proceed without.
CREATE OR REPLACE VIEW engine_internal.datamap_required_onboarding AS
    SELECT step, screen, field_name, engine_variable, target_layer,
           mapping_logic, priority
    FROM engine_internal.datamap_onboarding_field
    WHERE default_if_missing = 'Required'
    ORDER BY source_row;

COMMENT ON VIEW engine_internal.datamap_required_onboarding IS
    'Onboarding fields with no default: the engine has no way to proceed '
    'without an answer.';

-- The one section-A row whose symbol cell the source leaves empty.
CREATE OR REPLACE VIEW engine_internal.datamap_unnamed_variable AS
    SELECT source_row, layer, equations, full_description
    FROM engine_internal.datamap_variable
    WHERE variable IS NULL;
