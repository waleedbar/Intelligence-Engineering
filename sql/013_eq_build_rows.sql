-- The canonical equation build rows.
--
-- Source: v39sEng2.xlsx, sheet 'EQ · Canonical Build Rows'. 119 rows:
-- Stable Eq ID | Layer/Module | Formula / rule | Inputs | Outputs | Units |
-- Cadence | Parameter registry ref | Python module/function | Validation test
-- | Evidence / provenance | Production status.
--
-- WHY IT IS HERE. 104 of the 126 rows in 'PARAM · Eq Param FK' do not list
-- their parameter keys; they say "see formula inputs and named parameter
-- refs". This sheet holds both: column D is the formula inputs and column H
-- is the named parameter reference. Loading it closes that coverage by
-- following the pointer rather than by inventing keys.
--
-- The Inputs column is a mixture of parameter symbols and prose naming data
-- or another equation's output, so each token is classified in
-- eq_build_row_inputs and never converted into a foreign key it is not. A
-- token resolves only when the registry holds its spelling exactly once, for
-- a layer this row's own Layer/Module cell does not contradict; the other
-- near-misses are recorded as AMBIGUOUS or OTHER_LAYER with their rejected
-- candidates, and are readable as engine_internal.withheld_input_tokens.

CREATE TABLE IF NOT EXISTS engine_internal.eq_build_rows (
    source_row             INTEGER PRIMARY KEY,
    eq_id                  TEXT NOT NULL,
    layer_module           TEXT,
    formula_or_rule        TEXT,
    inputs_verbatim        TEXT,
    outputs                TEXT,
    units                  TEXT,
    cadence                TEXT,
    parameter_registry_ref TEXT,
    python_module_function TEXT,
    validation_test        TEXT,
    evidence_provenance    TEXT,
    production_status      TEXT,
    -- The FK rows this build row supplies inputs for. Empty for the eight
    -- build rows the FK sheet does not list at all.
    covers_fk_eq_ids       TEXT[] NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS eq_build_rows_by_eq_id
    ON engine_internal.eq_build_rows (eq_id);

-- One row per (build row, input token), with the token classified.
CREATE TABLE IF NOT EXISTS engine_internal.eq_build_row_inputs (
    source_row      INTEGER NOT NULL REFERENCES engine_internal.eq_build_rows (source_row),
    token_order     INTEGER NOT NULL,
    token           TEXT NOT NULL,
    kind            TEXT NOT NULL,
    registry_symbol TEXT,
    -- The registry symbols this token spells but does not resolve to, and why
    -- each was rejected. Empty unless the kind says otherwise.
    candidates      TEXT[] NOT NULL DEFAULT '{}',

    PRIMARY KEY (source_row, token_order),
    CONSTRAINT eq_build_row_inputs_kind_is_known CHECK (kind IN (
        'SYMBOL',       -- resolves: one registry symbol, layer not contradicted
        'AMBIGUOUS',    -- several share the spelling and nothing chooses
        'OTHER_LAYER',  -- the registry has the spelling, for another layer
        'PROSE'         -- not a symbol at all
    )),
    -- Only a SYMBOL names a registry symbol, and it must name one.
    CONSTRAINT eq_build_row_inputs_symbol_link CHECK (
        (kind = 'SYMBOL') = (registry_symbol IS NOT NULL)
    ),
    -- A withheld token must say what it was withheld from; nothing else may
    -- carry candidates. This is what stops a near-miss being downgraded to
    -- plain prose and disappearing.
    CONSTRAINT eq_build_row_inputs_candidates_recorded CHECK (
        (kind IN ('AMBIGUOUS', 'OTHER_LAYER')) = (cardinality(candidates) > 0)
    )
);

CREATE INDEX IF NOT EXISTS eq_build_row_inputs_by_kind
    ON engine_internal.eq_build_row_inputs (kind);

-- Coverage of build step 2's FK half, as a query: which FK rows now have a
-- build row behind them, and which do not.
CREATE OR REPLACE VIEW engine_internal.fk_coverage AS
    SELECT f.source_row,
           f.eq_id,
           f.keys_are_explicit,
           EXISTS (
               SELECT 1 FROM engine_internal.eq_build_rows b
               WHERE f.eq_id = ANY (b.covers_fk_eq_ids)
           ) AS has_build_row
    FROM engine_internal.eq_param_fk f
    ORDER BY f.source_row;

-- The tokens that spell a registry symbol without being one. A short list,
-- and a finding rather than a nuisance: each row is a quantity an equation
-- consumes that the registry does not hold under that equation's own layer.
CREATE OR REPLACE VIEW engine_internal.withheld_input_tokens AS
    SELECT b.eq_id,
           b.layer_module,
           b.parameter_registry_ref,
           i.token,
           i.kind,
           i.candidates
    FROM engine_internal.eq_build_row_inputs i
    JOIN engine_internal.eq_build_rows b USING (source_row)
    WHERE i.kind IN ('AMBIGUOUS', 'OTHER_LAYER')
    ORDER BY i.kind, b.eq_id, i.token_order;

COMMENT ON VIEW engine_internal.withheld_input_tokens IS
    'Input tokens that match a parameter-registry spelling but were not '
    'resolved to it, with the candidates rejected. See '
    'tests/test_eq_build_rows.py, which pins every row by (equation, token).';

COMMENT ON VIEW engine_internal.fk_coverage IS
    'For each FK row: does a canonical build row supply its formula inputs? '
    'Rows with has_build_row = false are the FK sheet''s ".." spans, whose '
    'members are not enumerated anywhere, plus three K3-N rows with no build '
    'row at all.';
