-- The equation-to-parameter foreign-key registry.
--
-- Source: v39sEng2.xlsx, sheet 'PARAM · Eq Param FK' -- "equation-to-parameter
-- foreign keys for Python backend". 126 rows.
--
-- This completes build step 2's "current parameter/FK registries". The
-- parameter registry (sql/011) says what each parameter IS; this says which
-- equation CONSUMES it, which registry is authoritative for its value, which
-- backend object carries it, and what rule validates it -- and so it is what
-- makes step 2's acceptance test, "no missing FK", answerable.
--
-- Only 22 of the 126 rows name their keys explicitly; the other 104 say
-- "see formula inputs and named parameter refs". Those are kept with
-- keys_are_explicit = false, because they still declare an authority and a
-- backend object.

-- eq_id is NOT unique: A-001, A-002 and B-001 each appear twice, once in the
-- key-listing block and once in the equation-to-function block, with
-- different backend objects. The sheet's own row number is the identity.
CREATE TABLE IF NOT EXISTS engine_internal.eq_param_fk (
    source_row            INTEGER PRIMARY KEY,
    eq_id                 TEXT NOT NULL,
    keys_are_explicit     BOOLEAN NOT NULL,
    consumes_keys         TEXT[]  NOT NULL DEFAULT '{}',
    authoritative_sheets  TEXT[]  NOT NULL DEFAULT '{}',
    loaded_registries     TEXT[]  NOT NULL DEFAULT '{}',
    all_authorities_loaded BOOLEAN NOT NULL,
    backend_object        TEXT,
    validation_rule       TEXT,

    CONSTRAINT eq_param_fk_explicit_rows_have_keys CHECK (
        NOT keys_are_explicit OR array_length(consumes_keys, 1) >= 1
    ),
    CONSTRAINT eq_param_fk_placeholder_rows_have_none CHECK (
        keys_are_explicit OR consumes_keys = '{}'
    ),
    CONSTRAINT eq_param_fk_declares_an_authority CHECK (
        array_length(authoritative_sheets, 1) >= 1
    )
);

-- One row per (equation, key) with how that key resolves in THIS build.
CREATE TABLE IF NOT EXISTS engine_internal.eq_param_fk_resolution (
    source_row  INTEGER NOT NULL REFERENCES engine_internal.eq_param_fk (source_row),
    eq_id       TEXT NOT NULL,
    param_key   TEXT NOT NULL,
    status      TEXT NOT NULL,
    resolved_in TEXT,

    PRIMARY KEY (source_row, param_key),
    CONSTRAINT eq_param_fk_status_is_known CHECK (status IN (
        'RESOLVED',           -- found in a registry this row declares authoritative
        'RESOLVED_ELSEWHERE', -- an engine-wide constant, found in the parameter registry
        'NON_PARAMETER',      -- an FK to an action/rule/model registry, not a parameter
        'NOT_LOADED',         -- an authority this build has not imported yet
        'MISSING_FK'          -- every authority IS loaded and the key is in none of them
    )),
    -- Only a resolved key names where it resolved.
    CONSTRAINT eq_param_fk_resolution_location CHECK (
        (status IN ('RESOLVED', 'RESOLVED_ELSEWHERE')) = (resolved_in IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS eq_param_fk_resolution_by_status
    ON engine_internal.eq_param_fk_resolution (status);
CREATE INDEX IF NOT EXISTS eq_param_fk_by_eq_id
    ON engine_internal.eq_param_fk (eq_id);

-- Build step 2's acceptance test, as a query. A row here means an equation
-- consumes a key that is in none of the registries its own row declares
-- authoritative, all of which this build has already imported -- so it is a
-- real hole rather than unfinished loading.
CREATE OR REPLACE VIEW engine_internal.missing_fk AS
    SELECT r.eq_id, r.param_key, f.authoritative_sheets,
           f.backend_object, f.validation_rule
    FROM engine_internal.eq_param_fk_resolution r
    JOIN engine_internal.eq_param_fk f USING (source_row)
    WHERE r.status = 'MISSING_FK'
    ORDER BY r.eq_id, r.param_key;

COMMENT ON VIEW engine_internal.missing_fk IS
    'Build step 2 acceptance test "no missing FK". Non-empty means an '
    'equation consumes a parameter key that no loaded authoritative registry '
    'defines. See docs/parameter-gaps.md.';
