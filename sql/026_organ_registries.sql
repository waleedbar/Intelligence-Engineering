-- Organ systems, organ-pathway weights, and the daily target registry.
--
-- Sources: v39sEng2.xlsx, '★ SYS Registry (organs)' (manifest 172),
-- 'REG · Organ×Pathway Long' (112), '★ Target Registry (versioned)' (114).
--
-- TWO NAMESPACES SHARE NUMBERS AND DO NOT SHARE MEANING. SYS1 Cardiovascular
-- holds process cluster C1 Membrane Integrity; SYS7 Neurological holds C7
-- Methylation. Reading a SYS number as a cluster number is the mistake the
-- table invites, and the sheet carries its own resolved instance: SYS11 is
-- Respiratory, because "naming SYS11 Neurological would duplicate SYS7 and
-- drop Respiratory entirely".
--
-- A THIRD NAMESPACE DISAGREES WITH THE FIRST. '★ SYS Registry' is marked
-- AUTHORITATIVE and says "Why NOT O1-O12: the O-namespace is occupied by
-- onboarding" with the binding rule "Any NEW organ reference must use a SYS
-- code". 'REG · Organ×Pathway Long' uses O1-O12. It predates the ruling, but
-- the collision is live: O1 is the cardiovascular organ node in one sheet
-- and the anthropometrics module in 'O·O1 Anthropometrics'. Both are loaded
-- as written; the extractor asserts the disagreement still exists so it
-- cannot be resolved by accident.
--
-- THE ORGAN MAP STOPS AT D13, and that is the fail-closed gate working: 48
-- links over 12 organs and 13 pathways, none for D14 or D15.
-- '00_ENGINEER_START' gate d14_d15_fail_closed reads GLOBAL_MODIFIER_PENDING,
-- "No invented organ weights. Fail closed until evidence-locked mapping is
-- signed off." The gate and the data agree.

CREATE TABLE IF NOT EXISTS engine_internal.organ_system (
    sys_code        TEXT PRIMARY KEY,
    source_row      INTEGER NOT NULL UNIQUE,
    organ_system    TEXT NOT NULL,
    -- The C-code cluster this system holds. NOT the same number: SYS7 holds
    -- C7 Methylation while being Neurological.
    process_cluster TEXT NOT NULL,
    note            TEXT,

    CONSTRAINT organ_system_code_is_canonical CHECK (sys_code ~ '^SYS(1[0-2]|[1-9])$')
);

COMMENT ON TABLE engine_internal.organ_system IS
    'The 12 canonical organ systems. Use SYS codes for any new organ '
    'reference -- the O namespace belongs to onboarding, and C codes are '
    'process clusters, which SYS numbers do not mirror.';

CREATE TABLE IF NOT EXISTS engine_internal.organ_pathway_weight (
    source_row  INTEGER PRIMARY KEY,
    -- O1-O12, the namespace '★ SYS Registry' asks new references not to use.
    -- Kept as written; see the header comment.
    organ_id    TEXT NOT NULL,
    organ_node  TEXT NOT NULL,
    pathway_id  TEXT NOT NULL,
    weight      NUMERIC NOT NULL,

    UNIQUE (organ_id, pathway_id),
    -- D14 and D15 are absent by design, not omission.
    CONSTRAINT organ_pathway_no_d14_d15 CHECK (pathway_id NOT IN ('D14', 'D15'))
);

COMMENT ON CONSTRAINT organ_pathway_no_d14_d15 ON engine_internal.organ_pathway_weight IS
    'Gate d14_d15_fail_closed: "No invented organ weights. Fail closed until '
    'evidence-locked mapping is signed off."';

CREATE TABLE IF NOT EXISTS engine_internal.nutrient_target (
    variable_key TEXT PRIMARY KEY,
    source_row   INTEGER NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    unit         TEXT NOT NULL,
    daily_target TEXT NOT NULL,
    -- Verbatim, including "none established" and "none formal; caution
    -- >4000". A null would read as "no limit".
    upper_limit  TEXT NOT NULL,
    basis_source TEXT NOT NULL,
    version      TEXT
);

COMMENT ON TABLE engine_internal.nutrient_target IS
    'Daily targets and upper limits. CoQ10 and betaine have no IOM DRI or UL '
    'at all -- the sheet''s own note requires they render as adequacy %, '
    'never as a treatment dose, for FDA General Wellness positioning.';

-- Targets whose basis is not an official DRI. These are the rows that must
-- never render as a dose.
CREATE OR REPLACE VIEW engine_internal.targets_without_official_basis AS
    SELECT variable_key, display_name, daily_target, upper_limit, basis_source
    FROM engine_internal.nutrient_target
    WHERE basis_source LIKE 'NO official%'
    ORDER BY variable_key;

COMMENT ON VIEW engine_internal.targets_without_official_basis IS
    'Literature-based wellness proxies with no Institute of Medicine DRI or '
    'UL. "Adequacy display only, NOT clinical dosing."';
