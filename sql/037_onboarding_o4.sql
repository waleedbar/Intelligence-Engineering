-- ONB-004: the PSS-10 stress instrument, its equations and its bands.
--
-- Source: v39sEng2.xlsx, sheet 'O·O4 Stress Index'.
-- '01_IMPORT_MANIFEST' role ONBOARDING, import YES, backend Yes.
-- Onboarding step 8, feeding Layers C and E.
--
-- Three tables because the sheet has three, and each is a different kind of
-- authority: the instrument says what is asked and how it is scored, the
-- equations say what is computed, and the bands say what a score means.
--
-- PSS-10, NOT PSS-4. The sheet's own header calls that a correction, so the
-- ten items are stored rather than assumed, with the reverse flag on each.
-- The four reverse-scored items are stated twice on the sheet -- in the
-- Reverse? column and inside O4.1's formula -- and the extractor refuses to
-- import a sheet where those two disagree.
--
-- NO PARAMETERS TABLE, as on O3: 0.4, 0.3, 0.15, the 40-point denominator and
-- p_stressprot's 0.05-per-practice with its 0.20 cap are all written inside
-- formulas, so they are transcribed with them.
--
-- THE FINDING: p_stressprot REACHES NOTHING. O4.3 computes
--
--     stress_idx_adj = max(0, stress_idx_raw - p_stressprot)
--
-- and names O4.4, O4.5, O4.6 and O4.7 as its consumers. None of the four
-- reads it: O4.4 recomputes Theta_AL = PSS10/40 from the total, and O4.5
-- through O4.9 all read Theta_AL. So the credit a user earns for stress
-- practices -- up to 0.20 of a 0-1 scale -- changes no modifier the engine
-- uses. Loaded as written and reported in docs/parameter-gaps.md; routing
-- O4.3 into O4.4 would move every downstream modifier and is the author's
-- decision, not this build's.

CREATE TABLE IF NOT EXISTS engine_internal.onboarding_o4_item (
    item_number    INTEGER PRIMARY KEY,
    source_row     INTEGER NOT NULL UNIQUE,
    question       TEXT NOT NULL,

    -- Every item is '0-4'; the 0-40 total assumes one shared scale.
    scale          TEXT NOT NULL,
    scoring        TEXT NOT NULL,
    reverse_scored BOOLEAN NOT NULL,

    CONSTRAINT onboarding_o4_item_is_one_of_ten
        CHECK (item_number BETWEEN 1 AND 10),
    CONSTRAINT onboarding_o4_item_scale_is_zero_to_four
        CHECK (scale = '0-4')
);

CREATE TABLE IF NOT EXISTS engine_internal.onboarding_o4_equation (
    equation_id   TEXT PRIMARY KEY,
    source_row    INTEGER NOT NULL UNIQUE,
    name          TEXT NOT NULL,
    formula       TEXT NOT NULL,
    variables     TEXT,
    units         TEXT NOT NULL,
    value_range   TEXT NOT NULL,

    -- Where the output goes: 'Layer C: Z3 Inflammation', 'O4.4, O4.5, ...'.
    engine_target TEXT NOT NULL,

    CONSTRAINT onboarding_o4_equation_id_shape CHECK (equation_id ~ '^O4\.[0-9]+$')
);

-- The three PSS-10 interpretation bands. They tile 0-40 with no gap and no
-- overlap -- the extractor checks that -- so every possible total has exactly
-- one stated meaning.
CREATE TABLE IF NOT EXISTS engine_internal.onboarding_o4_band (
    score_min       INTEGER PRIMARY KEY,
    score_max       INTEGER NOT NULL,
    source_row      INTEGER NOT NULL UNIQUE,
    score_range     TEXT NOT NULL,
    stress_level    TEXT NOT NULL,
    cortisol_impact TEXT NOT NULL,
    system_response TEXT NOT NULL,

    CONSTRAINT onboarding_o4_band_inside_pss10_range
        CHECK (score_min >= 0 AND score_max <= 40),
    CONSTRAINT onboarding_o4_band_is_not_empty
        CHECK (score_max >= score_min),
    CONSTRAINT onboarding_o4_band_level_is_named
        CHECK (stress_level IN ('Low', 'Moderate', 'High'))
);
