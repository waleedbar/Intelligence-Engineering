-- client_render's payload tables, and the row-owner protection they carry.
--
-- Source: SIGDB SIG-DB-v1.1, sheets 13_DB_TABLES (TBL021-TBL033),
-- 14_DB_COLUMNS (the column dictionary) and 16_ENUMS (the public codebook).
--
-- This is the table set migration 010 deliberately did not write. Its DBF-004
-- section says so in as many words: "client_render has no tables yet ... So
-- what is installed here is the RULE rather than one instance of it." The
-- rule has been enforced since -- tests/test_firewall.py fails any
-- client_render table lacking RLS or a policy, and proves the guard bites by
-- creating an unprotected probe. This migration is the first real instance.
--
-- THE CANONICAL RLS RULE, transcribed from 13_DB_TABLES and identical on all
-- 33 declared tables:
--
--     "user_id = authenticated subject; service bypass separated"
--
-- Both halves are implemented literally. The subject policy is scoped TO
-- app_consumer and matches on the authenticated subject; the service's
-- access is a SEPARATE policy scoped TO engine_writer, rather than the same
-- policy widened with an OR. A widened policy is how a service predicate
-- becomes reachable by a client role after one careless edit.
--
-- WHAT IS BUILT AND WHAT IS NOT. 13_DB_TABLES declares thirteen
-- client_render tables. 14_DB_COLUMNS gives columns for SEVEN of them, and
-- those seven are built here, transcribed. The other six -- signal_availability,
-- science_packet, share_receipt, consent_receipt, notification_settings and
-- audit_receipt_public -- are named with a purpose, a retention and an access
-- class, and have no column dictionary anywhere in the workbook. A table name
-- is not a schema, and inventing columns for a payload that crosses the
-- client boundary is the one place guessing is least acceptable. Recorded in
-- docs/parameter-gaps.md.
--
-- WHAT IS DELIBERATELY EMPTY. All seven ship with zero rows. They are filled
-- by the projection step, which requires Layers A-H to have computed
-- something, and nothing in this build computes yet. An empty table with a
-- correct policy is the honest state; a table populated with placeholder
-- scores would be a fabricated health value crossing the firewall, which
-- FW08 (FAIL_CLOSED) exists to prevent.


-- === the authenticated subject ============================================
-- The single point where "who is asking" enters the database.
--
-- Reads a session GUC rather than a table, because the subject is per
-- connection, not per row. `current_setting(..., true)` returns NULL when
-- unset rather than raising, and NULL is the fail-closed answer: every
-- policy below compares user_id against it, and `user_id = NULL` is never
-- true, so a connection that never declared a subject sees nothing at all.
--
-- THIS IS THE SUPABASE SWAP POINT. Under Supabase the body becomes
-- `SELECT auth.uid()` and nothing else in this migration changes. The
-- contract's M1 names Supabase; this build runs on stock PostgreSQL, so the
-- indirection is here to make that a one-line substitution rather than a
-- rewrite of thirteen policies.
CREATE OR REPLACE FUNCTION client_render.current_subject() RETURNS uuid
    LANGUAGE sql
    STABLE
    -- Not SECURITY DEFINER: it reads a session setting, owns nothing, and
    -- must run with the caller's own rights.
AS $$
    SELECT nullif(current_setting('sahacore.subject_id', true), '')::uuid
$$;

COMMENT ON FUNCTION client_render.current_subject() IS
    'The authenticated subject for this connection, from the sahacore.subject_id '
    'GUC. NULL when unset, which makes every owner policy match no rows. '
    'Under Supabase this becomes auth.uid().';


-- === TBL021 · api_snapshot ================================================
-- "signed per-product response snapshot". The parent every other payload
-- table hangs from, and the only one carrying user_id directly.
CREATE TABLE IF NOT EXISTS client_render.api_snapshot (
    snapshot_id         UUID PRIMARY KEY,
    user_id             UUID NOT NULL,
    product             TEXT NOT NULL,
    schema_version      TEXT NOT NULL,
    -- "Serializer-allowlisted DTO". The allowlist is enforced by the
    -- serializer and by 04_API_ALLOWLIST, not by this column's type.
    payload_json        JSONB NOT NULL,
    generated_at        TIMESTAMPTZ NOT NULL,
    data_through        TIMESTAMPTZ NOT NULL,
    expires_at          TIMESTAMPTZ NOT NULL,
    availability_status TEXT NOT NULL,
    confidence_tier     TEXT NOT NULL,
    lineage_ref         UUID NOT NULL,
    key_id              TEXT NOT NULL,
    payload_hash        TEXT NOT NULL UNIQUE,
    signature           TEXT NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT api_snapshot_product_is_known CHECK (
        product IN ('TWIN', 'PULSE', 'ATLAS', 'PLAN', 'CORE')
    ),
    -- ENUM003. "Value omitted/null when unavailable."
    CONSTRAINT api_snapshot_availability_is_known CHECK (
        availability_status IN ('available', 'partial', 'unavailable', 'suppressed')
    ),
    -- ENUM004. "Public ordinal only; covariance hidden."
    CONSTRAINT api_snapshot_confidence_is_known CHECK (
        confidence_tier IN ('high', 'moderate', 'low', 'not_available')
    ),
    -- A snapshot cannot include data from after it was computed, and cannot
    -- expire before it was generated.
    CONSTRAINT api_snapshot_data_through_precedes_generation CHECK (
        data_through <= generated_at
    ),
    CONSTRAINT api_snapshot_expires_after_generation CHECK (
        expires_at > generated_at
    )
);

CREATE INDEX IF NOT EXISTS api_snapshot_user_product
    ON client_render.api_snapshot (user_id, product, generated_at DESC);
CREATE INDEX IF NOT EXISTS api_snapshot_expiry
    ON client_render.api_snapshot (expires_at);

COMMENT ON TABLE client_render.api_snapshot IS
    'SIGDB TBL021. Signed per-product response snapshot; the owner root for '
    'every other client_render payload table.';


-- === TBL022 · signal_value_scalar =========================================
CREATE TABLE IF NOT EXISTS client_render.signal_value_scalar (
    snapshot_id   UUID NOT NULL
        REFERENCES client_render.api_snapshot (snapshot_id) ON DELETE CASCADE,
    signal_id     TEXT NOT NULL,
    number_value  DOUBLE PRECISION,
    text_value    TEXT,
    boolean_value BOOLEAN,
    unit_code     TEXT,
    value_status  TEXT NOT NULL,
    quality_flags TEXT[] NOT NULL DEFAULT '{}',

    PRIMARY KEY (snapshot_id, signal_id),

    -- ENUM003.
    CONSTRAINT signal_value_scalar_status_is_known CHECK (
        value_status IN ('available', 'partial', 'unavailable', 'suppressed')
    ),
    -- "Value omitted/null when unavailable" -- and the converse: a row that
    -- says `available` and carries no value is the fabricated-availability
    -- case FW08 forbids.
    CONSTRAINT signal_value_scalar_available_carries_a_value CHECK (
        value_status <> 'available'
        OR number_value IS NOT NULL
        OR text_value IS NOT NULL
        OR boolean_value IS NOT NULL
    ),
    CONSTRAINT signal_value_scalar_unavailable_carries_none CHECK (
        value_status = 'available'
        OR (number_value IS NULL AND text_value IS NULL AND boolean_value IS NULL)
    )
);


-- === TBL023 · signal_value_vector =========================================
CREATE TABLE IF NOT EXISTS client_render.signal_value_vector (
    vector_id      UUID PRIMARY KEY,
    snapshot_id    UUID NOT NULL
        REFERENCES client_render.api_snapshot (snapshot_id) ON DELETE CASCADE,
    signal_id      TEXT NOT NULL,
    axis_id        TEXT NOT NULL,
    -- "Exact cardinality". QA023 requires vector arrays to return stable
    -- member ids; a declared count is what makes a short vector detectable.
    expected_count INTEGER NOT NULL,
    unit_code      TEXT,
    order_version  TEXT NOT NULL,

    CONSTRAINT signal_value_vector_count_is_positive CHECK (expected_count > 0)
);

CREATE INDEX IF NOT EXISTS signal_value_vector_snapshot
    ON client_render.signal_value_vector (snapshot_id, signal_id);


-- === TBL024 · signal_vector_member ========================================
CREATE TABLE IF NOT EXISTS client_render.signal_vector_member (
    vector_id           UUID NOT NULL
        REFERENCES client_render.signal_value_vector (vector_id) ON DELETE CASCADE,
    member_order        SMALLINT NOT NULL,
    member_id           TEXT NOT NULL,
    number_value        DOUBLE PRECISION,
    band_token          TEXT,
    availability_status TEXT NOT NULL,

    CONSTRAINT signal_vector_member_order_is_unique UNIQUE (vector_id, member_order),
    CONSTRAINT signal_vector_member_id_is_unique UNIQUE (vector_id, member_id),
    -- "Stable 1-based order".
    CONSTRAINT signal_vector_member_order_is_one_based CHECK (member_order >= 1),
    -- ENUM001. Higher is better: Optimal >=80, Build 60-79, Focus 40-59,
    -- Reach Out <40.
    CONSTRAINT signal_vector_member_band_is_known CHECK (
        band_token IS NULL
        OR band_token IN ('optimal', 'build', 'focus', 'reach_out')
    ),
    CONSTRAINT signal_vector_member_availability_is_known CHECK (
        availability_status IN ('available', 'partial', 'unavailable', 'suppressed')
    )
);


-- === TBL025 · signal_time_series_point ====================================
CREATE TABLE IF NOT EXISTS client_render.signal_time_series_point (
    series_id        UUID NOT NULL,
    snapshot_id      UUID NOT NULL
        REFERENCES client_render.api_snapshot (snapshot_id) ON DELETE CASCADE,
    signal_id        TEXT NOT NULL,
    -- DEC09: "Every point has timestamp". GAP002 was a curve payload with y
    -- values and no x coordinate; this column is that gap closed.
    observed_at      TIMESTAMPTZ NOT NULL,
    elapsed_seconds  INTEGER,
    member_id        TEXT,
    number_value     DOUBLE PRECISION,
    unit_code        TEXT,
    quality_flags    TEXT[] NOT NULL DEFAULT '{}',
    sequence_no      INTEGER NOT NULL,

    CONSTRAINT signal_time_series_point_sequence_is_unique
        UNIQUE (series_id, sequence_no),
    CONSTRAINT signal_time_series_point_sequence_is_positive CHECK (sequence_no >= 1)
);

CREATE INDEX IF NOT EXISTS signal_time_series_point_series
    ON client_render.signal_time_series_point (series_id, sequence_no);
CREATE INDEX IF NOT EXISTS signal_time_series_point_snapshot
    ON client_render.signal_time_series_point (snapshot_id, signal_id);


-- === TBL027 · feature_payload =============================================
CREATE TABLE IF NOT EXISTS client_render.feature_payload (
    payload_id        UUID PRIMARY KEY,
    snapshot_id       UUID NOT NULL
        REFERENCES client_render.api_snapshot (snapshot_id) ON DELETE CASCADE,
    product           TEXT NOT NULL,
    feature_id        TEXT NOT NULL,
    dto_json          JSONB NOT NULL,
    catalog_version   TEXT NOT NULL,
    copy_version      TEXT,
    -- "Required for action-bearing DTOs". FW06 VETO_FIRST and QA020: an
    -- action-bearing payload with no safety receipt is an action served
    -- without a safety evaluation. Which DTOs are action-bearing is the
    -- serializer's knowledge, so the column is nullable here and the rule
    -- is enforced where that is known.
    safety_receipt_id UUID,
    generated_at      TIMESTAMPTZ NOT NULL,
    expires_at        TIMESTAMPTZ NOT NULL,

    CONSTRAINT feature_payload_product_is_known CHECK (
        product IN ('TWIN', 'PULSE', 'ATLAS', 'PLAN', 'CORE')
    ),
    CONSTRAINT feature_payload_expires_after_generation CHECK (
        expires_at > generated_at
    )
);

CREATE INDEX IF NOT EXISTS feature_payload_snapshot
    ON client_render.feature_payload (snapshot_id, product, feature_id);


-- === TBL028 · ui_plan =====================================================
-- 13_DB_TABLES notes: "Replaces undeclared ui_plan and deprecated ui_132
-- references" -- GAP045 and GAP061.
CREATE TABLE IF NOT EXISTS client_render.ui_plan (
    plan_payload_id   UUID PRIMARY KEY,
    snapshot_id       UUID NOT NULL
        REFERENCES client_render.api_snapshot (snapshot_id) ON DELETE CASCADE,
    decision_ids      UUID[] NOT NULL,
    -- ENUM006. "Named capacity state, not raw Phi" -- the raw capacity
    -- number stays server-side.
    capacity_token    TEXT NOT NULL,
    items_json        JSONB NOT NULL,
    -- NOT NULL here, unlike feature_payload: a plan is action-bearing by
    -- definition, so FW06 admits no plan without its VETO-first proof.
    safety_receipt_id UUID NOT NULL,
    copy_version      TEXT NOT NULL,
    generated_at      TIMESTAMPTZ NOT NULL,
    expires_at        TIMESTAMPTZ NOT NULL,

    CONSTRAINT ui_plan_capacity_is_known CHECK (
        capacity_token IN ('depleted', 'steady', 'ready')
    ),
    CONSTRAINT ui_plan_expires_after_generation CHECK (expires_at > generated_at)
);


-- === DBF-004 · row-owner protection =======================================
-- "user_id = authenticated subject; service bypass separated"
--
-- OWNERSHIP IS A CHAIN, AND IT DOES NOT NEED REPEATING. Only api_snapshot
-- carries user_id; the other six reach it through snapshot_id (or through
-- vector_id then snapshot_id). Their subject policy asks only whether the
-- parent row is visible -- and because the parent is itself RLS-protected,
-- that subquery is filtered by the SAME policy under the SAME role. So the
-- subject test, and the expiry test with it, is written once and inherited.
-- Copying `user_id = current_subject()` into seven policies would be seven
-- places for it to drift.
--
-- EXPIRY IS PART OF THE CLIENT PREDICATE. 14_DB_COLUMNS calls expires_at a
-- "Hard client expiry". Enforcing it in the policy rather than in the
-- serializer means a stale payload is unreadable by the client even if a
-- query forgets the filter, while engine_writer still sees it to replace or
-- audit it -- which is what "bounded audit" retention needs.

-- api_snapshot: the root.
ALTER TABLE client_render.api_snapshot ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS api_snapshot_subject ON client_render.api_snapshot;
CREATE POLICY api_snapshot_subject ON client_render.api_snapshot
    FOR SELECT TO app_consumer
    USING (user_id = client_render.current_subject() AND expires_at > now());

DROP POLICY IF EXISTS api_snapshot_service ON client_render.api_snapshot;
CREATE POLICY api_snapshot_service ON client_render.api_snapshot
    FOR ALL TO engine_writer
    USING (true) WITH CHECK (true);

-- The six children, each visible exactly when its parent is.
DO $children$
DECLARE
    spec RECORD;
BEGIN
    FOR spec IN
        SELECT * FROM (VALUES
            ('signal_value_scalar',
             'EXISTS (SELECT 1 FROM client_render.api_snapshot p'
             ' WHERE p.snapshot_id = signal_value_scalar.snapshot_id)'),
            ('signal_value_vector',
             'EXISTS (SELECT 1 FROM client_render.api_snapshot p'
             ' WHERE p.snapshot_id = signal_value_vector.snapshot_id)'),
            ('signal_vector_member',
             'EXISTS (SELECT 1 FROM client_render.signal_value_vector v'
             ' WHERE v.vector_id = signal_vector_member.vector_id)'),
            ('signal_time_series_point',
             'EXISTS (SELECT 1 FROM client_render.api_snapshot p'
             ' WHERE p.snapshot_id = signal_time_series_point.snapshot_id)'),
            ('feature_payload',
             'EXISTS (SELECT 1 FROM client_render.api_snapshot p'
             ' WHERE p.snapshot_id = feature_payload.snapshot_id)'),
            ('ui_plan',
             'EXISTS (SELECT 1 FROM client_render.api_snapshot p'
             ' WHERE p.snapshot_id = ui_plan.snapshot_id)')
        ) AS t(table_name, owner_predicate)
    LOOP
        EXECUTE format(
            'ALTER TABLE client_render.%I ENABLE ROW LEVEL SECURITY',
            spec.table_name);

        EXECUTE format(
            'DROP POLICY IF EXISTS %I ON client_render.%I',
            spec.table_name || '_subject', spec.table_name);
        EXECUTE format(
            'CREATE POLICY %I ON client_render.%I FOR SELECT TO app_consumer'
            ' USING (%s)',
            spec.table_name || '_subject', spec.table_name,
            spec.owner_predicate);

        EXECUTE format(
            'DROP POLICY IF EXISTS %I ON client_render.%I',
            spec.table_name || '_service', spec.table_name);
        EXECUTE format(
            'CREATE POLICY %I ON client_render.%I FOR ALL TO engine_writer'
            ' USING (true) WITH CHECK (true)',
            spec.table_name || '_service', spec.table_name);
    END LOOP;
END
$children$;


-- === grants ===============================================================
-- Migration 010 granted app_consumer SELECT on all client_render tables and
-- set default privileges, and engine_writer INSERT/UPDATE.
--
-- TWO THINGS IT DID NOT GRANT, both found by probing the finished tables
-- rather than by reading the migration:
--
--   SELECT to engine_writer.  It was granted SELECT on engine_internal and
--   INSERT/UPDATE here, never SELECT here. Its service policy reads
--   `FOR ALL ... USING (true)`, which looks like full access and is not: a
--   POLICY FILTERS A GRANT, IT NEVER CREATES ONE. So the projection step
--   would have written a snapshot and then failed on its first read of it,
--   and the policy would have looked innocent. Upserts, expiry sweeps and
--   audit all read.
--
--   DELETE to engine_writer.  "expires_at + bounded audit" retention means
--   something eventually removes expired rows.
GRANT SELECT ON ALL TABLES IN SCHEMA client_render TO app_consumer;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA client_render TO engine_writer;
ALTER DEFAULT PRIVILEGES IN SCHEMA client_render
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO engine_writer;

-- app_consumer must be able to ask who it is; without EXECUTE the policies
-- it is subject to would error rather than filter.
GRANT EXECUTE ON FUNCTION client_render.current_subject() TO app_consumer, engine_writer;


-- === what a reader should be able to ask ==================================
-- Every client_render table, with its protection state. Any row reading
-- false in either column is a boundary defect; tests/test_firewall.py
-- already fails on one.
CREATE OR REPLACE VIEW client_render.table_protection AS
    SELECT c.relname AS table_name,
           c.relrowsecurity AS rls_enabled,
           count(p.polname) FILTER (WHERE p.polname IS NOT NULL) AS policies,
           count(p.polname) FILTER (
               WHERE 'app_consumer' = ANY (
                   SELECT rolname FROM pg_roles WHERE oid = ANY (p.polroles))
           ) AS subject_policies,
           count(p.polname) FILTER (
               WHERE 'engine_writer' = ANY (
                   SELECT rolname FROM pg_roles WHERE oid = ANY (p.polroles))
           ) AS service_policies
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    LEFT JOIN pg_policy p ON p.polrelid = c.oid
    WHERE n.nspname = 'client_render' AND c.relkind = 'r'
    GROUP BY c.relname, c.relrowsecurity
    ORDER BY c.relname;

COMMENT ON VIEW client_render.table_protection IS
    'Every client_render table with its RLS state and the count of subject '
    'and service policies. Both policy counts must be >= 1 on every row: '
    'the canonical rule is "user_id = authenticated subject; service bypass '
    'separated", and a table with only one of the two has either no client '
    'access or no separation.';
