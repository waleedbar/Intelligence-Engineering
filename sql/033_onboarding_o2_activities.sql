-- ONB-002: the physical-activity prior, and the MET catalogue it reads.
--
-- Sources: v39sEng2.xlsx, sheets 'O·O2 MVPA Prior' (manifest order 72) and
-- 'P1 Activities 50' (order 46). Both import YES, backend Yes, and both
-- named by 'O · Onboarding Canonical' as ONB-002's authorities.
--
-- SIX OF O2'S EIGHT EQUATIONS ARE IMPLEMENTED. O2.4 and O2.5 are recorded
-- with computable = false and the symbol each waits on, because:
--
--   O2.4  PA_benefit = 100 * (1 - HR_Arem).  HR_Arem is described on the
--         authority sheet -- "hazard ratio from dose-response curve,
--         Anchored at 150-300 min/wk zone" -- and given nowhere.
--
--         'O · Onboarding Canonical' and 'EQ · Canonical Build Rows' both
--         define the same quantity differently:
--             PA_benefit = 100*(1-exp(-MET_min_week/K_PA))
--         a saturating exponential rather than a hazard ratio. K_PA appears
--         in exactly those two cells and in neither parameter registry.
--
--   O2.5  rho_modified needs O2.4's output and rho_pop, which appears twice
--         in the workbook -- both times inside O2.5 -- and in neither
--         registry.
--
-- PA_benefit feeds Layer C's repair rate through 'O·Engine Connections', so
-- a guess would not stay contained. See docs/parameter-gaps.md.

CREATE TABLE IF NOT EXISTS engine_internal.onboarding_o2_equation (
    equation_id     TEXT PRIMARY KEY,
    source_row      INTEGER NOT NULL UNIQUE,
    name            TEXT NOT NULL,
    formula         TEXT NOT NULL,
    variables       TEXT,
    units           TEXT NOT NULL,
    value_range     TEXT NOT NULL,

    -- THIS BUILD'S columns. False means a symbol the workbook never defines.
    computable      BOOLEAN NOT NULL,
    missing_symbol  TEXT,
    unresolved_note TEXT,

    CONSTRAINT onboarding_o2_equation_id_shape CHECK (equation_id ~ '^O2\.[0-9]+$'),
    -- An equation that cannot be computed must say what it is waiting for,
    -- and one that can must not pretend to wait.
    CONSTRAINT onboarding_o2_gap_is_named CHECK (
        (computable = FALSE) = (missing_symbol IS NOT NULL)
    )
);

-- The onboarding screen's ordinal answers and what each one means as a
-- number. "Frequency: 3-4" is 3.5 sessions a week; "Duration: <30 min" is 20
-- minutes, which the sheet calls a "Conservative midpoint" rather than the
-- arithmetic 15. These choices decide what a user's answer means, so the
-- sheet's own reason is stored beside the value.
CREATE TABLE IF NOT EXISTS engine_internal.onboarding_o2_encoding (
    field         TEXT NOT NULL,
    option        TEXT NOT NULL,
    source_row    INTEGER NOT NULL UNIQUE,
    ui_selection  TEXT NOT NULL,
    mapped_value  TEXT NOT NULL,
    numeric_value DOUBLE PRECISION NOT NULL,
    variable      TEXT NOT NULL,
    source        TEXT NOT NULL,

    PRIMARY KEY (field, option),
    CONSTRAINT onboarding_o2_encoding_is_nonnegative CHECK (numeric_value >= 0)
);

-- 'P1 Activities 50': MET values from the 2024 Compendium of Physical
-- Activities (Herrmann et al. 2024), with cluster impacts from the exercise
-- physiology literature.
CREATE TABLE IF NOT EXISTS engine_internal.activity_catalogue (
    activity_id      TEXT PRIMARY KEY,
    number           INTEGER NOT NULL UNIQUE,
    source_row       INTEGER NOT NULL UNIQUE,
    name             TEXT NOT NULL,

    -- A multiple of resting metabolic rate: strictly positive, and 1.0 for
    -- sleep, which anchors the scale.
    met              DOUBLE PRECISION NOT NULL,

    -- The sheet's own banding. NOT held to the Compendium's numeric
    -- boundaries: the sheet cites the Compendium for MET VALUES and does not
    -- claim its labels follow those bands. Six rows disagree with them, and
    -- that is recorded in activity_intensity_disagreement rather than
    -- enforced here.
    intensity        TEXT NOT NULL,

    typical_duration DOUBLE PRECISION NOT NULL,
    duration_unit    TEXT NOT NULL,

    CONSTRAINT activity_met_is_positive CHECK (met > 0),
    CONSTRAINT activity_intensity_is_known CHECK (
        intensity IN ('Sedentary', 'Light', 'Moderate', 'Vigorous')
    ),
    CONSTRAINT activity_duration_is_in_minutes CHECK (duration_unit = 'min')
);

-- SIGNED impacts: sitting quietly carries -0.05 on C1 and -0.1 on C2, while
-- walking carries +0.05 and +0.08. These are directional effects on damage,
-- so the sign is the content.
--
-- SIX CLUSTERS, TWELVE PROMISED. The sheet's banner reads "50-Activity
-- Catalog — MET Values + 12-Cluster Impact Weights" and its columns stop at
-- C6 Oxidative -- not blank cells, no columns at all. The missing half is
-- left missing rather than filled with zeros: a zero here would read as
-- "this activity does not affect methylation", a claim the sheet does not
-- make.
CREATE TABLE IF NOT EXISTS engine_internal.activity_cluster_impact (
    activity_id TEXT NOT NULL REFERENCES engine_internal.activity_catalogue(activity_id),
    cluster_id  TEXT NOT NULL,
    impact      DOUBLE PRECISION NOT NULL,

    PRIMARY KEY (activity_id, cluster_id),
    -- The sheet carries C1..C6 only. A C7 here would mean the catalogue was
    -- completed, which changes what this table can answer.
    CONSTRAINT activity_cluster_is_present_in_the_sheet CHECK (
        cluster_id IN ('C1', 'C2', 'C3', 'C4', 'C5', 'C6')
    )
);

-- Rows whose intensity label disagrees with the Compendium's own numeric
-- bands (sedentary <= 1.5, light 1.6-2.9, moderate 3.0-5.9, vigorous >= 6.0).
-- Recorded because the sheet cites the Compendium as its source, and because
-- O2.6 splits activity by these labels while weighting with 4.5 and 7.5 --
-- the midpoints of the Compendium's bands, not of this catalogue's.
CREATE TABLE IF NOT EXISTS engine_internal.activity_intensity_disagreement (
    activity_id          TEXT PRIMARY KEY
                         REFERENCES engine_internal.activity_catalogue(activity_id),
    met                  DOUBLE PRECISION NOT NULL,
    sheet_intensity      TEXT NOT NULL,
    compendium_intensity TEXT NOT NULL,

    CONSTRAINT activity_disagreement_actually_disagrees CHECK (
        sheet_intensity <> compendium_intensity
    )
);

-- What ONB-002 still cannot compute, and what each one is waiting for.
CREATE OR REPLACE VIEW engine_internal.onboarding_o2_gaps AS
    SELECT equation_id, name, formula, missing_symbol, unresolved_note
    FROM engine_internal.onboarding_o2_equation
    WHERE NOT computable
    ORDER BY equation_id;
