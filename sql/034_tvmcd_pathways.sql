-- The fifteen TVMCD pathways, and the map ONB-011 needs.
--
-- Source: v39sEng2.xlsx, sheet 'TVMCD · 15 Pathways Build'.
-- '01_IMPORT_MANIFEST' order 131, role CORE_ENGINE, import YES, backend Yes.
--
--   "TVMCD · 15 Pathways Build — complete server implementation table"
--
-- A CORRECTION THIS TABLE EXISTS TO CARRY. An earlier commit reported the
-- "canonical 15->12 bridge" as absent from the workbook. It is not: the
-- Cluster outputs column here gives two or three clusters for every one of
-- the fifteen pathways. The search that concluded otherwise matched C1..C12
-- and D1..D15, and this sheet writes them zero-padded -- C02, D01 -- so it
-- scored zero on both counts and was passed over. Re-run with padding
-- allowed, it is the only sheet of 205 carrying ten or more of each.
--
-- WHAT THE MAP GIVES IS MEMBERSHIP, NOT WEIGHTS, and three things are still
-- missing before ONB-011 can run:
--
--   * No weights. C12 is fed by eight pathways and C11 by one, and nothing
--     says how several pathway values become one cluster value.
--   * No C01. Membrane Integrity is not an output of any pathway, so a
--     warm-start driven by this map leaves one cluster with nothing.
--   * No hi/lo split. ONB-012 fills xi_hi[163:174] and xi_lo[175:186] --
--     twenty-four slots from fifteen values.
--
-- See docs/parameter-gaps.md.

CREATE TABLE IF NOT EXISTS engine_internal.tvmcd_pathway (
    pathway_id          TEXT PRIMARY KEY,
    source_row          INTEGER NOT NULL UNIQUE,
    biological_meaning  TEXT NOT NULL,

    -- Each pathway carries its own state: logZ_inflam, logZ_AGE, ... in log
    -- coordinates, which is what keeps Z positive (battery test C3).
    state_variable      TEXT NOT NULL,

    ode                 TEXT NOT NULL,
    inputs              TEXT NOT NULL,
    parameters          TEXT NOT NULL,
    integration_cadence TEXT NOT NULL,
    numerical_method    TEXT NOT NULL,
    bounds              TEXT NOT NULL,

    -- "from O·O11 warm-start or zero with prior covariance" -- this column is
    -- what ties the sheet to ONB-011, and it points from O11 to the PATHWAY
    -- state rather than to a cluster. Whether the cluster-outputs column is a
    -- warm-start remapping or a runtime aggregation is not settled by the
    -- sheet; both readings fit what is written.
    initialization      TEXT NOT NULL,

    CONSTRAINT tvmcd_pathway_id_is_zero_padded CHECK (
        pathway_id ~ '^D(0[1-9]|1[0-5])$'
    )
);

-- Pathway -> cluster membership. No weight column, because the sheet gives
-- no weights; adding one with a default would be inventing the combination
-- rule that is the whole difficulty.
CREATE TABLE IF NOT EXISTS engine_internal.tvmcd_cluster_output (
    pathway_id TEXT NOT NULL REFERENCES engine_internal.tvmcd_pathway(pathway_id),
    cluster_id TEXT NOT NULL,

    -- The position in the sheet's own comma-separated list. Kept because the
    -- order may encode dominance -- 'Map · TVMCD→12→Hallmarks' uses a
    -- "Dominant organ node(s)" column in the same style -- and dropping it
    -- would destroy that reading before anyone can ask about it.
    list_position INTEGER NOT NULL,

    PRIMARY KEY (pathway_id, cluster_id),
    CONSTRAINT tvmcd_cluster_is_zero_padded CHECK (
        cluster_id ~ '^C(0[1-9]|1[0-2])$'
    ),
    CONSTRAINT tvmcd_list_position_is_ordinal CHECK (list_position >= 0)
);

-- The clusters this map can and cannot warm-start. Expected to hold exactly
-- C01 until the sheet's author says what feeds it.
CREATE OR REPLACE VIEW engine_internal.clusters_with_no_pathway AS
    SELECT c.cluster_id
    FROM (SELECT 'C' || to_char(n, 'FM00') AS cluster_id
          FROM generate_series(1, 12) AS n) c
    LEFT JOIN engine_internal.tvmcd_cluster_output o
           ON o.cluster_id = c.cluster_id
    WHERE o.cluster_id IS NULL;

-- How unevenly the map spreads: eight pathways into C12, one into C11.
-- Not a defect on its own -- but it is why a combination rule matters, and
-- why an unweighted mean would not be a neutral choice.
CREATE OR REPLACE VIEW engine_internal.cluster_pathway_fan_in AS
    SELECT cluster_id, count(*) AS pathways,
           array_agg(pathway_id ORDER BY pathway_id) AS fed_by
    FROM engine_internal.tvmcd_cluster_output
    GROUP BY cluster_id
    ORDER BY count(*) DESC, cluster_id;
