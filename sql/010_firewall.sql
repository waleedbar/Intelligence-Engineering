-- The T-1 firewall, enforced at the database role.
--
-- Source: v39sEng2.xlsx, sheet '08 · Delivery & Firewall', section
-- "DATABASE-ENFORCED FIREWALL CONTRACT — canonical implementation", controls
-- DBF-001 .. DBF-006. The sheet's own statement of WHY it lives here rather
-- than in application code, transcribed verbatim:
--
--     "Copy review can be bypassed by a bug; a database grant cannot. The
--      consumer service account has no read permission on the engine schema,
--      so raw state values, biomarker levels, disease terms and internal
--      mechanism names are physically unreachable from the client --
--      satisfying the six red lines structurally."
--
--     DBF-006 release test: "CI verifies the database grants/RLS plus API
--      schema before release; application-code filtering alone is not
--      accepted."
--
-- This is gate QA-014 (t1_database_role_firewall) in '02_QA_GATES', whose
-- expected status is PASS and whose failure impact is "Raw physiological
-- state or proprietary model leakage".
--
-- SIGDB '13_DB_TABLES' states the same model in two lines:
--     "Two-schema data model: engine_internal for computation;
--      client_render for signed owner-scoped presentation payloads."
--     "app_consumer receives no USAGE/SELECT on engine_internal. All
--      client_render tables are row-owner protected."


-- === DBF-001: the two schemas =============================================
-- Release test: "Both schemas exist; raw posterior/state/pathway tables are
-- confined to engine_internal."

CREATE SCHEMA IF NOT EXISTS engine_internal;
CREATE SCHEMA IF NOT EXISTS client_render;


-- --- confining what is already built --------------------------------------
-- Migrations 002-008 created the Layer 0 registries in `public`, before the
-- two-schema model was implemented. They are computation inputs carrying
-- exactly what DBF-005 forbids crossing the boundary -- absorption kernel
-- shapes, F_max ceilings, damage half-lives, cluster weights, scarring
-- thresholds -- so they belong in engine_internal with everything else the
-- engine computes from.
--
-- Leaving them in `public` would have made the boundary depend on the fact
-- that PostgreSQL grants no table privileges by default, rather than on an
-- explicit control. PUBLIC does hold USAGE on schema public, so that is
-- precisely the "application-code filtering alone" posture DBF-006 rejects.

DO $confine$
DECLARE
    t TEXT;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'nutrients',
        'state_vector',
        'cluster_scoring_params',
        'nutrient_cluster_weights',
        'damage_registry_canonical',
        'layer_m_scarring_params',
        'qssa_atp_complexes'
    ] LOOP
        IF to_regclass('public.' || t) IS NOT NULL THEN
            EXECUTE format('ALTER TABLE public.%I SET SCHEMA engine_internal', t);
        END IF;
    END LOOP;
END
$confine$;

-- `schema_migrations` deliberately stays in public: it holds migration
-- filenames and their timestamps -- no health data, no model parameters, and
-- nothing on DBF-005's forbidden list. It is the migration runner's own
-- bookkeeping, and moving it would make the runner depend on a schema that
-- one of its own migrations creates. It is still explicitly revoked below,
-- so the boundary is stated rather than inherited from a default.


-- === DBF-002: the consumer role ===========================================
-- Canonical SQL from the sheet, with CREATE ROLE made idempotent: roles are
-- cluster-wide rather than per-database, so a second database on the same
-- cluster must not fail on a role that already exists.
--
-- Release test: "Connect as app_consumer: SELECT on engine_internal.* must
-- fail with permission denied; approved client_render read must succeed."

DO $app_consumer$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'app_consumer') THEN
        CREATE ROLE app_consumer NOLOGIN;
    END IF;
END
$app_consumer$;

REVOKE ALL ON ALL TABLES IN SCHEMA engine_internal FROM app_consumer;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA engine_internal FROM app_consumer;
REVOKE USAGE ON SCHEMA engine_internal FROM app_consumer;

-- Defence in depth, beyond the sheet's own text: public keeps only the
-- migration ledger, but the boundary should not rest on that staying true.
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM app_consumer;

GRANT USAGE ON SCHEMA client_render TO app_consumer;
GRANT SELECT ON ALL TABLES IN SCHEMA client_render TO app_consumer;
ALTER DEFAULT PRIVILEGES IN SCHEMA client_render
    GRANT SELECT ON TABLES TO app_consumer;


-- === DBF-003: the trusted sanitizer role ==================================
-- "Only the trusted server-side sanitizer role can transform internal state
-- into client-safe rows."

DO $engine_writer$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'engine_writer') THEN
        CREATE ROLE engine_writer NOLOGIN;
    END IF;
END
$engine_writer$;

GRANT USAGE ON SCHEMA engine_internal, client_render TO engine_writer;
GRANT SELECT ON ALL TABLES IN SCHEMA engine_internal TO engine_writer;
GRANT INSERT, UPDATE ON ALL TABLES IN SCHEMA client_render TO engine_writer;

-- So that a table added by a later build step inherits the contract instead
-- of needing another grant migration -- and so that forgetting one cannot
-- silently widen app_consumer's reach, which it cannot in any case without
-- USAGE on the schema.
ALTER DEFAULT PRIVILEGES IN SCHEMA engine_internal
    GRANT SELECT ON TABLES TO engine_writer;
ALTER DEFAULT PRIVILEGES IN SCHEMA client_render
    GRANT INSERT, UPDATE ON TABLES TO engine_writer;


-- === DBF-004: row-owner protection on client_render =======================
-- The sheet's canonical example is:
--
--     ALTER TABLE client_render.user_scores ENABLE ROW LEVEL SECURITY;
--     CREATE POLICY own_scores ON client_render.user_scores
--         USING (user_id = current_setting('app.user_id')::uuid);
--
-- client_render has no tables yet: its payload tables (api_snapshot,
-- feature_payload, ui_plan and the signal_value_* family in SIGDB
-- '14_DB_COLUMNS') are produced by the projection build step, not this one.
-- Writing the policy for one example table now would protect a table that
-- does not exist and say nothing about the ones that will.
--
-- So what is installed here is the RULE rather than one instance of it --
-- SIGDB '13_DB_TABLES': "All client_render tables are row-owner protected."
-- tests/test_firewall.py asserts that every table in client_render has row
-- level security enabled AND carries at least one policy, and proves the
-- assertion actually bites by creating a deliberately unprotected table and
-- checking it is caught. A future step that adds a payload table without a
-- policy turns CI red on the commit that adds it.

COMMENT ON SCHEMA client_render IS
    'Signed owner-scoped presentation payloads. Every table here MUST enable '
    'row level security and carry an owner policy (08 Delivery & Firewall '
    'DBF-004; SIGDB 13_DB_TABLES). Enforced by tests/test_firewall.py.';

COMMENT ON SCHEMA engine_internal IS
    'Engine computation: raw events, controls, measurements, posterior and '
    'derived state, plus the parameter registries. app_consumer holds no '
    'USAGE here (08 Delivery & Firewall DBF-002).';
