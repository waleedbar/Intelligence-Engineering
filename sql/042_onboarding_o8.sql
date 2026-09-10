-- ONB-008: condition modifiers, and the rule that keeps absorption bounded.
--
-- Source: v39sEng2.xlsx, sheet 'O·O8 Condition Modifiers'.
-- '01_IMPORT_MANIFEST' order 78, role ONBOARDING, import YES, backend Yes.
-- Onboarding step 5, feeding Layers A and C.
--
-- This sheet has NO numbered equations. It is one ten-row table plus one rule
-- stated in prose, and the rule is the safety-critical part:
--
--   "any legacy positive F_bio multiplier m is interpreted as an ODDS
--    multiplier and converted to Delta_logit_abs = ln(m). The production
--    equation is F_abs = F_max*sigmoid(logit(F_base/F_max) + sum(Delta_logit
--    _abs)); no direct multiplication may exceed [0,1]."
--
-- An absorbed fraction is bounded and a multiplier is not: F_base 0.8 times
-- 1.5 is 1.2, which is not a fraction of anything. The rule forbids that and
-- gives the transformation that stays in range. It is stored verbatim in
-- onboarding_o8_rule and implemented in sahacore/onboarding/condition_mods.py.
--
-- WHY `gate` IS ITS OWN COLUMN. The table does not only say 'eta_Z7 x1.5' --
-- it says 'eta_Z7 x1.5 ONLY WHEN CALIBRATED', 'eta_Z3 x1.2 only if symptoms
-- support it', 'eta_Z11 x1.5 only when confirmed'. Four of the ten rows gate
-- a number that way and a fifth gates a described modifier. A reader who took
-- the factor and dropped the clause would apply a 50% damage-sensitivity
-- increase the sheet withheld, so the clause is stored separately and the
-- module refuses to return a gated factor without an explicit per-call
-- statement that the gate holds.
--
-- `evidence_role` is doing the same work in the other direction -- 'Safety/
-- target modifier; do not force K malabsorption', 'Timing, not global
-- absorption extent' -- so it is NOT NULL too.
--
-- THE GAP: the Z-pathways column declares 20 condition-to-pathway links and
-- only 9 carry a modifier. Celiac declares Z5, Z11 and Z12 and quantifies
-- none; GERD declares Z3 and quantifies none. Those 11 links are stored with
-- factor NULL rather than 1.0, because 'declared affected, effect unstated'
-- and 'no effect' are different claims. See docs/parameter-gaps.md.

CREATE TABLE IF NOT EXISTS engine_internal.onboarding_o8_rule (
    name TEXT PRIMARY KEY,
    text TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS engine_internal.onboarding_o8_condition (
    condition                 TEXT PRIMARY KEY,
    source_row                INTEGER NOT NULL UNIQUE,

    -- The modifier cell verbatim, gate and all.
    modifier_text             TEXT NOT NULL,

    -- The clause that withholds the modifier, or NULL when it is
    -- unconditional. Never folded into modifier_text alone.
    gate                      TEXT,

    bounded_absorption_effect TEXT NOT NULL,
    target_adjustment         TEXT NOT NULL,
    z_pathways_text           TEXT NOT NULL,

    -- A warning against a specific misreading. Never NULL.
    evidence_role             TEXT NOT NULL
);

-- One row per condition-to-pathway link the sheet DECLARES. factor is NULL
-- where the sheet declares the pathway affected and gives no number -- 11 of
-- the 20 links. A NULL here is a question for the author, not a 1.0.
CREATE TABLE IF NOT EXISTS engine_internal.onboarding_o8_pathway (
    condition TEXT NOT NULL
        REFERENCES engine_internal.onboarding_o8_condition(condition),
    z_pathway TEXT NOT NULL,
    factor    DOUBLE PRECISION,

    PRIMARY KEY (condition, z_pathway),
    CONSTRAINT onboarding_o8_pathway_shape CHECK (z_pathway ~ '^Z[0-9]+$'),
    -- A stated factor is a damage-sensitivity multiplier; on this sheet they
    -- all increase sensitivity, and one at or below zero would be a sign
    -- error rather than a weaker effect.
    CONSTRAINT onboarding_o8_pathway_factor_is_positive
        CHECK (factor IS NULL OR factor > 0)
);
