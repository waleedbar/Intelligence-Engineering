-- Layer 0: canonical 219-state vector layout (the structural definition of
-- what each of the filter's 219 coordinates IS, not yet the filter/estimation
-- engine itself). Source of truth: Dr. Ali's v39sEng2 workbook, sheet
-- '★ State Vector v33 (219)' section 1 (BLOCK MAP), cross-checked against
-- 'P1 Variables 219' and 'K3 · Mechanistic Modules'.
--
-- Requires sql/002_layer0_registries.sql to already be applied (nutrients FK).

CREATE TABLE IF NOT EXISTS state_vector (
    idx            SMALLINT PRIMARY KEY CHECK (idx BETWEEN 1 AND 219),
    block          TEXT NOT NULL CHECK (block IN (
                       'C_fast', 'C_slow', 'xi_hi', 'xi_lo', 'lifestyle',
                       'N1', 'N2', 'N3', 'N4', 'N5'
                   )),
    symbol         TEXT NOT NULL,
    name           TEXT NOT NULL,
    unit           TEXT,
    is_nonlinear   BOOLEAN NOT NULL,

    -- populated only for C_fast/C_slow rows (one of the 81 canonical nutrients)
    nutrient_code  TEXT REFERENCES nutrients(code),
    -- populated only for xi_hi/xi_lo rows (one of the 12 process clusters, C1-C12)
    cluster_id     TEXT,
    side           TEXT CHECK (side IN ('hi', 'lo')),

    -- each block occupies a fixed, contiguous index range per the block map
    CONSTRAINT block_index_range CHECK (
        (block = 'C_fast'    AND idx BETWEEN   1 AND  81) OR
        (block = 'C_slow'    AND idx BETWEEN  82 AND 162) OR
        (block = 'xi_hi'     AND idx BETWEEN 163 AND 174) OR
        (block = 'xi_lo'     AND idx BETWEEN 175 AND 186) OR
        (block = 'lifestyle' AND idx BETWEEN 187 AND 210) OR
        (block = 'N1'        AND idx BETWEEN 211 AND 213) OR
        (block = 'N2'        AND idx =  214) OR
        (block = 'N3'        AND idx BETWEEN 215 AND 216) OR
        (block = 'N4'        AND idx BETWEEN 217 AND 218) OR
        (block = 'N5'        AND idx =  219)
    ),
    CONSTRAINT nutrient_code_only_on_exposure_blocks CHECK (
        (block IN ('C_fast', 'C_slow')) = (nutrient_code IS NOT NULL)
    ),
    CONSTRAINT cluster_side_only_on_damage_blocks CHECK (
        (block IN ('xi_hi', 'xi_lo')) = (cluster_id IS NOT NULL AND side IS NOT NULL)
    ),
    CONSTRAINT side_matches_block CHECK (
        (block <> 'xi_hi' OR side = 'hi') AND
        (block <> 'xi_lo' OR side = 'lo')
    ),
    CONSTRAINT unique_nutrient_per_block UNIQUE (block, nutrient_code),
    CONSTRAINT unique_cluster_side_per_block UNIQUE (block, cluster_id, side)
);

CREATE INDEX IF NOT EXISTS idx_state_vector_block ON state_vector (block);
CREATE INDEX IF NOT EXISTS idx_state_vector_nutrient_code ON state_vector (nutrient_code);
