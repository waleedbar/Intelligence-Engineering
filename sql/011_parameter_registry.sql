-- The parameter registry: every tunable and fixed constant the engine reads,
-- with its units, admissible range, weight and calibration method.
--
-- Source: v39sEng2.xlsx, sheet 'P1 Parameters 134+' -- "CURRENT VERSIONED
-- PARAMETER REGISTRY -- units, ranges, evidence provenance, RB filter
-- parameters, hazards and safe-decision parameters". 192 rows across six
-- blocks (the base registry plus five EXTENSION blocks appended by later
-- versions), extracted by sahacore/data/build_parameter_registry.py.
--
-- Build step 2 of '★ Build Guide Python' names "current parameter/FK
-- registries" among the registries that must load before the equations can
-- "resolve parameter FKs deterministically". This is that registry.
--
-- WHAT IT IS FOR. The sheet holds almost no values: 63 of the 192 rows give
-- only an admissible interval, and the actual per-nutrient and per-cluster
-- numbers live in the entity registries (nutrients, damage_registry_canonical,
-- cluster_scoring_params, ...). Loading it turns "which parameters does this
-- build actually have values for?" from a memory into a query:
--
--     SELECT param_no, symbol, layer, default_or_range
--     FROM engine_internal.parameter_registry
--     WHERE weight = 'Critical'
--       AND value_kind IN ('RANGE','PER_ENTITY_UNSPECIFIED','ABSENT')
--       AND resolved_by IS NULL
--     ORDER BY param_no;
--
-- which is exactly the list to take to the workbook's author, and exactly
-- what tests/test_parameter_registry.py pins so it cannot drift unnoticed.

CREATE TABLE IF NOT EXISTS engine_internal.parameter_registry (
    param_no            INTEGER PRIMARY KEY,
    symbol              TEXT NOT NULL,
    layer               TEXT,
    equations           TEXT,
    full_name           TEXT NOT NULL,
    description         TEXT,
    units               TEXT,

    -- The sheet's "Default Value / Range" cell, verbatim, plus a derived
    -- classification of what kind of thing it actually is.
    default_or_range    TEXT,
    value_kind          TEXT NOT NULL,

    weight              TEXT,
    calibration_method  TEXT,
    verification_source TEXT,

    -- The registry table in THIS build that supplies the per-entity values,
    -- or NULL when nothing does. NULL together with a RANGE value_kind means
    -- the engine has an interval and no number.
    resolved_by         TEXT,

    CONSTRAINT parameter_registry_value_kind_is_known CHECK (value_kind IN (
        'SCALAR',                 -- one number, usable as-is
        'RANGE',                  -- an admissible interval and nothing else
        'RANGE_WITH_DEFAULT',     -- an interval that also states a usable default
        'FORMULA',                -- computed from other quantities
        'PER_ENTITY_UNSPECIFIED', -- explicitly "varies per cluster" etc.
        'TEXT',                   -- prose (an enum, a policy, a citation)
        'ABSENT'                  -- the cell is empty
    )),
    -- 'Weight' is the sheet's own priority column. Its four values are the
    -- only ones that appear across all 192 rows.
    CONSTRAINT parameter_registry_weight_is_known CHECK (
        weight IS NULL OR weight IN ('Critical', 'High', 'Medium', 'Low')
    ),
    CONSTRAINT parameter_registry_param_no_is_positive CHECK (param_no >= 1)
);

CREATE INDEX IF NOT EXISTS parameter_registry_by_layer
    ON engine_internal.parameter_registry (layer, param_no);

-- The open-gap query above, as a view, so operations and CI ask the same
-- question the same way.
CREATE OR REPLACE VIEW engine_internal.parameter_gaps AS
    SELECT param_no, symbol, layer, equations, full_name, units,
           default_or_range, weight
    FROM engine_internal.parameter_registry
    -- RANGE_WITH_DEFAULT is deliberately absent: a stated default is a
    -- usable value, so those rows are not gaps.
    WHERE value_kind IN ('RANGE', 'PER_ENTITY_UNSPECIFIED', 'ABSENT')
      AND resolved_by IS NULL
    ORDER BY
        CASE weight WHEN 'Critical' THEN 0 WHEN 'High' THEN 1
                    WHEN 'Medium' THEN 2 ELSE 3 END,
        param_no;

COMMENT ON VIEW engine_internal.parameter_gaps IS
    'Parameters the engine has an admissible range for but no value, and no '
    'entity registry that supplies one. Ordered by the source sheet''s own '
    'Weight column. See docs/parameter-gaps.md.';
