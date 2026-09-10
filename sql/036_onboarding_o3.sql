-- ONB-003's equations: the sleep prior.
--
-- Source: v39sEng2.xlsx, sheet 'O·O3 Sleep Deficit'.
-- '01_IMPORT_MANIFEST' order 73, role ONBOARDING, import YES, backend Yes.
--
-- All eight equations are implemented in sahacore/onboarding/sleep_deficit.py.
-- sahacore.data.onboarding_symbols reports no symbol this sheet uses and the
-- workbook fails to define -- the first of the three O-sheets for which that
-- is true. O3.7 defines e_sleepqual inline, "(5-quality)/4", where O1.9
-- leaves e_WHtR and e_BMI undefined.
--
-- NO PARAMETERS TABLE. Unlike O1, every constant lives inside a formula, so
-- there is nothing here for a module to read from a registry. What IS read
-- is O3.6's ordinal scale: a user answering "Fairly consistent" scores 3
-- because the sheet says so, not because the module chose it.
--
-- TWO DEFINITIONS OF SLEEP SHORTFALL, AND THEY DISAGREE.
--
--   O3.1 SDS       one-sided and SIGNED. At nine hours it is (7-9)/7 times
--                  the quality factor -- negative -- while the sheet's own
--                  declared range for it is 0-1.
--   O3.5 sleep_def two-sided and clamped: zero across seven to nine hours,
--                  rising on both sides, never negative.
--
-- Both are loaded as written and implemented under their own names. Reported
-- in docs/parameter-gaps.md, not resolved here.

CREATE TABLE IF NOT EXISTS engine_internal.onboarding_o3_equation (
    equation_id   TEXT PRIMARY KEY,
    source_row    INTEGER NOT NULL UNIQUE,
    name          TEXT NOT NULL,
    formula       TEXT NOT NULL,
    variables     TEXT,
    units         TEXT NOT NULL,
    value_range   TEXT NOT NULL,

    -- Where the output goes: 'Layer C: Z3 Inflammation rate', 'O3.7'.
    engine_target TEXT NOT NULL,

    CONSTRAINT onboarding_o3_equation_id_shape CHECK (equation_id ~ '^O3\.[0-9]+$')
);

-- O3.6's schedule-consistency scale, written inline in its formula cell
-- rather than in an encoding table. Four ordered options; the module reads
-- the scores from here.
CREATE TABLE IF NOT EXISTS engine_internal.onboarding_o3_ordinal (
    equation_id TEXT NOT NULL
                REFERENCES engine_internal.onboarding_o3_equation(equation_id),
    option      TEXT NOT NULL,
    score       DOUBLE PRECISION NOT NULL,

    PRIMARY KEY (equation_id, option),
    CONSTRAINT onboarding_o3_ordinal_score_is_positive CHECK (score >= 1)
);
