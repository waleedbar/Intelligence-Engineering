-- The engine's acceptance criteria, as data.
--
-- Source: v39sEng2.xlsx, sheet '★ Validation Test Battery'.
-- '01_IMPORT_MANIFEST' order 14, role VALIDATION, import YES, backend Yes.
--
-- The sheet's own framing:
--
--   "★ VALIDATION & ADMISSION TEST BATTERY  ·  verification is not clinical
--    validation"
--   "Named mathematical, software and model-admission tests. Synthetic truth
--    can verify code. It cannot validate physiology."
--
-- 71 named tests. 54 of them BLOCKING.
--
-- WHY THIS IS PHASE-1 WORK, ahead of most of what it tests. A criterion that
-- arrives after the code is a criterion the code was not written to meet.
-- And several of these are already executable against registries this build
-- has loaded: I7 and I8 are column sums over the damage and nutrient-cluster
-- registries, I16 is the VETO primary-key integrity check, I6 is the
-- firewall. Importing the battery is what made it visible that two of those
-- were being asserted in this repo at a LOOSER tolerance than the sheet
-- requires -- I7 at 1e-2 where the battery says "exactly", I8 at 1e-4 where
-- it says 1.000000. Both are now held to the battery.

CREATE TABLE IF NOT EXISTS engine_internal.validation_test (
    test_id        TEXT PRIMARY KEY,
    source_row     INTEGER NOT NULL UNIQUE,

    -- The heading the test appears under: 'LEVEL 1 — COMPONENT', 'v33
    -- ADDITIONS', 'LAYER T RESEARCH GATES', and so on.
    section        TEXT NOT NULL,

    target         TEXT NOT NULL,
    method         TEXT NOT NULL,
    pass_criterion TEXT NOT NULL,

    -- BLOCKING stops a release. The BLOCKING_FOR_* variants stop one
    -- specific thing: promotion of a model, raising a feature flag, shipping
    -- the spectral code, or leaving shadow mode.
    gate           TEXT NOT NULL,

    -- THIS BUILD'S columns, in the same sense as
    -- runtime_invariant.enforced_by: what the repo actually runs today.
    --
    --   ENFORCED  a named test executes the stated criterion.
    --   PARTIAL   part of it runs; coverage_note says which part and why the
    --             rest cannot yet.
    --   NOT_YET   nothing runs it, usually because its layer is unbuilt.
    coverage       TEXT NOT NULL,
    enforced_by    TEXT,
    coverage_note  TEXT,

    CONSTRAINT validation_gate_is_known CHECK (
        gate IN ('BLOCKING', 'MONITORED', 'BLOCKING_FOR_PROMOTION',
                 'BLOCKING_FOR_FLAG', 'BLOCKING_FOR_SPECTRAL_CODE',
                 'BLOCKING_FOR_SHADOW')
    ),
    CONSTRAINT validation_coverage_is_known CHECK (
        coverage IN ('ENFORCED', 'PARTIAL', 'NOT_YET')
    ),
    -- A claim of coverage must name the test making it and say what it
    -- covers; a claim of none must not name anything. Without this the
    -- table could report a green build by leaving a field blank.
    CONSTRAINT validation_coverage_is_accountable CHECK (
        CASE coverage
            WHEN 'NOT_YET' THEN enforced_by IS NULL AND coverage_note IS NULL
            ELSE enforced_by IS NOT NULL AND coverage_note IS NOT NULL
        END
    )
);

-- The sheet's section headings, kept so the battery can be read back in the
-- order it was written rather than alphabetically by id.
CREATE TABLE IF NOT EXISTS engine_internal.validation_section (
    source_row INTEGER PRIMARY KEY,
    heading    TEXT NOT NULL
);

-- What is left to build, most binding first. This is the build's own backlog
-- taken from the workbook rather than from anybody's memory.
CREATE OR REPLACE VIEW engine_internal.validation_gaps AS
    SELECT test_id, section, gate, coverage, target, pass_criterion
    FROM engine_internal.validation_test
    WHERE coverage <> 'ENFORCED'
    ORDER BY (gate = 'BLOCKING') DESC, coverage, test_id;

-- A BLOCKING criterion nothing executes cannot stop anything. This is the
-- honest count of that, and it is expected to be large now and to shrink.
CREATE OR REPLACE VIEW engine_internal.blocking_tests_not_enforced AS
    SELECT test_id, section, target, pass_criterion
    FROM engine_internal.validation_test
    WHERE gate = 'BLOCKING' AND coverage = 'NOT_YET'
    ORDER BY test_id;
