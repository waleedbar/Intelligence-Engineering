-- ONB-009: drug-nutrient modifiers, and what is NOT an absorption effect.
--
-- Source: v39sEng2.xlsx, sheet 'O·O9 Drug-Nutrient Mods'.
-- '01_IMPORT_MANIFEST' order 79, role ONBOARDING, import YES, backend Yes.
-- Onboarding step 7, feeding Layers A, B, C and H.
--
-- O8'S RULE, VERIFIED BY THIS SHEET'S NUMBERS. Five rows carry both a legacy
-- multiplier and its converted shift, and every one is ln(m) to six decimals:
-- Metformin x B12 0.70 -> -0.356675, PPIs x Mg 0.75 -> -0.287682, and so on.
-- The extractor recomputes all five. It is the first place in this build
-- where one sheet's rule is confirmed by another sheet's arithmetic.
--
-- WHY factor AND shift ARE BOTH NULLABLE, AND WHY rule_text IS NOT. Fifteen
-- of the twenty rows carry an ACTION CLASS instead of a number -- TIMING,
-- MONITOR, VETO, VETO/MONITOR, CLEARANCE, N/A -- and those are not smaller
-- absorption effects, they are different kinds of thing. The sheet says so
-- twice, in the production target itself:
--
--   Levothyroxine    'Layer H: timing VETO; do not alter nutrient F_abs'
--   Fluoroquinolones 'Layer H: timing VETO; nutrient F_abs unchanged'
--
-- In both, chelation reduces absorption of the DRUG. Reading it the other way
-- would cut a calcium target because the user takes a thyroid tablet. So
-- production_target is NOT NULL and a CHECK forbids a row from carrying an
-- action class and a shift at once.
--
-- THE DISAGREEMENT THIS SHEET HAS WITH THE VETO REGISTRY is stored rather
-- than resolved. VETO-DN-0265 and VETO-DN-0267 rate insulin and
-- sulfonylureas against carbohydrate intake CRITICAL and action them
-- 'STABLE PATTERN - discuss with prescriber'; row 29 here rates the same
-- drug class MODERATE and actions it MONITOR. Same hypoglycaemia hazard,
-- a prescriber referral against a measurement.
--
-- And the two scales do not match at all: this sheet is CRITICAL/MODERATE/LOW
-- and the VETO registry is CRITICAL/HIGH/MODERATE/LOW/CONTROVERSIAL. HIGH is
-- that registry's LARGEST tier -- 111 of 339 rows, just under a third -- and
-- no O9 row can express it.

CREATE TABLE IF NOT EXISTS engine_internal.onboarding_o9_interaction (
    source_row        INTEGER PRIMARY KEY,
    drug              TEXT NOT NULL,
    nutrient          TEXT NOT NULL,

    -- The cell verbatim: a number, or one of the action classes.
    rule_text         TEXT NOT NULL,
    legacy_multiplier DOUBLE PRECISION,
    delta_logit_abs   DOUBLE PRECISION,

    mechanism_class   TEXT NOT NULL,
    severity          TEXT NOT NULL,

    -- Says whether the effect touches nutrient absorption at all. Never NULL.
    production_target TEXT NOT NULL,

    UNIQUE (drug, nutrient),
    CONSTRAINT onboarding_o9_severity_is_known
        CHECK (severity IN ('CRITICAL', 'MODERATE', 'LOW')),
    -- A multiplier and its shift arrive together or not at all.
    CONSTRAINT onboarding_o9_multiplier_and_shift_agree_on_presence
        CHECK (num_nonnulls(legacy_multiplier, delta_logit_abs) IN (0, 2)),
    -- Every quantified interaction on this sheet REDUCES absorption.
    CONSTRAINT onboarding_o9_multiplier_reduces_absorption
        CHECK (legacy_multiplier IS NULL
               OR (legacy_multiplier > 0 AND legacy_multiplier <= 1)),
    CONSTRAINT onboarding_o9_shift_is_not_positive
        CHECK (delta_logit_abs IS NULL OR delta_logit_abs <= 0),
    -- An action class is not an absorption effect and must not carry one.
    CONSTRAINT onboarding_o9_action_class_has_no_shift
        CHECK (delta_logit_abs IS NULL
               OR rule_text NOT IN ('TIMING', 'MONITOR', 'VETO',
                                    'VETO/MONITOR', 'CLEARANCE', 'N/A'))
);

-- Where this sheet and the drug-nutrient VETO registry rate the same hazard
-- differently. Bridged by hand, one pair at a time; see the extractor.
CREATE TABLE IF NOT EXISTS engine_internal.onboarding_o9_severity_disagreement (
    drug                 TEXT NOT NULL,
    veto_rule_id         TEXT NOT NULL,
    o9_nutrient          TEXT NOT NULL,
    o9_severity          TEXT NOT NULL,
    o9_rule              TEXT NOT NULL,
    o9_production_target TEXT NOT NULL,
    veto_nutrient        TEXT NOT NULL,
    veto_severity        TEXT NOT NULL,
    veto_action          TEXT NOT NULL,

    PRIMARY KEY (drug, veto_rule_id),
    CONSTRAINT onboarding_o9_disagreement_actually_disagrees
        CHECK (o9_severity <> veto_severity)
);
