-- ONB-007: the diet-pattern nutrient priors -- and the 1,296 missing numbers.
--
-- Source: v39sEng2.xlsx, sheet 'O·O7 Diet Pattern Priors'.
-- '01_IMPORT_MANIFEST' order 77, role ONBOARDING, import YES, backend Yes.
-- Onboarding step 3, feeding Layers A, B and E.
--
-- WHAT IS NOT IN THESE TABLES IS THE POINT. O7.1 is
--
--     C_f(0)_i ~ N(mu_pattern_i, sigma2_pattern_i)
--
-- and its engine target is 'Layer E: x_hat(0)[1..81]' -- the starting value
-- of every nutrient the engine tracks, 81 of its 219 states. That needs a
-- mean and a variance per nutrient per pattern: 8 x 81 x 2 = 1,296 numbers.
-- The workbook supplies NONE of them, so there is no table here to hold them.
-- What the sheet gives is prose, one line per pattern, and prose is what the
-- pattern table stores.
--
-- Searched before concluding: mu_pattern and sigma2_pattern appear only on
-- this sheet and its duplicate at 'P1 Onboarding' row 328; the 81-nutrient
-- registry carries kinetics and no baseline intake column; and the only other
-- 'pattern' sheet is Layer W's behavioural alarms.
--
-- THE PATTERN LIST IS STATED THREE TIMES AND THE THREE DISAGREE.
--   this sheet          8 patterns, two marked 'Not in current UI'
--   'P1 DataMap' r125   'Radio (8 options)', default 'Standard Balanced'
--   the questionnaire   6 options, including Intermittent Fasting
--
-- The sheet knows about two of the three gaps and says so. It does not know
-- that the interface offers a seventh pattern it has never heard of, so
-- ui_status is stored per pattern and a user selecting Intermittent Fasting
-- matches none of them.

CREATE TABLE IF NOT EXISTS engine_internal.onboarding_o7_equation (
    equation_id   TEXT PRIMARY KEY,
    source_row    INTEGER NOT NULL UNIQUE,
    name          TEXT NOT NULL,
    formula       TEXT NOT NULL,
    variables     TEXT NOT NULL,
    units         TEXT NOT NULL,
    value_range   TEXT NOT NULL,
    engine_target TEXT NOT NULL,

    CONSTRAINT onboarding_o7_equation_id_shape CHECK (equation_id ~ '^O7\.[0-9]+$')
);

CREATE TABLE IF NOT EXISTS engine_internal.onboarding_o7_pattern (
    pattern              TEXT PRIMARY KEY,
    source_row           INTEGER NOT NULL UNIQUE,

    -- Prose. Deliberately TEXT and deliberately not parsed: 'High omega-3,
    -- olive oil, fiber' is a description, and turning it into numbers would
    -- be this build writing the prior the sheet declines to.
    key_nutrient_shifts  TEXT NOT NULL,
    typical_deficiencies TEXT NOT NULL,

    -- The label the sheet says the interface shows, and how that stands up
    -- against what it actually offers.
    ui_label             TEXT NOT NULL,
    ui_status            TEXT NOT NULL,

    CONSTRAINT onboarding_o7_pattern_ui_status_is_known
        CHECK (ui_status IN ('MATCHES_UI_EXACTLY',
                             'DECLARED_NOT_IN_UI',
                             'LABEL_DOES_NOT_MATCH_ANY_UI_OPTION'))
);

-- A diet pattern the interface offers and no O7 pattern claims. One row is
-- expected and it is Intermittent Fasting -- a user can select it and there
-- is no prior, no nutrient shift and no deficiency list anywhere for it.
--
-- The other two rows the exact-match test produces ('Low-carb/Keto',
-- 'Mediterranean') are near-misses against 'Low-carb/Ketogenic' and
-- 'Mediterranean Diet'. They are recorded the same way rather than bridged
-- here, because "plainly means" is the inference this build refuses.
CREATE TABLE IF NOT EXISTS engine_internal.onboarding_o7_ui_option_unclaimed (
    ui_option TEXT PRIMARY KEY
);
