-- The engine's consolidated wiring map: every equation, what it reads, what
-- it feeds, and on which plane it runs.
--
-- Source: v39sEng2.xlsx, sheet '★ Equation Backbone'.
-- '01_IMPORT_MANIFEST' order 124, role CORE_ENGINE, import YES, backend Yes.
--
-- 58 equations from ONB (the onboarding warm-start prior) through RB (the
-- Rao-Blackwellised factorisation). Where 'EQ · Canonical Build Rows' maps
-- each equation to the Python function it becomes, this maps them to each
-- other -- it is the dependency graph, and the place to look before writing
-- any layer to find out what that layer is supposed to consume.
--
-- WHAT IT SETTLED. Three quantities this build had recorded as missing
-- parameters are computed here rather than looked up:
--
--   CL       B4: CL = CL_renal + CL_hepatic, with B5 and B6 supplying the
--            two terms. Reported MISSING_FK on B-002/B-003; it was never a
--            parameter.
--   rho, g   C2: rho = exp(-k*dt), g = -expm1(-k*dt)/k. This is the exact
--            relation docs/parameter-gaps.md had hypothesised against #125
--            k_Z,k and refused to encode until the workbook stated it. It is
--            stated here.
--
-- eq_id IS NOT THE IDENTITY. 'C2' is Layer C's exact excess-damage
-- integration at row 23 and the Cost-Benefit net-value re-rank at row 61.
-- Third time in this build that an obvious key is not unique, so the sheet's
-- own row number is the primary key here as well.

CREATE TABLE IF NOT EXISTS engine_internal.equation_backbone (
    source_row INTEGER PRIMARY KEY,

    eq_id      TEXT NOT NULL,
    layer      TEXT NOT NULL,
    name       TEXT NOT NULL,
    -- Verbatim, notation and all. Parsing the arrows in inputs/outputs into
    -- a graph is a separate job this sheet does not authorise on its own.
    formula    TEXT NOT NULL,
    inputs     TEXT,
    outputs    TEXT,
    cadence    TEXT,

    CONSTRAINT equation_backbone_has_a_formula CHECK (length(btrim(formula)) > 0)
);

CREATE INDEX IF NOT EXISTS equation_backbone_by_eq_id
    ON engine_internal.equation_backbone (eq_id);
CREATE INDEX IF NOT EXISTS equation_backbone_by_layer
    ON engine_internal.equation_backbone (layer);

COMMENT ON TABLE engine_internal.equation_backbone IS
    'The 58-equation wiring map from ''★ Equation Backbone''. eq_id is not '
    'unique -- C2 names two equations in two layers -- so source_row is the '
    'key.';

-- The backbone joined to the build rows, so an equation's formula and the
-- Python function it becomes can be read together. LEFT JOIN in both
-- directions would be more complete; this is the direction a layer author
-- actually needs.
CREATE OR REPLACE VIEW engine_internal.equation_map AS
    SELECT b.eq_id,
           b.layer,
           b.name,
           b.formula,
           b.inputs,
           b.outputs,
           b.cadence,
           r.python_module_function,
           r.validation_test
    FROM engine_internal.equation_backbone b
    LEFT JOIN engine_internal.eq_build_rows r
           ON r.eq_id = b.eq_id
    ORDER BY b.source_row;

COMMENT ON VIEW engine_internal.equation_map IS
    'Each equation with its formula, its wiring and -- where the build-rows '
    'sheet names one -- the Python function it becomes.';
