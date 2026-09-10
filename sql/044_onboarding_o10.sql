-- ONB-010: goal priority weights -- pi_k for a reward whose terms are open.
--
-- Source: v39sEng2.xlsx, sheet 'O·O10 Goal Priority Wts'.
-- '01_IMPORT_MANIFEST' order 80, role ONBOARDING, import YES, backend Yes.
-- Onboarding steps 4 and 11, feeding Layers D and F.
--
-- ONE OF ONLY TWO SHEETS THAT CITE SOURCES. Every goal area names the
-- guideline behind its nutrient targets -- AHA and REDUCE-IT, ADA 2024,
-- NOF/IOF, EFSA, ASRM. 'O·O6 Family History' is the other, so `source` is
-- NOT NULL here for the same reason it is there.
--
-- THE LADDER IS MONOTONE AND ITS BASELINE IS EXACTLY 1.0: Primary 2.5,
-- Secondary 2.0, Tertiary 1.5, unselected 1.0. The baseline being exactly one
-- is what makes pi_k a multiplier on a reward term rather than a rescaling of
-- everything, so a user who ranks nothing gets the unweighted reward.
--
-- THE FINDING: the Primary weight -- the top rung -- is assigned from the
-- "Highest priority goal from Step 4/11". Step 11's eight options ARE these
-- eight rows (six exactly, two where the sheet truncates the UI's label).
-- Step 4's seven are none of them: Weight Loss, Muscle Gain, Energy Levels,
-- Digestive Health, Chronic Condition, Manage Benefits, Healthy Aging. Not
-- one is a goal area, so "Weight Loss" has no pi_k, no nutrient targets and
-- no Z-pathways. ui_status records which rows line up and how.
--
-- AND WHAT THE WEIGHTS MULTIPLY IS UNDECIDED. The engine equation is
-- "H1: r_t^pi = SUM(pi_k * r_k)". Layer H is the conservative bandit and
-- '★ Scoped Builds — LTMLE Bandit' lists its reward proxy as OPEN FOUNDER
-- DECISION 5, noted there as "the single biggest decision". pi_k is settled;
-- r_k is not.

CREATE TABLE IF NOT EXISTS engine_internal.onboarding_o10_goal (
    goal_area            TEXT PRIMARY KEY,
    source_row           INTEGER NOT NULL UNIQUE,
    weight               DOUBLE PRECISION NOT NULL,
    priority_level       TEXT NOT NULL,
    key_nutrient_targets TEXT NOT NULL,
    z_pathways_text      TEXT NOT NULL,

    -- The guideline. Never NULL -- see the header.
    source               TEXT NOT NULL,

    -- How this row's name stands against what Step 11 offers.
    ui_status            TEXT NOT NULL,

    CONSTRAINT onboarding_o10_goal_weight_is_positive CHECK (weight > 0),
    CONSTRAINT onboarding_o10_goal_ui_status_is_known
        CHECK (ui_status IN ('MATCHES_STEP_11_EXACTLY',
                             'PREFIX_OF_A_STEP_11_OPTION',
                             'MATCHES_NO_STEP_11_OPTION'))
);

CREATE TABLE IF NOT EXISTS engine_internal.onboarding_o10_goal_pathway (
    goal_area TEXT NOT NULL
        REFERENCES engine_internal.onboarding_o10_goal(goal_area),
    z_pathway TEXT NOT NULL,

    PRIMARY KEY (goal_area, z_pathway),
    CONSTRAINT onboarding_o10_goal_pathway_shape CHECK (z_pathway ~ '^Z[0-9]+$')
);

CREATE TABLE IF NOT EXISTS engine_internal.onboarding_o10_weight_rule (
    priority_level  TEXT PRIMARY KEY,
    source_row      INTEGER NOT NULL UNIQUE,
    weight          DOUBLE PRECISION NOT NULL,
    assignment_rule TEXT NOT NULL,

    -- Names r_k, which is open founder decision 5.
    engine_equation TEXT NOT NULL,

    CONSTRAINT onboarding_o10_weight_rule_is_at_least_baseline
        CHECK (weight >= 1.0)
);
