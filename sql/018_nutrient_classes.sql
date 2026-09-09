-- Kinetic classes, and which class each of the 81 nutrients belongs to.
--
-- Source: v39sEng2.xlsx, sheet '★ Nutrient Class Registry'.
-- '01_IMPORT_MANIFEST' order 41, role REGISTRY, import YES, backend Yes.
--
-- WHY THIS IS FOUNDATION AND NOT METADATA. The class decides what shape of
-- model a nutrient may be given at all, and the sheet says so in its own
-- 'Modelling consequence' column:
--
--   A  Acute absorbed load        two-compartment PK fully justified
--   B  Homeostatically buffered   "Intake != serum. Serum is tightly clamped
--                                  by renal and hormonal control."
--   C  Storage / body pool        two compartments plus a slow store
--   D  Gut substrate              "Not a plasma concentration."
--   E  Membrane / lipoprotein     two compartments, strongly deferred
--   F  Behavioural exposure       the 24 lifestyle states, not the nutrients
--
-- Layer B applying one kinetic shape to all 81 nutrients would produce a
-- serum calcium that tracks calcium intake, which class B says does not
-- happen in a healthy person. That is a modelling error the code cannot
-- detect on its own, so the constraint is loaded before the layer is
-- written.
--
-- Class F holds zero nutrients, correctly: it describes the lifestyle block
-- of the state vector (indices 187-210), not the nutrient pools.

CREATE TABLE IF NOT EXISTS engine_internal.nutrient_class (
    class_code            TEXT PRIMARY KEY,
    source_row            INTEGER NOT NULL UNIQUE,
    name                  TEXT NOT NULL,
    kinetic_character     TEXT NOT NULL,
    -- What the engine is and is not allowed to do with a nutrient of this
    -- class. Verbatim: the reason is the useful part.
    modelling_consequence TEXT NOT NULL,

    CONSTRAINT nutrient_class_code_is_a_letter CHECK (class_code ~ '^[A-F]$')
);

COMMENT ON TABLE engine_internal.nutrient_class IS
    'The six kinetic classes of ''★ Nutrient Class Registry''. '
    'modelling_consequence is a constraint on Layer A/B, not a description.';

CREATE TABLE IF NOT EXISTS engine_internal.nutrient_class_assignment (
    nutrient_code       TEXT PRIMARY KEY
                        REFERENCES engine_internal.nutrients (code),
    source_row          INTEGER NOT NULL UNIQUE,
    num                 SMALLINT NOT NULL UNIQUE,
    class_code          TEXT NOT NULL
                        REFERENCES engine_internal.nutrient_class (class_code),

    -- What may legitimately be measured to anchor this nutrient's state, and
    -- frequently what may NOT: "NOT serum Ca (PTH-clamped)", "serum Mg
    -- INSENSITIVE", "serum chol is NOT a dietary readout". Kept as written
    -- rather than reduced to a flag.
    observation_anchor  TEXT NOT NULL,

    -- Endogenous synthesis dominates intake for this nutrient, so a dietary
    -- input moves the state far less than the dose suggests.
    endogenous_dominant BOOLEAN NOT NULL DEFAULT FALSE,

    CONSTRAINT nutrient_class_assignment_num_in_range
        CHECK (num BETWEEN 1 AND 81)
);

CREATE INDEX IF NOT EXISTS nutrient_class_assignment_by_class
    ON engine_internal.nutrient_class_assignment (class_code);

COMMENT ON TABLE engine_internal.nutrient_class_assignment IS
    'Each of the 81 nutrients with its kinetic class, observation anchor and '
    'endogenous-dominance flag. The foreign keys make the 81-nutrient '
    'namespace shared with ''P1 Nutrients 81'' rather than merely parallel.';

-- Every nutrient with the constraint that governs it, as one query. This is
-- what a layer reads before choosing a kinetic model for a nutrient.
CREATE OR REPLACE VIEW engine_internal.nutrient_kinetics AS
    SELECT n.num,
           n.code            AS nutrient_code,
           n.name,
           a.class_code,
           c.name            AS class_name,
           c.modelling_consequence,
           a.observation_anchor,
           a.endogenous_dominant
    FROM engine_internal.nutrients n
    JOIN engine_internal.nutrient_class_assignment a ON a.nutrient_code = n.code
    JOIN engine_internal.nutrient_class c            ON c.class_code = a.class_code
    ORDER BY n.num;

COMMENT ON VIEW engine_internal.nutrient_kinetics IS
    'The 81 nutrients joined to the kinetic constraint each is subject to. '
    'Read this before applying a compartment model to a nutrient.';
