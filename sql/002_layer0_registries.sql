-- Layer 0: canonical registries that all higher SahaCore layers read from.
--
-- `nutrients` holds the 81-row registry (Dr. Ali's "P1 Nutrients 81" sheet,
-- v39sEng2, 81-NUTRIENT REGISTRY v32.10) including the pharmacokinetic
-- parameters needed to drive the C_fast[81]/C_slow[81] state computation,
-- not just display metadata. Every column here maps 1:1 to a field in
-- sahacore/data/nutrients_81.json.

CREATE TABLE IF NOT EXISTS nutrients (
    code                  TEXT PRIMARY KEY,
    num                   SMALLINT NOT NULL UNIQUE CHECK (num BETWEEN 1 AND 81),
    name                  TEXT NOT NULL,
    category              TEXT NOT NULL,
    unit                  TEXT NOT NULL,
    is_nitrate            BOOLEAN NOT NULL DEFAULT FALSE,

    -- which of the two C_fast/C_slow interpretations this nutrient's state follows
    state_semantics       TEXT NOT NULL
                              CHECK (state_semantics IN ('BODY_POOL_PROXY', 'EXPOSURE_EQUIVALENT')),
    canonical_state_unit  TEXT NOT NULL,

    -- gamma-distribution absorption kinetics
    gamma_k_shape         DOUBLE PRECISION NOT NULL CHECK (gamma_k_shape > 0),
    gamma_theta_min       DOUBLE PRECISION NOT NULL CHECK (gamma_theta_min > 0),

    -- clearance rate and fast/slow pool partition
    lambda_per_min        DOUBLE PRECISION NOT NULL CHECK (lambda_per_min > 0),
    kappa_fast            DOUBLE PRECISION NOT NULL CHECK (kappa_fast BETWEEN 0 AND 1),
    kappa_slow            DOUBLE PRECISION NOT NULL CHECK (kappa_slow BETWEEN 0 AND 1),
    w_fast                DOUBLE PRECISION NOT NULL CHECK (w_fast BETWEEN 0 AND 1),

    -- pool half-lives; half_life_slow_d is NULL exactly when kappa_slow = 0
    -- (e.g. water, alcohol, sodium, potassium, chloride have no slow pool)
    half_life_fast_d      DOUBLE PRECISION NOT NULL CHECK (half_life_fast_d > 0),
    half_life_slow_d      DOUBLE PRECISION CHECK (half_life_slow_d IS NULL OR half_life_slow_d > 0),

    v_f_dl                DOUBLE PRECISION NOT NULL CHECK (v_f_dl > 0),
    f_max                 DOUBLE PRECISION NOT NULL CHECK (f_max > 0),
    s_hi_log              DOUBLE PRECISION NOT NULL,
    s_lo_log              DOUBLE PRECISION NOT NULL,
    evidence_prior        TEXT NOT NULL,

    CONSTRAINT kappa_partition_sums_to_one
        CHECK (abs(kappa_fast + kappa_slow - 1.0) < 1e-9),
    CONSTRAINT slow_half_life_matches_slow_pool
        CHECK (
            (kappa_slow = 0 AND half_life_slow_d IS NULL) OR
            (kappa_slow > 0 AND half_life_slow_d IS NOT NULL)
        )
);

CREATE INDEX IF NOT EXISTS idx_nutrients_category ON nutrients (category);
