-- What version each registry is at, and what it contained at that version.
--
-- Source: v39sEng2.xlsx, sheet 'IO · Lineage DataMap' -- "database lineage,
-- packet versioning and schemas". Its rows require derived packets to cite
-- the registry they were computed against:
--
--     exposure_state   ... exposure_version, model_shape_version,
--                          nutrient_registry_version, parent_control_version,
--                          ... status, lineage_hash
--     posterior_state  ... posterior_version, state_registry_version,
--                          model_version, parent_exposure_version, ...
--
-- and 'EQ · Canonical Build Rows' row LEDGER-002 makes it general: "Every
-- packet carries parent_packet_ids, parent_versions, lineage_hash,
-- as_of_time, status", cadence "all downstream".
--
-- WHY THIS TABLE HAS TO EXIST BEFORE ANY LAYER RUNS. The version columns were
-- already on checkpoint_state, but nothing in the build DEFINED what a
-- registry version is or what it contained. So if a gamma shape in
-- 'P1 Nutrients 81' changed tomorrow, the 81 rows would simply be overwritten
-- and no packet computed yesterday could say which value it used. Replay would
-- silently mix parameter generations, which is precisely the failure RT-01
-- ("E and M histories both change consistently") and AUD-01 ("query what the
-- engine knew before the late result") exist to catch. A layer that writes a
-- packet citing nutrient_registry_version needs something for that number to
-- point at, and this is it.
--
-- WHAT A VERSION IS. Two things, and the pair is the point:
--
--   version_no    a per-registry counter, so a human can say "nutrients v3".
--   content_hash  the SHA-256 of the loaded rows in canonical JSON, computed
--                 by sahacore.ledger.lineage.lineage_hash -- the same
--                 function the ledger already uses for packet lineage, not a
--                 second hashing scheme invented for registries.
--
-- The counter makes it readable; the hash makes it verifiable. A reload whose
-- content hash is unchanged does NOT create a new version, so re-running the
-- loaders (which CI does on every push) is idempotent, exactly as re-running
-- the migrations is.
--
-- The ACTIVE/SUPERSEDED shape is the one already used by event_quality and
-- controls_u in migration 009, for the same reason: history is kept, and a
-- partial unique index makes `registry` the key of the row consumers resolve.

CREATE TABLE IF NOT EXISTS engine_internal.registry_version (
    -- The table this version describes, schema-qualified as the engine
    -- refers to it: 'engine_internal.nutrients'.
    registry        TEXT        NOT NULL,
    version_no      INTEGER     NOT NULL,

    -- SHA-256 over the canonical JSON of every row loaded, in the loader's
    -- own order. Two loads of identical content produce one version.
    content_hash    TEXT        NOT NULL,
    row_count       INTEGER     NOT NULL,

    -- Which workbook sheet the rows came from, and the JSON the loader read.
    -- A version that cannot name its own source is not auditable.
    source_sheet    TEXT        NOT NULL,
    source_file     TEXT        NOT NULL,

    -- When the engine accepted this content. The registry has no physiological
    -- time of its own -- it is knowledge, not an event -- so it carries the
    -- knowledge clock only, and deliberately not an effective_at.
    knowledge_at    TIMESTAMPTZ NOT NULL DEFAULT now(),

    status          TEXT        NOT NULL DEFAULT 'ACTIVE',

    PRIMARY KEY (registry, version_no),

    CONSTRAINT registry_version_no_is_positive CHECK (version_no >= 1),
    CONSTRAINT registry_version_row_count_is_positive CHECK (row_count > 0),
    -- The same three statuses the ledger's versioned tables use.
    CONSTRAINT registry_version_status_is_known
        CHECK (status IN ('ACTIVE', 'SUPERSEDED', 'INVALIDATED')),
    -- The ledger's own lineage_hash format, algorithm prefix included, so
    -- one digest format is readable across the whole build rather than two.
    CONSTRAINT registry_version_content_hash_is_a_lineage_hash
        CHECK (content_hash ~ '^sha256:[0-9a-f]{64}$'),
    -- Identical content must not appear twice under one registry: that is a
    -- version number handed out for nothing, and it would make "did this
    -- change?" unanswerable by comparing hashes.
    CONSTRAINT registry_version_content_is_unique_per_registry
        UNIQUE (registry, content_hash)
);

-- Exactly one ACTIVE version per registry. This is the row every packet's
-- *_registry_version resolves to, and the reason a consumer never has to
-- guess which of several loads is current.
CREATE UNIQUE INDEX IF NOT EXISTS registry_version_one_active
    ON engine_internal.registry_version (registry)
    WHERE status = 'ACTIVE';

COMMENT ON TABLE engine_internal.registry_version IS
    'What version each registry is at and what it contained. Required by '
    '''IO · Lineage DataMap'': exposure_state cites nutrient_registry_version '
    'and posterior_state cites state_registry_version, so those numbers need '
    'a definition that outlives a reload. Written by '
    'sahacore.registry_version.record_version, which every loader calls.';

-- The current state of every registry, as one query: what a packet being
-- written now should cite, and what an operator should see after a load.
CREATE OR REPLACE VIEW engine_internal.registry_current AS
    SELECT registry, version_no, content_hash, row_count,
           source_sheet, source_file, knowledge_at
    FROM engine_internal.registry_version
    WHERE status = 'ACTIVE'
    ORDER BY registry;

COMMENT ON VIEW engine_internal.registry_current IS
    'The ACTIVE version of every registry. A packet citing '
    'nutrient_registry_version resolves it here.';
