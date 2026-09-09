-- The two hardest builds, and the prerequisite that is a claim about today.
--
-- Source: v39sEng2.xlsx, sheet '★ Scoped Builds — LTMLE Bandit'.
-- '01_IMPORT_MANIFEST' order 6, role BUILD_CONTRACT, import YES, backend Yes.
--
--   "★ SCOPED BUILDS — LTMLE (Layer G) & Conservative Bandit (Layer H)"
--   "The two hardest, highest-stakes builds in the engine."
--
-- Layers G and H are build-flow phases 7 and 8. Neither can be built for a
-- long time, and this is imported anyway, for one sentence:
--
--   SHARED PREREQUISITE 1 · Historical outcome log
--   "Both learn from a per-user longitudinal record the ONLINE engine must
--    already be writing"
--
-- and its restatement as the eighth open founder decision:
--
--   "BOTH · confirm the historical outcome log is being written"
--   "Prerequisite -- nothing offline can start without it"
--
-- ALREADY WRITING IS A CLAIM ABOUT TODAY. A log that starts at phase 7 gives
-- Layers G and H no history to learn from, and the months not recorded are
-- not recoverable by any amount of later engineering. So the prerequisite
-- belongs to whoever is building the ledger -- which is this build, now.
--
-- Its status here is MISSING, and deliberately not fixed by inventing
-- tables: this build writes exactly what '★ Build Guide Python' step 1
-- specifies. See docs/parameter-gaps.md.

CREATE TABLE IF NOT EXISTS engine_internal.scoped_build_prerequisite (
    number       TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    source_row   INTEGER NOT NULL UNIQUE,
    detail       TEXT NOT NULL,

    -- THIS BUILD'S columns, as in validation_test.coverage.
    --   IN_PLACE            something in this repo satisfies it, named.
    --   MISSING             nothing does, and the note says what is absent.
    --   NOT_APPLICABLE_YET  it governs something that does not exist.
    status       TEXT NOT NULL,
    satisfied_by TEXT,
    status_note  TEXT NOT NULL,

    CONSTRAINT scoped_prerequisite_status_is_known CHECK (
        status IN ('IN_PLACE', 'MISSING', 'NOT_APPLICABLE_YET')
    ),
    -- Only a satisfied prerequisite may name something, and it must.
    CONSTRAINT scoped_prerequisite_in_place_names_its_evidence CHECK (
        (status = 'IN_PLACE') = (satisfied_by IS NOT NULL)
    )
);

CREATE TABLE IF NOT EXISTS engine_internal.scoped_build (
    item_id    TEXT PRIMARY KEY,
    source_row INTEGER NOT NULL UNIQUE,
    title      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS engine_internal.scoped_build_attribute (
    item_id    TEXT NOT NULL REFERENCES engine_internal.scoped_build(item_id),
    name       TEXT NOT NULL,
    source_row INTEGER NOT NULL,
    value      TEXT NOT NULL,

    PRIMARY KEY (item_id, name)
);

-- The sheet interleaves warnings among the contract rows -- item 2's is
-- "⚠ THE HARD PART — REWARD DESIGN (founder decision)". Kept beside the
-- contract rather than dropped for not fitting the two-column shape.
CREATE TABLE IF NOT EXISTS engine_internal.scoped_build_note (
    item_id    TEXT NOT NULL REFERENCES engine_internal.scoped_build(item_id),
    source_row INTEGER NOT NULL,
    text       TEXT NOT NULL,

    PRIMARY KEY (item_id, source_row)
);

-- "OPEN FOUNDER DECISIONS — required BEFORE code starts". Eight of them,
-- each with the sheet's own statement of what it determines. None is
-- answered here; answering one would be inventing product policy.
CREATE TABLE IF NOT EXISTS engine_internal.founder_decision (
    number          INTEGER PRIMARY KEY,
    source_row      INTEGER NOT NULL UNIQUE,
    decision        TEXT NOT NULL,
    why_it_matters  TEXT NOT NULL,

    CONSTRAINT founder_decision_is_numbered_from_one CHECK (number >= 1)
);

-- What blocks both scoped builds today. Expected to hold exactly one row --
-- the outcome log -- until the ledger writes it.
CREATE OR REPLACE VIEW engine_internal.unmet_scoped_prerequisites AS
    SELECT number, name, detail, status_note
    FROM engine_internal.scoped_build_prerequisite
    WHERE status = 'MISSING'
    ORDER BY number;
