-- The workbook's own worked examples, as acceptance vectors.
--
-- Source: v39sEng2.xlsx, sheet 'Live Verification Lab'.
-- '01_IMPORT_MANIFEST' order 5, role VALIDATION, import YES, backend Yes.
--
-- WHAT THE SHEET IS, in its own words:
--
--   "★ v38 LIVE VERIFICATION LAB · the load-bearing numbers, re-derived by
--    live formulas in front of you"
--   "Blue cells are inputs -- change them and watch the PASS/FAIL verdicts
--    move. Black cells are live formulas."
--
-- WHAT THESE NUMBERS ARE NOT. They are not parameter values. The sheet calls
-- its inputs inputs; they exist to be varied, and 'P1 Parameters 134+'
-- remains the registry. Nothing here reaches a parameter table. What the
-- import buys instead is that every derived quantity carries the source's
-- exact Excel formula next to its published result, so an implementation can
-- be held to a number the workbook already committed to rather than to one
-- this build computed for itself.

CREATE TABLE IF NOT EXISTS engine_internal.verification_lab (
    lab_id     TEXT PRIMARY KEY,
    source_row INTEGER NOT NULL UNIQUE,
    title      TEXT NOT NULL,

    -- Three labs keep half of themselves in a wide side table: LAB 2 derives
    -- its gains across a grid, LAB 3 reads a 12x12 coupling matrix, LAB 5
    -- reads two persistence vectors. NULL for the labs whose pane is whole.
    side_table TEXT,

    CONSTRAINT verification_lab_id_shape CHECK (lab_id ~ '^LAB [0-9]+$')
);

CREATE TABLE IF NOT EXISTS engine_internal.verification_lab_quantity (
    lab_id     TEXT NOT NULL REFERENCES engine_internal.verification_lab(lab_id),
    source_row INTEGER NOT NULL,
    name       TEXT NOT NULL,

    -- INPUT   a constant cell -- the sheet's blue, something to vary.
    -- DERIVED a formula cell resolving to a number.
    -- VERDICT a formula cell resolving to a judgement: PASS, FAIL or FIRE as
    --         text in five of the six labs, and TRUE/FALSE in LAB 6, whose
    --         'bounds check' returns a boolean instead.
    --
    -- Taken from whether the cell stores a formula, not from its colour.
    role       TEXT NOT NULL,

    -- The source's Excel formula, verbatim, for everything not an INPUT.
    formula    TEXT,

    value_num  DOUBLE PRECISION,
    value_text TEXT,

    PRIMARY KEY (lab_id, name),

    CONSTRAINT verification_quantity_role_is_known CHECK (
        role IN ('INPUT', 'DERIVED', 'VERDICT')
    ),
    -- An input has no formula; anything derived has one. This is the
    -- classification itself, so it is enforced rather than assumed.
    CONSTRAINT verification_quantity_formula_matches_role CHECK (
        (role = 'INPUT') = (formula IS NULL)
    ),
    -- A numeric quantity carries a number and a verdict carries text.
    CONSTRAINT verification_quantity_value_matches_role CHECK (
        CASE role
            WHEN 'VERDICT' THEN value_text IS NOT NULL AND value_num IS NULL
            ELSE value_num IS NOT NULL AND value_text IS NULL
        END
    ),
    -- The sheet publishes no failing lab. Importing one as data would make a
    -- known-broken gate look like a fixture.
    CONSTRAINT verification_quantity_no_published_failure CHECK (
        role <> 'VERDICT'
        OR (value_text NOT LIKE 'FAIL%' AND value_text <> 'FALSE')
    )
);

-- LAB 3's Gamma: the candidate directed cross-cluster forcing matrix, whose
-- spectral radius the lab re-derives by power iteration.
--
-- STORED AS A CANDIDATE, NOT AS A COEFFICIENT SET. Runtime invariant
-- 'Cluster coupling = OFF (ETA=0)' (00_ENGINEER_START row 27) holds these
-- edges to be hypotheses: "Numeric Gamma edges remain hypotheses; any
-- non-zero gain requires held-out incremental value and full-Jacobian
-- stability." The matrix is imported so the stability claim about it can be
-- re-checked; it is not imported so that anything may multiply by it.
CREATE TABLE IF NOT EXISTS engine_internal.cluster_coupling_gamma (
    driver_cluster TEXT NOT NULL,
    target_cluster TEXT NOT NULL,
    weight         DOUBLE PRECISION NOT NULL,
    source_row     INTEGER NOT NULL,

    PRIMARY KEY (driver_cluster, target_cluster),
    CONSTRAINT gamma_weight_is_a_fraction CHECK (weight >= 0 AND weight <= 1)
);

-- LAB 2: the zero-order-hold gain against the Euler approximation, at three
-- step sizes. The sheet's point is that the relative error grows with dt --
-- 0.6% at a quarter day, 13% at five days.
CREATE TABLE IF NOT EXISTS engine_internal.verification_zoh_gain (
    dt_days        DOUBLE PRECISION PRIMARY KEY,
    source_row     INTEGER NOT NULL UNIQUE,
    analytic_gain  DOUBLE PRECISION NOT NULL,
    euler_gain     DOUBLE PRECISION NOT NULL,
    relative_error DOUBLE PRECISION NOT NULL,

    CONSTRAINT zoh_euler_gain_is_dt CHECK (euler_gain = dt_days)
);

-- LAB 5: the persistence vector now and thirty days ago.
CREATE TABLE IF NOT EXISTS engine_internal.verification_topology_vector (
    component     TEXT PRIMARY KEY,
    source_row    INTEGER NOT NULL UNIQUE,
    tau_reference DOUBLE PRECISION NOT NULL,
    tau_now       DOUBLE PRECISION NOT NULL,
    difference    DOUBLE PRECISION NOT NULL
);

-- LAB 6's closing rules, including the production equation transcribed
-- verbatim: 'dS/dt = alpha·o·(1−S) − beta·S'.
CREATE TABLE IF NOT EXISTS engine_internal.layer_m_rule (
    name       TEXT PRIMARY KEY,
    source_row INTEGER NOT NULL UNIQUE,
    statement  TEXT NOT NULL
);

-- The eight Layer-M inputs LAB 4 and LAB 6 share, re-keyed from the two
-- spellings the sheet uses. One row, because there is one worked example.
CREATE TABLE IF NOT EXISTS engine_internal.layer_m_demo_point (
    only_row               BOOLEAN PRIMARY KEY DEFAULT TRUE,
    s_t                    DOUBLE PRECISION NOT NULL,
    z_t                    DOUBLE PRECISION NOT NULL,
    theta_elastic          DOUBLE PRECISION NOT NULL,
    alpha_scar_per_day     DOUBLE PRECISION NOT NULL,
    beta_autophagy_per_day DOUBLE PRECISION NOT NULL,
    gamma_scar             DOUBLE PRECISION NOT NULL,
    dt_days                DOUBLE PRECISION NOT NULL,
    vmax_base              DOUBLE PRECISION NOT NULL,

    CONSTRAINT layer_m_demo_point_is_singular CHECK (only_row),
    CONSTRAINT layer_m_demo_beta_is_positive CHECK (beta_autophagy_per_day > 0)
);

-- ---------------------------------------------------------------------------
-- FINDING 1 · the demo point sits outside the admitted parameter region.
--
-- LAB 4 and LAB 6 run at gamma_scar = 0.69 and alpha/beta = 4, so gamma*r =
-- 2.76. '★ Scarring Bistability Guard' caps gamma*r per cluster and 2.76 is
-- above the cap for eleven of the twelve; only C6 (4.86) admits it. The demo
-- also uses theta_elastic = 50, which is C5's value, and C5's cap is 1.08 --
-- the second tightest in the table.
--
-- Both labs return PASS, and correctly: LM-P01 asks only whether
-- 0 <= S_next <= 1, and LM-P02 whether two half-steps equal one full step.
-- Neither is wrong. What neither lab does is evaluate PG-1 at all -- LAB 6's
-- own "Parameter rules" row lists S, theta, alpha, beta, gamma, dt and
-- Vmax_base bounds and says nothing about gamma*r.
--
-- This view is the finding, kept queryable rather than corrected: amending a
-- published worked example is the workbook owner's decision. Reported in
-- docs/parameter-gaps.md.
CREATE OR REPLACE VIEW engine_internal.demo_point_outside_admitted_region AS
    SELECT m.*
    FROM engine_internal.layer_m_demo_point d
    -- The lab stores its inputs as double precision, the way the workbook
    -- published them; the caps are exact decimals. The cast is explicit so
    -- the margin is computed in the caps' arithmetic rather than in binary
    -- floating point.
    CROSS JOIN LATERAL engine_internal.bistability_margin(
        d.gamma_scar::NUMERIC,
        d.alpha_scar_per_day::NUMERIC,
        d.beta_autophagy_per_day::NUMERIC) m
    WHERE NOT m.admitted;

-- ---------------------------------------------------------------------------
-- FINDING 2 · LAB 3 treats a gain three sheets call zero as an operating one.
--
-- Row 100 is labelled "η_net (operating gain)" and holds 0.05. Against that:
--
--   00_ENGINEER_START row 27  "Cluster coupling | OFF (ETA=0)", gate
--                             eta_net_zero.
--   Parameter #138 eta_net    "production value is exactly 0"; range
--                             "0 production; any non-zero value is
--                              shadow/data-derived".
--
-- And rows 118-119 derive "stability bound 1/rho" and a "margin x0.5
-- (recommended ceiling)" of 0.577 from the spectral radius -- which is the
-- one derivation parameter #141 (rho_Gamma) rules out by name: "matrix
-- diagnostic; do not derive an eta ceiling from 1/rho alone", because it
-- "is not a stability governor for the complete physiological dynamics".
--
-- The lab's arithmetic is sound and its verdict is true; the disagreement is
-- over what the number means. Left as a finding for the workbook owner --
-- this build keeps eta_net at 0, which gate eta_net_zero enforces.
CREATE OR REPLACE VIEW engine_internal.eta_net_disagreement AS
    SELECT q.lab_id,
           q.source_row      AS lab_row,
           q.name            AS lab_label,
           q.value_num       AS lab_value,
           p.param_no,
           p.default_or_range AS registry_position,
           i.source_row      AS invariant_row,
           i.value           AS invariant_value,
           i.gate
    FROM engine_internal.verification_lab_quantity q
    JOIN engine_internal.parameter_registry p ON p.symbol = 'eta_net'
    JOIN engine_internal.runtime_invariant i  ON i.gate = 'eta_net_zero'
    WHERE q.name LIKE '%net%(operating gain)%'
      AND q.role = 'INPUT'
      AND q.value_num <> 0;
