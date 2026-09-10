-- ONB-006: family history as Bayesian prior shifts.
--
-- Source: v39sEng2.xlsx, sheet 'O·O6 Family History'.
-- '01_IMPORT_MANIFEST' order 76, role ONBOARDING, import YES, backend Yes.
-- Onboarding step 6, feeding Layers C, E and O11.
--
-- THE BEST-SOURCED SHEET IN THE BUILD. Every relative risk names the study it
-- came from -- 'EPIC-InterAct consortium', 'AHA journal meta-analysis' -- and
-- no other O-sheet cites a source for any constant. `source` is NOT NULL for
-- that reason: a risk that stopped naming its provenance would be a real
-- regression, not a cosmetic one.
--
-- FOUR STATEMENTS OF EVERY RELATIVE RISK, ALL HELD TOGETHER by the extractor:
-- inside the formula as ln(RR), again pre-computed, again in the Variables
-- cell, and again in this reference table -- with the logarithm recomputed.
--
-- WHY BOTH LOGS ARE STORED. ln(2.72) = 1.000632 and the sheet writes 1.000,
-- because the T2D relative risk is *e* rounded to 2.72 for display. So the
-- sheet's pre-computed log is the exact one and the RR column is the rounded
-- one, and the module reads log_in_formula rather than recomputing. Same
-- shape as the independently-rounded columns on '★ Scarring Bistability
-- Guard'.
--
-- WHAT THE SHEET DOES NOT SUPPLY. O6.8's Pearson-Aitken update and O6.9's
-- liability-threshold model are standard statistics with none of their inputs
-- given -- no covariance blocks, no population means, no threshold, no
-- genetic/environmental split. And O6.11 says "if FH positive" without saying
-- which of the six. All recorded in docs/parameter-gaps.md.

CREATE TABLE IF NOT EXISTS engine_internal.onboarding_o6_equation (
    equation_id     TEXT PRIMARY KEY,
    source_row      INTEGER NOT NULL UNIQUE,
    name            TEXT NOT NULL,
    formula         TEXT NOT NULL,
    variables       TEXT NOT NULL,
    units           TEXT NOT NULL,
    value_range     TEXT NOT NULL,
    engine_target   TEXT NOT NULL,

    -- Set on O6.2-O6.7 only: the Step 6 checkbox the equation reads, and the
    -- relative risk it asserts in two places plus its pre-computed log.
    indicator       TEXT,
    rr_in_formula   DOUBLE PRECISION,
    log_in_formula  DOUBLE PRECISION,
    rr_in_variables DOUBLE PRECISION,

    CONSTRAINT onboarding_o6_equation_id_shape
        CHECK (equation_id ~ '^O6\.[0-9]+$'),
    -- A per-condition equation carries all four or none of them.
    CONSTRAINT onboarding_o6_equation_states_its_risk_completely
        CHECK (num_nonnulls(indicator, rr_in_formula, log_in_formula,
                            rr_in_variables) IN (0, 4)),
    -- The formula and the Variables cell must not disagree.
    CONSTRAINT onboarding_o6_equation_risk_agrees_with_itself
        CHECK (rr_in_formula IS NULL OR rr_in_formula = rr_in_variables),
    CONSTRAINT onboarding_o6_equation_risk_is_an_increase
        CHECK (rr_in_formula IS NULL OR rr_in_formula > 1.0)
);

CREATE TABLE IF NOT EXISTS engine_internal.onboarding_o6_condition (
    condition         TEXT PRIMARY KEY,
    source_row        INTEGER NOT NULL UNIQUE,
    relative_risk     DOUBLE PRECISION NOT NULL,
    log_relative_risk DOUBLE PRECISION NOT NULL,

    -- The study. Never NULL -- see the header.
    source            TEXT NOT NULL,
    z_pathways        TEXT NOT NULL,

    CONSTRAINT onboarding_o6_condition_risk_is_an_increase
        CHECK (relative_risk > 1.0),
    CONSTRAINT onboarding_o6_condition_log_is_positive
        CHECK (log_relative_risk > 0)
);

-- Which damage pathway each family history moves. The RR table's Z-Pathway
-- Affected column is the only statement of this in the workbook, and it is
-- what makes O6.10's "FH_relevant per pathway" answerable at all.
CREATE TABLE IF NOT EXISTS engine_internal.onboarding_o6_condition_pathway (
    condition  TEXT NOT NULL
        REFERENCES engine_internal.onboarding_o6_condition(condition),
    z_pathway  TEXT NOT NULL,

    PRIMARY KEY (condition, z_pathway),
    CONSTRAINT onboarding_o6_condition_pathway_shape
        CHECK (z_pathway ~ '^Z[0-9]+$')
);
