-- The 20-parameter registry extension.
--
-- Source: v39sEng2.xlsx, sheet '★ Param Registry +20' -- "★ Parameter
-- Registry — 20 new". '01_IMPORT_MANIFEST' lists it at order 21, import
-- status YES, backend Yes.
--
-- WHY A SECOND TABLE. engine_internal.parameter_registry is keyed on the
-- parameter number 'P1 Parameters 134+' assigns. This sheet has no number
-- column, so merging would mean issuing 20 identifiers the workbook never
-- wrote. The extension keeps its own table keyed on its own source row, and
-- the view at the bottom unions the two for anyone who wants every parameter
-- the engine knows about.
--
-- WHAT IT CLOSES. Six of these twenty were reported by this build as absent
-- from the workbook. They were not absent; they were in a sheet the manifest
-- listed and the import had not reached:
--
--   alpha_scar,k      0.001-0.01 /day   was MISSING_FK on K3-FIX-01
--   beta_autophagy,k  1e-4-1e-3 /day    was MISSING_FK on K3-FIX-01
--   delta_i           0.3/event         was OTHER_LAYER on K3-FIX-04
--   mu_base           0.05              was reported as owed
--   nu_D              0.15              was reported as owed
--   kappa_D           0.1               was reported as owed
--
-- The lesson is recorded in docs/parameter-gaps.md: "this build has not
-- imported it" and "the workbook does not contain it" are different claims,
-- and only the first was ever supportable before the manifest was finished.

CREATE TABLE IF NOT EXISTS engine_internal.parameter_registry_ext20 (
    source_row         INTEGER PRIMARY KEY,

    parameter          TEXT NOT NULL,
    -- Null on four rows. The sheet writes an em-dash for the warning
    -- cool-down, the maximum warnings per week, the F1 suppression threshold
    -- and the Levy window: policy constants named in prose, with no symbol of
    -- their own. Giving them one would invent notation.
    symbol             TEXT,
    unit               TEXT,
    default_or_range   TEXT NOT NULL,
    calibration_source TEXT,

    CONSTRAINT ext20_parameter_is_named CHECK (length(btrim(parameter)) > 0)
);

-- Unique where present, so a symbol resolves to one row.
CREATE UNIQUE INDEX IF NOT EXISTS parameter_registry_ext20_symbol_is_unique
    ON engine_internal.parameter_registry_ext20 (symbol)
    WHERE symbol IS NOT NULL;

COMMENT ON TABLE engine_internal.parameter_registry_ext20 IS
    'The 20 parameters of ''★ Param Registry +20'', which the base registry '
    'does not number. Six of them close gaps this build had reported as '
    'missing from the workbook -- see docs/parameter-gaps.md.';

-- Every parameter the engine knows, from both registries, as one list.
-- `origin` says which sheet a row came from, because the two carry different
-- columns and a caller usually needs to know which it is holding.
CREATE OR REPLACE VIEW engine_internal.parameter_all AS
    SELECT 'P1 Parameters 134+'            AS origin,
           param_no::text                  AS ref,
           symbol,
           units                           AS unit,
           default_or_range,
           layer,
           calibration_method              AS calibration_source
    FROM engine_internal.parameter_registry
    UNION ALL
    SELECT '★ Param Registry +20'          AS origin,
           'row ' || source_row::text      AS ref,
           symbol,
           unit,
           default_or_range,
           NULL                            AS layer,
           calibration_source
    FROM engine_internal.parameter_registry_ext20;

COMMENT ON VIEW engine_internal.parameter_all IS
    'Both parameter registries as one list: 192 numbered rows from '
    '''P1 Parameters 134+'' plus 20 unnumbered rows from '
    '''★ Param Registry +20''. 212 in total.';
