-- Supplements, and the effect cap each one carries.
--
-- Source: v39sEng2.xlsx, sheet '★ Supplement Registry'.
-- '01_IMPORT_MANIFEST' order 42, role REGISTRY, import YES, backend Yes.
--
-- THE NULL-CAP RULE, in the sheet's own words:
--
--   "Where randomised trials of the supplement form are null, the engine
--    caps its modelled effect at zero regardless of how strong the
--    dietary-pattern evidence is... A null cap is not an omission -- it is
--    the finding."
--
-- and why the registry is separate from the 81 nutrients at all:
--
--   "Keeping one registry would let a strong dietary association silently
--    license a supplement claim the trials do not support."
--
-- That is a claim the engine could make by accident rather than by decision.
-- A vitamin D capsule adds to vit_d_iu; the dietary pattern for vitamin D
-- carries real cardiovascular weight; without a cap the supplement inherits
-- that weight, which VITAL does not support. Four supplements are null-capped
-- today -- CoQ10, vitamin D, EPA+DHA and curcumin -- and the extractor
-- refuses to write if that set changes, because adding or removing one is a
-- safety decision rather than a data edit.

CREATE TABLE IF NOT EXISTS engine_internal.supplement_registry (
    supplement               TEXT PRIMARY KEY,
    source_row               INTEGER NOT NULL UNIQUE,

    -- Verbatim: 'YES → vit_d_iu', 'NO — supplement only',
    -- 'Partial → glycine, proline', 'YES → several'.
    maps_to_canonical        TEXT,
    -- The cell's first word, which the sheet writes consistently.
    mapping_kind             TEXT,
    -- Only canonical ids that appear in the cell AND exist in the nutrient
    -- registry. 'several' yields an empty array rather than a guess about
    -- which several; 'glycine, proline' likewise, because the registry spells
    -- those aa_glycine_mg and aa_proline_mg and bridging the two here would
    -- be an undeclared alias.
    maps_to_nutrients        TEXT[] NOT NULL DEFAULT '{}',

    effect_cap               TEXT,
    evidence_position        TEXT,
    cluster_effect_permitted TEXT,

    -- False for the one row the source leaves unfinished.
    is_complete              BOOLEAN NOT NULL,

    CONSTRAINT supplement_mapping_kind_is_known CHECK (
        mapping_kind IS NULL OR mapping_kind IN ('YES', 'NO', 'PARTIAL')
    ),
    -- A complete row must state its cap. An incomplete one must not pretend
    -- to: the whole point of keeping it is that the cap is unknown.
    CONSTRAINT supplement_complete_rows_state_a_cap CHECK (
        is_complete = (effect_cap IS NOT NULL
                       AND evidence_position IS NOT NULL
                       AND cluster_effect_permitted IS NOT NULL
                       AND maps_to_canonical IS NOT NULL)
    )
);

COMMENT ON TABLE engine_internal.supplement_registry IS
    'Supplements and their effect caps. Separate from the 81 nutrients so a '
    'dietary association cannot license a supplement claim the randomised '
    'trials do not support -- the sheet''s NULL-CAP rule.';

-- The supplements whose modelled effect is capped at zero. Layer C reads
-- this before letting a supplement dose reach a damage weight.
CREATE OR REPLACE VIEW engine_internal.supplement_null_capped AS
    SELECT supplement, effect_cap, evidence_position, maps_to_nutrients
    FROM engine_internal.supplement_registry
    WHERE effect_cap IS NOT NULL AND upper(effect_cap) LIKE '%NULL CAP%'
    ORDER BY supplement;

COMMENT ON VIEW engine_internal.supplement_null_capped IS
    'Supplements whose modelled effect is zero regardless of dietary-pattern '
    'evidence. "A null cap is not an omission -- it is the finding."';

-- The rows the source has not finished. Empty is the goal; not empty is a
-- question for the workbook''s author, not something to fill in here.
CREATE OR REPLACE VIEW engine_internal.supplement_incomplete AS
    SELECT supplement, source_row
    FROM engine_internal.supplement_registry
    WHERE NOT is_complete
    ORDER BY source_row;
