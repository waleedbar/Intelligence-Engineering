-- Layer M: per-cluster timescales behind the pinned repair constants and
-- the bistability bound. Source: v39sEng2.xlsx, sheet '★ Scarring
-- Bistability Guard', section 3 ("PER-CLUSTER BOUNDS -- assert these at
-- build time"), columns tau_dam / tau_heal / V.
--
-- Section 2 of that sheet pins the cluster-level repair constants from
-- these, with no new measurement required:
--     K_m,k     = theta_elastic,k          (declared: repair half-saturates
--                                           where scarring begins)
--     V_max,k   = theta_elastic,k / tau_heal,k
--     V_k       = 1.443 * tau_dam,k / tau_heal,k   (shipped as v_ratio)

ALTER TABLE layer_m_scarring_params
    ADD COLUMN IF NOT EXISTS tau_dam_days  DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS tau_heal_days DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS v_ratio       DOUBLE PRECISION;

ALTER TABLE layer_m_scarring_params
    ADD CONSTRAINT tau_dam_days_is_positive  CHECK (tau_dam_days  IS NULL OR tau_dam_days  > 0),
    ADD CONSTRAINT tau_heal_days_is_positive CHECK (tau_heal_days IS NULL OR tau_heal_days > 0),
    ADD CONSTRAINT v_ratio_is_positive       CHECK (v_ratio       IS NULL OR v_ratio       > 0);
