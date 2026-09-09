-- The per-cluster ceiling on the scarring feedback loop.
--
-- Source: v39sEng2.xlsx, sheet '★ Scarring Bistability Guard'.
-- '01_IMPORT_MANIFEST' order 17, role MEMORY_WARNING, import YES, backend Yes.
--
-- WHY A CAP EXISTS AT ALL, in the sheet's words:
--
--   "The scarring loop is positive feedback: damage raises scarring and
--    scarring suppresses repair."
--
-- and what happens without one:
--
--   "Two users with identical intake settle in different long-run states."
--
-- The destabilising group is gamma_scar * (alpha_scar / beta_autophagy).
-- Past a per-cluster threshold the removal curve folds back and the damage
-- level admits three equilibria -- stable, unstable, stable -- so a user who
-- crosses the fold cannot return by undoing what they did.
--
-- WHY IT IS HERE IN PHASE 1 RATHER THAN WITH LAYER M. Parameter #190
-- (kappa_bist) says the bound is asserted "at build time". A build-time
-- assert needs the caps present as data before the first equation module is
-- written, so the table belongs with the registries.
--
-- ONE NUMBER WOULD NOT DO, and the sheet says so in capitals:
--
--   "READ THE LAST COLUMN, NOT A SINGLE NUMBER.  A blanket cap of gamma*r <=
--    0.75 would be 5x too tight for C6 and still too loose for C7."
--
-- C6 tolerates 4.86 and C7 only 0.87 -- a 5.6-fold spread across clusters.

CREATE TABLE IF NOT EXISTS engine_internal.bistability_cap (
    cluster_id             TEXT PRIMARY KEY,
    cluster_name           TEXT NOT NULL,
    source_row             INTEGER NOT NULL UNIQUE,

    -- From '★ Damage Registry — Canonical', restated here.
    tau_dam_days           NUMERIC NOT NULL,
    tau_heal_days          NUMERIC NOT NULL,

    -- Section 2: V_k = V_max/(k*theta) = 1.443 * tau_dam,k / tau_heal,k.
    v_repair               NUMERIC NOT NULL,

    -- The bound this table exists for.
    cap_gamma_r            NUMERIC NOT NULL,
    gamma_scar             NUMERIC NOT NULL,
    max_alpha_beta_ratio   NUMERIC NOT NULL,

    -- Section 8, the independent verification receipt. Kept because a sheet
    -- that carries its own second opinion should not lose it on import.
    f_prime_min_at_cap     TEXT NOT NULL,
    receipt_agrees         TEXT NOT NULL,

    CONSTRAINT bistability_cap_is_positive CHECK (cap_gamma_r > 0),
    CONSTRAINT bistability_timescales_are_positive CHECK (
        tau_dam_days > 0 AND tau_heal_days > 0
    ),
    -- gamma_scar takes exactly two values across the twelve clusters. This is
    -- not a tolerance to widen: a third value means the source changed, and
    -- the caps must then be re-derived rather than extended.
    CONSTRAINT bistability_gamma_scar_is_declared CHECK (
        gamma_scar IN (0.6, 1.2)
    ),
    CONSTRAINT bistability_receipt_confirms CHECK (receipt_agrees = 'YES')
);

-- Section 6: the point check compares POINT estimates, and the sheet says
-- plainly that is not enough --
--
--   "But alpha_scar, beta_autophagy and gamma_scar are uncertain priors until
--    the Phase-2 cohort fit"
--
-- Four guards are specified. Only PG-1 is placed on this sheet; PG-2 belongs
-- to '★ Validation Test Battery' test C17 and PG-3 to 'M-W LayerW Equations',
-- neither of which is imported yet. They are stored as specifications so the
-- placement is visible when those sheets arrive -- not implemented, because
-- implementing a guard from its one-line summary would be inventing it.
CREATE TABLE IF NOT EXISTS engine_internal.bistability_probabilistic_guard (
    guard_id      TEXT PRIMARY KEY,
    source_row    INTEGER NOT NULL UNIQUE,
    name          TEXT NOT NULL,
    specification TEXT NOT NULL,
    placement     TEXT NOT NULL,

    CONSTRAINT bistability_guard_id_is_pg CHECK (guard_id ~ '^PG-[1-9][0-9]*$')
);

-- Section 5. Recorded because the caps only mean what they mean while
-- monotonicity is the adopted option: under the alternative they stop being
-- build-time asserts and become one edge of a declared hysteresis band.
CREATE TABLE IF NOT EXISTS engine_internal.bistability_decision (
    option     TEXT PRIMARY KEY,
    source_row INTEGER NOT NULL UNIQUE,
    meaning    TEXT NOT NULL,
    status     TEXT NOT NULL
);

-- Section 4. What the declared parameter ranges permitted before the caps
-- were derived: alpha/beta reachable over 0.53-16.67, gamma*(alpha/beta) up
-- to 26.7 at the worst corner -- "30x the tightest cluster bound", and a 34.8%
-- hysteresis width that, in the sheet's words, nobody chose:
--
--   "it was an emergent accident of the parameter ranges"
--
-- Kept so the reason for the table is legible next to the table.
CREATE TABLE IF NOT EXISTS engine_internal.bistability_unconstrained_range (
    quantity    TEXT PRIMARY KEY,
    source_row  INTEGER NOT NULL UNIQUE,
    value       TEXT NOT NULL,
    consequence TEXT NOT NULL
);

-- PG-1 as a query: B_k = cap_k / (gamma_k * r_k), require B_k >= 1, and the
-- sheet asks for it "Reported per cluster, not just pass/fail". The margin is
-- a function of a candidate (gamma, alpha, beta), so this is a function
-- rather than a view -- it answers "would these values fold this cluster?".
--
-- PG-3's freeze threshold (B_k < 1.25) is returned alongside the pass flag so
-- a caller cannot read the pass and miss the proximity.
CREATE OR REPLACE FUNCTION engine_internal.bistability_margin(
    p_gamma_scar NUMERIC,
    p_alpha_scar NUMERIC,
    p_beta_autophagy NUMERIC
) RETURNS TABLE (
    cluster_id    TEXT,
    cluster_name  TEXT,
    cap_gamma_r   NUMERIC,
    gamma_r       NUMERIC,
    margin        NUMERIC,
    admitted      BOOLEAN,
    near_fold     BOOLEAN
) LANGUAGE sql STABLE AS $$
    SELECT c.cluster_id,
           c.cluster_name,
           c.cap_gamma_r,
           p_gamma_scar * (p_alpha_scar / p_beta_autophagy)          AS gamma_r,
           c.cap_gamma_r / (p_gamma_scar * (p_alpha_scar / p_beta_autophagy))
                                                                     AS margin,
           c.cap_gamma_r / (p_gamma_scar * (p_alpha_scar / p_beta_autophagy))
               >= 1                                                  AS admitted,
           c.cap_gamma_r / (p_gamma_scar * (p_alpha_scar / p_beta_autophagy))
               < 1.25                                                AS near_fold
    FROM engine_internal.bistability_cap c
    ORDER BY margin;
$$;
