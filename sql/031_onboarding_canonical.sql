-- Layer 0's build contract: fourteen steps, each naming its own function.
--
-- Source: v39sEng2.xlsx, sheet 'O · Onboarding Canonical'.
-- '01_IMPORT_MANIFEST' order 128, role ONBOARDING, import YES, backend Yes.
--
-- This is '★ Build Guide Python' step 3 -- "Implement onboarding warm-start",
-- package sahacore.onboarding, acceptance "length x0=219; PSD P0" -- stated
-- one row per module, with the operational equation, the I/O, the parameter
-- references, the QA that must pass, and the Python function that implements
-- it.
--
-- TWELVE OF THE FOURTEEN ARE BUILDABLE TODAY. ONB-011 and ONB-012 are not,
-- and the reason is a missing bridge rather than missing effort: ONB-011's
-- authority sheet produces FIFTEEN pathway warm-start values and repeats on
-- every one of its fifteen rows "15->12 bridge -> xi_hi/xi_lo; no direct
-- x_hat slot", while the slots ONB-012 fills at 163-186 are twelve CLUSTERS.
-- Five sheets name "the canonical 15->12 bridge" as the step between them.
-- It is not in the workbook. See docs/parameter-gaps.md.

CREATE TABLE IF NOT EXISTS engine_internal.onboarding_step (
    step_id              TEXT PRIMARY KEY,
    source_row           INTEGER NOT NULL UNIQUE,

    -- The detail sheet(s) that own the real equations and parameter values.
    -- This sheet consolidates; it is not the authority.
    authority_sheets     TEXT NOT NULL,

    operational_equation TEXT NOT NULL,
    inputs               TEXT NOT NULL,
    outputs              TEXT NOT NULL,
    parameter_refs       TEXT NOT NULL,

    -- The module to write. Unique across the fourteen.
    python_function      TEXT NOT NULL UNIQUE,

    -- The sheet's own acceptance test for the step.
    validation_qa        TEXT NOT NULL,

    -- NULL when the step can be built today; otherwise what stops it.
    blocked_by           TEXT,

    CONSTRAINT onboarding_step_id_shape CHECK (step_id ~ '^ONB-[0-9]{3}$'),
    CONSTRAINT onboarding_function_is_in_the_package CHECK (
        python_function LIKE 'sahacore.onboarding.%'
    )
);

-- The 219 slot layout ONB-012 declares, verified at extract time against
-- state_vector_219.json -- a different sheet, imported days earlier. Stored
-- so the layout the onboarding code writes into is queryable rather than
-- transcribed into Python from a spreadsheet cell.
--
-- NOTE ON NAMES. The sheet writes slots 163-186 as Z_hi/Z_lo; the state
-- vector registry names those blocks xi_hi/xi_lo, unit log(AU). The log
-- coordinate is what the slot holds. Z = exp(xi) - eps is derived from it
-- and never stored in it, which is what battery test C3 ("Damage positivity
-- (log-coordinates)", BLOCKING) rests on. Both names are kept so the
-- difference stays visible instead of being resolved by whichever sheet was
-- read last.
CREATE TABLE IF NOT EXISTS engine_internal.onboarding_state_block (
    registry_block TEXT PRIMARY KEY,
    sheet_name     TEXT NOT NULL,
    first_index    INTEGER NOT NULL,
    last_index     INTEGER NOT NULL,

    CONSTRAINT onboarding_block_range_is_ordered CHECK (first_index <= last_index),
    CONSTRAINT onboarding_block_is_inside_the_vector CHECK (
        first_index >= 1 AND last_index <= 219
    )
);

-- What Layer 0 can be built from today, and what it cannot.
CREATE OR REPLACE VIEW engine_internal.onboarding_buildable AS
    SELECT step_id, python_function, validation_qa
    FROM engine_internal.onboarding_step
    WHERE blocked_by IS NULL
    ORDER BY step_id;

CREATE OR REPLACE VIEW engine_internal.onboarding_blocked AS
    SELECT step_id, python_function, outputs, blocked_by
    FROM engine_internal.onboarding_step
    WHERE blocked_by IS NOT NULL
    ORDER BY step_id;
