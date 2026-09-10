-- ONB-005: substance exposure -- tobacco, alcohol and sugary drinks.
--
-- Source: v39sEng2.xlsx, sheet 'O·O5 Substance Exposure'.
-- '01_IMPORT_MANIFEST' order 75, role ONBOARDING, import YES, backend Yes.
-- Onboarding steps 3 and 10, feeding Layers C and E.
--
-- FOUR ENCODINGS IN ONE TABLE. This sheet turns a user's answer into a
-- number four separate times -- pack_years and tobacco_idx from the same
-- smoking answer, units_week from the alcohol band, and O5.5's SSB
-- servings -- and each is the sheet's judgement about what an answer is
-- worth, so each is stored rather than retyped into a module.
--
-- WHY `option` IS NULLABLE. Three of the four encodings label their options
-- ('Never=0', '1-3=2'). O5.5's does not: its Variables cell reads
-- "(midpoint: 0/0.5/1.75/3)" and gives four bare numbers. Pairing them with
-- Step 3's four bands would be this build deciding which number means which
-- answer, so they are stored by position with a NULL option instead.
--
-- FIRST SHEET IMPORTED AFTER ITS OWN UI CONTRACT. 'O·Step-by-Step Questions'
-- is manifest order 70 and landed first, so for the first time an O-sheet's
-- inputs are checked against what the interface actually collects. The
-- extractor holds this sheet to that one, and three of its four findings
-- exist only because it can.
--
-- WHAT CORROBORATES: O5.2's alcohol midpoints are the exact midpoints of
-- Step 10's bands, and O5.3's ceiling (1.4 * 1.1 = 1.54) matches its
-- declared "1.0-1.5+".
--
-- FOUR FINDINGS, none corrected, all in docs/parameter-gaps.md:
--   1. O5.5's "midpoints" 0/0.5/1.75/3 are not the midpoints of Step 3's
--      bands 0 / 1-2 / 3-4 / 5+ (which are 0/1.5/3.5).
--   2. Step 10 offers no "Former" option, so O5's five smoking categories
--      are a join of two UI answers and no sheet gives the rule.
--   3. O5.1 ties Former(<1yr) with Occasional; O5.7 does not.
--   4. O5.6's male branch is unreachable if drinks_wk is units_week.

CREATE TABLE IF NOT EXISTS engine_internal.onboarding_o5_equation (
    equation_id   TEXT PRIMARY KEY,
    source_row    INTEGER NOT NULL UNIQUE,
    name          TEXT NOT NULL,
    formula       TEXT NOT NULL,
    variables     TEXT NOT NULL,
    units         TEXT NOT NULL,
    value_range   TEXT NOT NULL,

    -- 'Layer C: Z2 Oxidative DNA', 'O11: Z8 Hepatic Fibrosis'.
    engine_target TEXT NOT NULL,

    CONSTRAINT onboarding_o5_equation_id_shape CHECK (equation_id ~ '^O5\.[0-9]+$')
);

CREATE TABLE IF NOT EXISTS engine_internal.onboarding_o5_encoding (
    equation_id      TEXT NOT NULL
        REFERENCES engine_internal.onboarding_o5_equation(equation_id),

    -- The quantity the encoding produces: 'pack_years', 'units_week',
    -- 'tobacco_idx', 'SSB_serv_day'.
    encodes          TEXT NOT NULL,
    ordinal_position INTEGER NOT NULL,

    -- NULL for O5.5, whose four midpoints carry no labels.
    option           TEXT,
    value            DOUBLE PRECISION NOT NULL,

    PRIMARY KEY (encodes, ordinal_position),
    CONSTRAINT onboarding_o5_encoding_position_is_positive
        CHECK (ordinal_position >= 1),
    CONSTRAINT onboarding_o5_encoding_is_not_negative
        CHECK (value >= 0)
);
