-- Layer M (Durable Memory): per-cluster scarring parameters.
-- Source: v39sEng2.xlsx, sheet 'M-PARAM Registry':
--   rows 47-60 "θ_elastic PER CLUSTER — RATIFIED (founder sign-off)" --
--     damage level above which scarring begins to accumulate (M1's
--     over_k threshold), each row cited to a specific evidence tier and
--     primary source (e.g. DCCT/EDIC, Ristow PNAS 2009, Banse JBMR 2003).
--   rows 30-43 "PER-CLUSTER BISTABILITY CAPS (v35.1)" -- gamma_scar,k
--     (M2's repair-suppression exponent) plus the max alpha_scar/
--     beta_autophagy ratio each cluster must stay under so M1's
--     equilibrium S* never approaches 1 (the v35.4 bistability guard).
--
-- alpha_scar,k and beta_autophagy,k themselves are NOT included here: they
-- are only documented as generic ranges (0.001-0.01 and 6e-4-1.9e-3/day),
-- not ratified per-cluster numbers -- same category of gap as C2/C3's
-- eta_hi,k/theta_hi,k, tracked separately. Callers pass them as plain
-- inputs to sahacore.engine.scarring.

CREATE TABLE IF NOT EXISTS layer_m_scarring_params (
    cluster_id                    TEXT PRIMARY KEY CHECK (cluster_id ~ '^C(1[0-2]|[1-9])$'),
    theta_elastic_au              DOUBLE PRECISION NOT NULL CHECK (theta_elastic_au > 0),
    theta_elastic_evidence_tier   TEXT NOT NULL,
    gamma_scar                    DOUBLE PRECISION NOT NULL CHECK (gamma_scar > 0),
    max_alpha_beta_ratio          DOUBLE PRECISION NOT NULL CHECK (max_alpha_beta_ratio > 0),
    bound_gamma_r                 DOUBLE PRECISION NOT NULL CHECK (bound_gamma_r > 0)
);
