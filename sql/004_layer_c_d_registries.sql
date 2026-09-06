-- Layer C (damage accumulation) and Layer D (scoring) registries.
-- Source: v39sEng2.xlsx, sheets '★ Damage Registry — Canonical' (108 rows,
-- explicitly supersedes 'P1 Clusters 81x12' Section C), 'REG · Nutrient×Cluster
-- Long' (357 rows), and 'P1 Clusters 81x12' Section B (12 cluster-level
-- scoring params). All three verified column-by-column against source before
-- writing this schema: nutrient_cluster_weights sums to exactly 1.0 per
-- cluster; damage_registry_canonical's weight_pct sums to exactly 100 per
-- cluster; both use only nutrient codes that exist in `nutrients`.

CREATE TABLE IF NOT EXISTS cluster_scoring_params (
    cluster_id    TEXT PRIMARY KEY CHECK (cluster_id ~ '^C(1[0-2]|[1-9])$'),
    a_k           DOUBLE PRECISION NOT NULL,
    b_k           DOUBLE PRECISION NOT NULL,
    tau_dam_days  DOUBLE PRECISION NOT NULL CHECK (tau_dam_days > 0),
    rho_k         DOUBLE PRECISION NOT NULL CHECK (rho_k BETWEEN 0 AND 1)
);

CREATE TABLE IF NOT EXISTS nutrient_cluster_weights (
    nutrient_id  TEXT NOT NULL REFERENCES nutrients(code),
    cluster_id   TEXT NOT NULL CHECK (cluster_id ~ '^C(1[0-2]|[1-9])$'),
    weight       DOUBLE PRECISION NOT NULL CHECK (weight > 0 AND weight <= 1),
    PRIMARY KEY (nutrient_id, cluster_id)
);

CREATE INDEX IF NOT EXISTS idx_nutrient_cluster_weights_cluster
    ON nutrient_cluster_weights (cluster_id);

-- Both damage sides (hi/lo) are carried on one row per (cluster, nutrient),
-- matching the source sheet's own layout; theta_hi/theta_lo are NULL for
-- clusters C7 and C9 only (Methylation and Neuro-Hormonal), whose thresholds
-- are derived from a dynamic mechanistic sub-model rather than a fixed
-- constant -- per the source sheet's own note, not a data gap.
CREATE TABLE IF NOT EXISTS damage_registry_canonical (
    cluster_id       TEXT NOT NULL CHECK (cluster_id ~ '^C(1[0-2]|[1-9])$'),
    nutrient_id      TEXT NOT NULL REFERENCES nutrients(code),
    weight_pct       DOUBLE PRECISION NOT NULL CHECK (weight_pct > 0 AND weight_pct <= 100),
    tau_damage_days  DOUBLE PRECISION NOT NULL CHECK (tau_damage_days > 0),
    tau_heal_days    DOUBLE PRECISION NOT NULL CHECK (tau_heal_days > 0),
    eta_hi           DOUBLE PRECISION NOT NULL CHECK (eta_hi >= 0),
    eta_lo           DOUBLE PRECISION NOT NULL CHECK (eta_lo >= 0),
    theta_hi         DOUBLE PRECISION CHECK (theta_hi IS NULL OR theta_hi >= 0),
    theta_lo         DOUBLE PRECISION CHECK (theta_lo IS NULL OR theta_lo >= 0),
    threshold_unit   TEXT NOT NULL,
    note             TEXT,
    PRIMARY KEY (cluster_id, nutrient_id),
    CONSTRAINT theta_hi_lo_both_or_neither CHECK (
        (theta_hi IS NULL) = (theta_lo IS NULL)
    )
);
