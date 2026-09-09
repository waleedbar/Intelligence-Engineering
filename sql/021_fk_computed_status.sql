-- Adds the COMPUTED resolution status.
--
-- '★ Equation Backbone' (migration 020) shows that some FK keys are not
-- values any registry was ever going to carry -- they are the OUTPUT of an
-- equation. B4 gives "CL = CL_renal + CL_hepatic", with B5 and B6 supplying
-- the two terms.
--
-- CL had been reported MISSING_FK on B-002/B-003. That was right about the
-- evidence -- it is in neither authority the row names -- and wrong about
-- the category, which made it look like something to ask the workbook's
-- author for. This status says what it actually is.
--
-- The distinction is kept narrow on purpose. `Q`, in the same FK row, stays
-- MISSING_FK: B2 and B3 consume it and no backbone row defines it. A
-- "computed" bucket that absorbed both would turn a real gap into a
-- reassuring word.

ALTER TABLE engine_internal.eq_param_fk_resolution
    DROP CONSTRAINT IF EXISTS eq_param_fk_status_is_known;

ALTER TABLE engine_internal.eq_param_fk_resolution
    ADD CONSTRAINT eq_param_fk_status_is_known CHECK (status IN (
        'RESOLVED',           -- found in a registry this row declares authoritative
        'RESOLVED_ELSEWHERE', -- found in a parameter registry the row does not name
        'NON_PARAMETER',      -- an FK to an action/rule/model registry
        'COMPUTED',           -- an equation's output; there is no value to look up
        'NOT_LOADED',         -- an authority this build has not imported yet
        'MISSING_FK'          -- every authority IS loaded and the key is in none of them
    ));

ALTER TABLE engine_internal.eq_param_fk_resolution
    DROP CONSTRAINT IF EXISTS eq_param_fk_resolution_location;

-- A COMPUTED key cites the equation that computes it, so it names a place
-- too.
ALTER TABLE engine_internal.eq_param_fk_resolution
    ADD CONSTRAINT eq_param_fk_resolution_location CHECK (
        (status IN ('RESOLVED', 'RESOLVED_ELSEWHERE', 'COMPUTED'))
        = (resolved_in IS NOT NULL)
    );

COMMENT ON COLUMN engine_internal.eq_param_fk_resolution.status IS
    'How the key resolved. COMPUTED means ''★ Equation Backbone'' defines it '
    'as an equation output rather than a stored value -- see '
    'sahacore.data.build_eq_param_fk.COMPUTED_BY_BACKBONE, where every entry '
    'cites the backbone row and formula.';
