-- ONB-001's equations and the parameters they read.
--
-- Source: v39sEng2.xlsx, sheet 'O·O1 Anthropometrics'.
-- '01_IMPORT_MANIFEST' order 71, role ONBOARDING, import YES, backend Yes.
--
-- The authority for the first of Layer 0's fourteen modules, and the first
-- sheet in this build whose contents are executed rather than checked:
-- sahacore/onboarding/anthropometrics.py implements O1.1-O1.10 and reads
-- every one of these parameters rather than carrying its own copy.
--
-- WHY THE PARAMETERS ARE A TABLE AND NOT LITERALS IN THE MODULE. Each row
-- here names where its value came from -- 'IDF/WHO harmonized 2009',
-- 'Ashwell et al. 2012', 'West et al. 1997'. A number typed into a .py file
-- loses that, and with it the ability to answer why the male waist threshold
-- is 94 cm. The sheet went to the trouble of sourcing all twelve.
--
-- THE VALUES ARE STORED AS TEXT IN THE WORKBOOK -- '15', not 15 -- which is
-- the same defect that once loaded 73 of 192 parameter-registry rows. The
-- extractor converts and refuses anything that will not parse, so a value
-- cannot reach a physiological calculation as a string.

CREATE TABLE IF NOT EXISTS engine_internal.onboarding_o1_equation (
    equation_id TEXT PRIMARY KEY,
    source_row  INTEGER NOT NULL UNIQUE,
    name        TEXT NOT NULL,

    -- Verbatim, so the implementation can be read against the source.
    formula     TEXT NOT NULL,

    -- The sheet's own notes on what each symbol is -- including the two
    -- 'GENERIC PRIOR ONLY' cautions on O1.1 and O1.2, which are the
    -- difference between a prior and a claimed physiological volume.
    variables   TEXT,

    units       TEXT NOT NULL,
    value_range TEXT NOT NULL,

    CONSTRAINT onboarding_o1_equation_id_shape CHECK (equation_id ~ '^O1\.[0-9]+$')
);

CREATE TABLE IF NOT EXISTS engine_internal.onboarding_o1_parameter (
    key         TEXT PRIMARY KEY,

    -- The sheet's own wording, kept beside the key the engine reads.
    name        TEXT NOT NULL UNIQUE,
    source_row  INTEGER NOT NULL UNIQUE,

    value       DOUBLE PRECISION NOT NULL,
    units       TEXT NOT NULL,

    -- NOT NULL: a constant with no provenance is a constant nobody can check.
    source      TEXT NOT NULL,
    calibration TEXT,
    notes       TEXT
);

-- Declared for ONB-001 by 'O · Onboarding Canonical' and 'EQ · Canonical
-- Build Rows' in identical words, absent from the authority sheet, and
-- consumed by no other O1 equation. Implemented from the consolidated rows
-- and recorded here so the gap travels with the value.
CREATE TABLE IF NOT EXISTS engine_internal.onboarding_declared_elsewhere (
    equation_id                 TEXT PRIMARY KEY,
    name                        TEXT NOT NULL,
    formula                     TEXT NOT NULL,
    units                       TEXT NOT NULL,
    declared_by                 TEXT[] NOT NULL,
    absent_from_authority_sheet BOOLEAN NOT NULL,
    consumed_by                 TEXT[] NOT NULL,

    CONSTRAINT declared_elsewhere_has_two_witnesses CHECK (
        array_length(declared_by, 1) >= 2
    )
);
