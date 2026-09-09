-- The equation specifications, and the corrections already applied to them.
--
-- Source: v39sEng2.xlsx, sheet 'P1 Core Equations'.
-- '01_IMPORT_MANIFEST' order 23, role CORE_ENGINE, import YES, backend Yes.
--
-- NOT A SECOND COPY OF '★ Equation Backbone'. The two share 22 ids and are
-- written at different levels: the backbone gives one line per equation plus
-- what it reads and feeds; this gives the full formula, its units, and the
-- corrections applied. 29 ids appear only here -- D1-D4, E4-E10, F1-F4,
-- G1-G5, H1-H8, the numbered detail equations -- and 35 only in the
-- backbone. Neither contains the other, so no formula-equality check is made
-- between them; what is checked is that both put a shared id in the same
-- layer, which holds for all 22.
--
-- THE correction_applied COLUMN IS WHY THIS SHEET IS WORTH LOADING. 19 of
-- the 51 equations carry one, and each records a mistake someone already
-- made in that equation:
--
--   B6  "v32.3 FIX: removed redundant f_u (was Q_H*E_H*f_u -- double-counted
--        binding)"
--   C2  "p = 1 enforced (not p = 2)"
--   C6  "P0-8: competitive MM (was independent)"
--   C4  "UNITS FIX. The sedentary term was a rate multiplied by dt and added
--        to a stock outside..."
--
-- Anyone implementing these needs the corrections more than the formulas.

CREATE TABLE IF NOT EXISTS engine_internal.core_equation (
    eq_id              TEXT PRIMARY KEY,
    source_row         INTEGER NOT NULL UNIQUE,

    layer              TEXT NOT NULL,
    name               TEXT NOT NULL,
    formula            TEXT NOT NULL,
    inputs             TEXT,
    outputs            TEXT,
    units              TEXT,

    -- A fix already made to this equation, verbatim. Null where none is
    -- recorded.
    correction_applied TEXT,

    CONSTRAINT core_equation_layer_is_a_letter CHECK (layer ~ '^[A-H]$')
);

CREATE INDEX IF NOT EXISTS core_equation_by_layer
    ON engine_internal.core_equation (layer);

COMMENT ON TABLE engine_internal.core_equation IS
    'The 51 equation specifications of ''P1 Core Equations'', with the '
    'corrections applied to 19 of them. Complements ''★ Equation Backbone'', '
    'which carries the wiring rather than the specification.';

-- The corrections, on their own. Read before implementing any equation:
-- each is a wrong version someone has already written.
CREATE OR REPLACE VIEW engine_internal.equation_corrections AS
    SELECT eq_id, layer, name, correction_applied
    FROM engine_internal.core_equation
    WHERE correction_applied IS NOT NULL
    ORDER BY layer, eq_id;

COMMENT ON VIEW engine_internal.equation_corrections IS
    'Corrections already applied to 19 equations -- units fixes, exponents '
    'pinned, double-counted terms removed. Each names a mistake made once.';

-- Specification and wiring side by side, for the ids both sheets carry.
CREATE OR REPLACE VIEW engine_internal.equation_full AS
    SELECT c.eq_id,
           c.layer,
           c.name,
           c.formula          AS specification,
           c.units,
           c.correction_applied,
           b.formula          AS wiring_summary,
           b.inputs           AS reads_from,
           b.outputs          AS feeds,
           b.cadence
    FROM engine_internal.core_equation c
    LEFT JOIN engine_internal.equation_backbone b ON b.eq_id = c.eq_id
    ORDER BY c.layer, c.source_row;
