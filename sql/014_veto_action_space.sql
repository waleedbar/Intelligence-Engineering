-- The safety registry and the Layer H action space.
--
-- Sources: v39sEng2.xlsx, sheets 'MERGE·VETO Drug-Nutrient 339' (339 rules)
-- and 'Action_Space' (127 outcome-bearing actions, 7 information actions,
-- 4 activation phases).
--
-- '★ Build Guide Python' step 2 names Action_Space and MERGE·VETO
-- Drug-Nutrient 339 among the registries that must load before any equation
-- runs. 'Replay Contract' section F makes one of them a release gate:
--
--     VETO-01 | Load VETO table | 339 rows and 339 unique canonical IDs;
--              source IDs retained | Primary-key collision | RELEASE_BLOCKING
--
-- WHY THE CONSTRAINTS ARE HERE RATHER THAN IN THE LOADER. This is the table
-- that decides whether a recommendation reaches a person taking warfarin.
-- The firewall sheet's reasoning applies with more force here than anywhere
-- else in the build: "Copy review can be bypassed by a bug; a database grant
-- cannot." Every invariant below was read off the 339 rows, not imposed on
-- them, and each is checked again in sahacore/data/build_veto_registry.py so
-- a bad row fails before it reaches a migration.

-- === The drug-nutrient VETO library =======================================

CREATE TABLE IF NOT EXISTS engine_internal.veto_drug_nutrient (
    -- The repaired canonical key. 'Replay Contract' section E: "339 rows
    -- contained only 319 unique rule IDs. A unique VETO-DN-0001…0339 rule_id
    -- is canonical; original duplicate source IDs are preserved separately."
    rule_id             TEXT PRIMARY KEY,
    source_row          INTEGER NOT NULL UNIQUE,

    drug_or_class       TEXT NOT NULL,
    nutrient_or_food    TEXT NOT NULL,

    -- Present only on rules that name an engine state; see the CHECK below.
    engine_nutrient_id  TEXT REFERENCES engine_internal.nutrients (code),
    nutrient_category   TEXT NOT NULL,
    link_type           TEXT NOT NULL,

    severity            TEXT NOT NULL,
    action              TEXT NOT NULL,
    bandit_action       TEXT NOT NULL,
    message_id          TEXT NOT NULL,
    clinical_rationale  TEXT NOT NULL,
    k_ij                INTEGER NOT NULL,

    -- Deliberately NOT unique: 339 rules carry 319 distinct source ids, and
    -- the 20 duplicates are the defect the canonical key repaired. They are
    -- kept so the repair stays auditable.
    source_rule_id      TEXT NOT NULL,

    CONSTRAINT veto_rule_id_is_canonical CHECK (rule_id ~ '^VETO-DN-[0-9]{4}$'),

    CONSTRAINT veto_severity_is_known CHECK (severity IN (
        'CRITICAL', 'HIGH', 'MODERATE', 'LOW', 'CONTROVERSIAL'
    )),
    CONSTRAINT veto_link_type_is_known CHECK (link_type IN (
        'engine_state',         -- the rule acts on a modelled nutrient state
        'supplement_offmodel',  -- a supplement the 81-nutrient model does not carry
        'food_flag',            -- a whole food or beverage
        'drug_drug',            -- no nutrient involved
        'nutrient_group',       -- a class of nutrients rather than one
        'review'                -- flagged for clinical review
    )),

    -- THE SAFETY INVARIANT. Severity determines the bandit's response, with
    -- no exceptions across all 339 rows. A CRITICAL rule removes the arm; it
    -- must never be downgraded to a note by an edit that touches one column
    -- and not the other.
    CONSTRAINT veto_severity_determines_bandit_action CHECK (
        (severity = 'CRITICAL'      AND bandit_action = 'HARD_VETO (remove arm)')
     OR (severity = 'HIGH'          AND bandit_action = 'SOFT_PENALTY (down-weight)')
     OR (severity = 'MODERATE'      AND bandit_action = 'WARNING (show note)')
     OR (severity = 'CONTROVERSIAL' AND bandit_action = 'WARNING (show note)')
     OR (severity = 'LOW'           AND bandit_action = 'INFORMATIONAL (passive)')
    ),

    -- A rule carries a nutrient foreign key exactly when it is about an
    -- engine state. The other 89 rules name a supplement, a food, another
    -- drug or a nutrient class; an id filled in for them would point at a
    -- nutrient the rule is not about.
    CONSTRAINT veto_engine_nutrient_id_iff_engine_state CHECK (
        (link_type = 'engine_state') = (engine_nutrient_id IS NOT NULL)
    ),

    -- k_ij is the interaction coefficient the sheet supplies for Layer H.
    CONSTRAINT veto_k_ij_is_positive CHECK (k_ij > 0)
);

CREATE INDEX IF NOT EXISTS veto_by_nutrient
    ON engine_internal.veto_drug_nutrient (engine_nutrient_id)
    WHERE engine_nutrient_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS veto_by_severity
    ON engine_internal.veto_drug_nutrient (severity);

COMMENT ON TABLE engine_internal.veto_drug_nutrient IS
    'Drug x nutrient VETO library, 339 rules. Source: MERGE·VETO '
    'Drug-Nutrient 339 -- NOT the sheet named ''VETO Canonical 339'', which '
    'is marked REFERENCE ONLY / DO NOT IMPORT and holds fewer rows. '
    'Release gate VETO-01 in tests/test_veto_registry.py.';

-- The rules that remove an arm outright, as a query. Layer H reads this
-- rather than re-deriving "which severities are hard vetoes" at call sites.
CREATE OR REPLACE VIEW engine_internal.veto_hard AS
    SELECT rule_id, drug_or_class, nutrient_or_food, engine_nutrient_id,
           action, message_id, clinical_rationale, k_ij
    FROM engine_internal.veto_drug_nutrient
    WHERE bandit_action = 'HARD_VETO (remove arm)'
    ORDER BY rule_id;

COMMENT ON VIEW engine_internal.veto_hard IS
    'The 94 CRITICAL rules, which remove a bandit arm rather than annotate '
    'it. Layer H applies these before ranking (H2: a is selected only if '
    'a is in A_safe).';

-- === The Layer H action space =============================================

CREATE TABLE IF NOT EXISTS engine_internal.action_space (
    action_id                     INTEGER PRIMARY KEY,
    source_row                    INTEGER NOT NULL UNIQUE,

    category                      TEXT NOT NULL,
    subcategory                   TEXT,
    action                        TEXT NOT NULL,
    magnitude_bin                 TEXT,
    primary_target                TEXT,
    cluster_affected              TEXT,

    -- Prose, deliberately. The sheet states where the real gate comes from:
    -- "Layer H builds the action x active-rule gate from the versioned VETO
    -- registry at load time. Do not hard-code." So this is a human-readable
    -- note and engine_internal.veto_drug_nutrient is the authority.
    veto_cross_ref                TEXT,

    default_reward_prior          NUMERIC NOT NULL,
    policy_class                  TEXT,
    online_exploration_rule       TEXT,
    physiological_uncertainty_rule TEXT,
    required_evaluation           TEXT,

    -- Non-null on exactly one arm. The sheet's Phase 3 cell, verbatim:
    -- action 127 (INCREASE Dietary Nitrate) "stays inactive pending
    -- VN-01…VN-07 clinical sign-off ... This is a deliberate safety hold,
    -- not an incomplete rollout."
    activation_hold               TEXT,

    CONSTRAINT action_id_in_range CHECK (action_id BETWEEN 1 AND 127),
    CONSTRAINT action_category_is_known CHECK (category IN (
        'Nutrient', 'Activity', 'Sleep/Stress', 'Timing'
    )),
    -- The hold belongs to arm 127 and to no other. An edit that puts a
    -- second arm on hold, or moves this one, has to say so explicitly by
    -- changing this constraint.
    CONSTRAINT action_hold_is_only_arm_127 CHECK (
        activation_hold IS NULL OR action_id = 127
    )
);

COMMENT ON COLUMN engine_internal.action_space.activation_hold IS
    'Why this arm is not activatable, verbatim from the source sheet. Set on '
    'action 127 only. The sheet instructs: "do NOT activate arm 127 to make '
    'the count full".';

-- Information actions. INFO-01..INFO-07 are NOT among the 127: the sheet
-- says so in capitals, and they run under a separate value-of-information
-- policy rather than being ranked for outcome. Held in their own table so
-- the bandit cannot pick one up by iterating the action space.
CREATE TABLE IF NOT EXISTS engine_internal.action_space_info (
    info_id                   TEXT PRIMARY KEY,
    source_row                INTEGER NOT NULL UNIQUE,
    information_action        TEXT NOT NULL,
    expected_information_gain TEXT,
    user_burden               TEXT,
    eligibility               TEXT,

    CONSTRAINT info_id_is_canonical CHECK (info_id ~ '^INFO-0[1-7]$')
);

COMMENT ON TABLE engine_internal.action_space_info IS
    'The 7 information actions, kept separate from the 127 outcome-bearing '
    'arms exactly as the source sheet requires: "INFORMATION ACTIONS — '
    'SEPARATE VOI POLICY (NOT PART OF THE 127 OUTCOME-BEARING ACTIONS)".';

-- The phased arm-activation schedule: how many arms are eligible at all,
-- given how much data a user has. Transcribed; the per-action phase
-- membership is NOT stated anywhere in the sheet, so it is not stored.
CREATE TABLE IF NOT EXISTS engine_internal.action_space_phase (
    phase              TEXT PRIMARY KEY,
    source_row         INTEGER NOT NULL UNIQUE,
    trigger_condition  TEXT NOT NULL,
    new_arms_activated TEXT NOT NULL,
    cumulative_arms    TEXT NOT NULL,
    active_categories  TEXT
);

COMMENT ON TABLE engine_internal.action_space_phase IS
    'Phased LinUCB arm activation (Oetomo et al. 2023 warm-start). Gates '
    'which arms are eligible by data sufficiency; never bypasses VETO -- '
    'the sheet''s own pseudocode applies the safety filter after the phase '
    'gate, not instead of it.';
