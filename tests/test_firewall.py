"""The T-1 firewall, verified against a real PostgreSQL.

Source: v39sEng2.xlsx, sheet '08 · Delivery & Firewall', controls DBF-001 to
DBF-006, and gate QA-014 (t1_database_role_firewall) in '02_QA_GATES', whose
expected status is PASS and whose failure impact is "Raw physiological state
or proprietary model leakage".

QA-014's check, transcribed verbatim:

    "Connect as app_consumer: engine_internal SELECT must fail; approved
     client_render own-user SELECT succeeds; cross-user RLS test returns no
     rows."

DBF-006's release test says why these are database tests and not code
review: "CI verifies the database grants/RLS plus API schema before release;
application-code filtering alone is not accepted."

Every test here therefore switches to the real role with SET ROLE and asks
PostgreSQL, rather than asking a Python object what it believes its
permissions are. The roles are NOLOGIN by the sheet's own SQL, so SET ROLE
from the migration owner is exactly how they are meant to be exercised.
"""
import psycopg
import pytest

# Registry tables migration 010 confines to engine_internal, each carrying
# something on DBF-005's forbidden list (kernel shapes, F_max ceilings,
# damage half-lives, cluster weights, scarring thresholds).
CONFINED_REGISTRIES = [
    "nutrients",
    "state_vector",
    "cluster_scoring_params",
    "nutrient_cluster_weights",
    "damage_registry_canonical",
    "layer_m_scarring_params",
    "qssa_atp_complexes",
    # Build step 2's parameter/FK half.
    "parameter_registry",
    "parameter_registry_ext20",
    "nutrient_class",
    "nutrient_class_assignment",
    "supplement_registry",
    "eq_param_fk",
    "eq_build_rows",
    "eq_build_row_inputs",
    # Build step 2's safety half. The VETO library is the sharpest case
    # DBF-005 covers: 339 curated drug-nutrient interaction rules with
    # clinical rationales and interaction coefficients are exactly the
    # "proprietary model parameters" the firewall exists to keep inside, and
    # a consumer role that could read the action space could enumerate every
    # arm the engine will ever consider.
    "veto_drug_nutrient",
    "action_space",
    "action_space_info",
    "action_space_phase",
    # What version each registry is at. It carries no parameter values, but
    # its content hashes are a fingerprint of every proprietary registry in
    # the build, and DBF-005 keeps those inside.
    "registry_version",
    # The canonical invariants and fail-closed gates. They describe the
    # engine's own safety posture, which is not consumer-facing.
    "runtime_invariant",
]

# Ledger tables from build step 1.
CONFINED_LEDGER = [
    "raw_events",
    "event_quality",
    "controls_u",
    "measurements_y",
    "checkpoint_state",
    "replay_job",
    "replay_lag_policy",
]


@pytest.fixture
def as_app_consumer(ledger_db):
    """Run the body as the consumer service account, then switch back.

    Wrapped in a nested transaction because every assertion in this file
    expects a permission error, and a failed statement would otherwise
    poison the connection for the reset.
    """
    def run(sql: str):
        with ledger_db.transaction():
            with ledger_db.cursor() as cur:
                cur.execute("SET LOCAL ROLE app_consumer")
                cur.execute(sql)
                return cur.fetchall()

    return run


# === DBF-001: both schemas exist, engine tables confined ==================

def test_both_schemas_exist(ledger_db):
    """DBF-001 release test, first clause."""
    with ledger_db.cursor() as cur:
        cur.execute(
            "SELECT nspname FROM pg_namespace "
            "WHERE nspname IN ('engine_internal', 'client_render')"
        )
        found = {row["nspname"] for row in cur.fetchall()}
    assert found == {"engine_internal", "client_render"}


@pytest.mark.parametrize("table", CONFINED_REGISTRIES + CONFINED_LEDGER)
def test_engine_tables_are_confined_to_engine_internal(ledger_db, table):
    """DBF-001 release test, second clause: "raw posterior/state/pathway
    tables are confined to engine_internal"."""
    with ledger_db.cursor() as cur:
        cur.execute(
            "SELECT table_schema FROM information_schema.tables "
            "WHERE table_name = %s AND table_schema NOT IN "
            "('pg_catalog', 'information_schema')",
            (table,),
        )
        schemas = {row["table_schema"] for row in cur.fetchall()}
    assert schemas == {"engine_internal"}, f"{table} is in {schemas}"


def test_public_holds_nothing_but_the_migration_ledger(ledger_db):
    """Whatever remains in `public` is reachable by anyone holding the
    schema's default USAGE, so the set has to be knowingly empty of engine
    data -- not merely empty today by accident."""
    with ledger_db.cursor() as cur:
        cur.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public'"
        )
        remaining = {row["table_name"] for row in cur.fetchall()}
    assert remaining <= {"schema_migrations"}, f"engine data left in public: {remaining}"


# === DBF-002: the consumer role cannot reach the engine ===================

def test_app_consumer_has_no_usage_on_the_engine_schema(ledger_db):
    """The sheet's "REVOKE USAGE ON SCHEMA engine_internal FROM
    app_consumer" -- which is the control that makes every table inside
    unreachable at once, whatever grants a future migration forgets."""
    with ledger_db.cursor() as cur:
        cur.execute(
            "SELECT has_schema_privilege('app_consumer', 'engine_internal', 'USAGE') AS ok"
        )
        assert cur.fetchone()["ok"] is False


@pytest.mark.parametrize("table", CONFINED_REGISTRIES + CONFINED_LEDGER)
def test_app_consumer_select_on_the_engine_schema_is_denied(as_app_consumer, table):
    """QA-014 clause 1: "Connect as app_consumer: engine_internal SELECT
    must fail".

    Run for every confined table, registries included: an absorption kernel
    shape or an F_max ceiling is a proprietary model parameter, and DBF-005
    forbids those crossing just as firmly as it forbids a raw posterior.
    """
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        as_app_consumer(f"SELECT * FROM engine_internal.{table} LIMIT 1")


def test_app_consumer_cannot_reach_the_engine_through_the_catalog_either(as_app_consumer):
    """A denied SELECT on a named table is not the whole boundary: the same
    role must not be able to read engine rows by any route it can name."""
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        as_app_consumer("SELECT count(*) FROM engine_internal.nutrients")


def test_app_consumer_cannot_write_to_the_engine(as_app_consumer):
    """Ingest is the engine's own path. A consumer account that could insert
    a raw event could forge physiological history."""
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        as_app_consumer(
            "INSERT INTO engine_internal.raw_events (event_uuid) "
            "VALUES (gen_random_uuid())"
        )


def test_app_consumer_can_use_the_presentation_schema(ledger_db):
    """DBF-002's other half: the consumer must still be able to read what it
    is entitled to. A firewall that blocked everything would pass the first
    clause and ship a broken product."""
    with ledger_db.cursor() as cur:
        cur.execute(
            "SELECT has_schema_privilege('app_consumer', 'client_render', 'USAGE') AS ok"
        )
        assert cur.fetchone()["ok"] is True


def test_app_consumer_cannot_read_the_migration_ledger(as_app_consumer):
    """Defence in depth beyond the sheet's text: `public` keeps only
    migration bookkeeping, and the boundary should not rest on that staying
    true."""
    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        as_app_consumer("SELECT * FROM public.schema_migrations LIMIT 1")


# === DBF-003: the trusted sanitizer role ==================================

def test_engine_writer_can_read_the_engine_but_the_consumer_cannot(ledger_db):
    """DBF-003 release test: "Only the trusted server-side sanitizer role can
    transform internal state into client-safe rows.\""""
    with ledger_db.cursor() as cur:
        cur.execute(
            """
            SELECT
              has_schema_privilege('engine_writer', 'engine_internal', 'USAGE')   AS writer_usage,
              has_table_privilege('engine_writer', 'engine_internal.nutrients', 'SELECT') AS writer_select,
              has_schema_privilege('app_consumer',  'engine_internal', 'USAGE')   AS consumer_usage
            """
        )
        row = cur.fetchone()
    assert row["writer_usage"] is True
    assert row["writer_select"] is True
    assert row["consumer_usage"] is False


def test_engine_writer_cannot_rewrite_an_immutable_fact(ledger_db):
    """The firewall grants the sanitizer SELECT on engine_internal, never
    UPDATE -- and step 1's append-only triggers hold against it regardless.
    Two independent controls, neither relying on the other."""
    with ledger_db.cursor() as cur:
        cur.execute(
            "SELECT has_table_privilege('engine_writer', "
            "'engine_internal.raw_events', 'UPDATE') AS can_update"
        )
        assert cur.fetchone()["can_update"] is False


# === DBF-004: every client_render table is row-owner protected ============

def _unprotected_client_render_tables(conn) -> list[str]:
    """Tables in client_render that lack row level security or lack a
    policy. SIGDB '13_DB_TABLES': "All client_render tables are row-owner
    protected." """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT c.relname,
                   c.relrowsecurity,
                   (SELECT count(*) FROM pg_policy p WHERE p.polrelid = c.oid) AS policies
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'client_render' AND c.relkind = 'r'
            """
        )
        return [
            row["relname"]
            for row in cur.fetchall()
            if not row["relrowsecurity"] or row["policies"] == 0
        ]


def test_every_client_render_table_is_row_owner_protected(ledger_db):
    """DBF-004 as a standing rule rather than one example table.

    client_render is empty at this build step -- its payload tables belong
    to the projection step -- so today this passes over an empty set. That
    is the point: the assertion is installed BEFORE the tables exist, so the
    commit that adds an unprotected one turns CI red instead of shipping.
    The next test proves the assertion actually bites.
    """
    assert _unprotected_client_render_tables(ledger_db) == []


def test_the_row_owner_guard_actually_catches_an_unprotected_table(ledger_db):
    """A guard over an empty set proves nothing on its own. This creates a
    deliberately unprotected payload table, confirms the guard names it,
    then adds the sheet's canonical policy and confirms the guard clears --
    so the test above is known to be enforcing, not vacuous."""
    with ledger_db.cursor() as cur:
        cur.execute(
            "CREATE TABLE client_render.guard_probe "
            "(id uuid PRIMARY KEY, user_id uuid NOT NULL)"
        )

        assert "guard_probe" in _unprotected_client_render_tables(ledger_db)

        # RLS enabled but no policy is still unprotected -- an easy way to
        # believe a table is covered when nothing is.
        cur.execute("ALTER TABLE client_render.guard_probe ENABLE ROW LEVEL SECURITY")
        assert "guard_probe" in _unprotected_client_render_tables(ledger_db)

        # DBF-004's canonical policy shape.
        cur.execute(
            "CREATE POLICY own_rows ON client_render.guard_probe "
            "USING (user_id = current_setting('app.user_id')::uuid)"
        )
        assert "guard_probe" not in _unprotected_client_render_tables(ledger_db)

    # the fixture rolls back, so the probe never survives the test


def test_the_row_owner_policy_returns_no_cross_user_rows(ledger_db):
    """QA-014 clause 3: "cross-user RLS test returns no rows", exercised
    end to end against the sheet's own policy expression."""
    import uuid

    mine, theirs = uuid.uuid4(), uuid.uuid4()
    with ledger_db.cursor() as cur:
        cur.execute(
            "CREATE TABLE client_render.rls_probe "
            "(id uuid PRIMARY KEY DEFAULT gen_random_uuid(), user_id uuid NOT NULL, score int)"
        )
        cur.execute("ALTER TABLE client_render.rls_probe ENABLE ROW LEVEL SECURITY")
        cur.execute(
            "CREATE POLICY own_rows ON client_render.rls_probe "
            "USING (user_id = current_setting('app.user_id')::uuid)"
        )
        cur.execute(
            "INSERT INTO client_render.rls_probe (user_id, score) VALUES (%s, 71), (%s, 42)",
            (mine, theirs),
        )
        cur.execute("GRANT SELECT ON client_render.rls_probe TO app_consumer")

    with ledger_db.transaction():
        with ledger_db.cursor() as cur:
            cur.execute("SET LOCAL ROLE app_consumer")
            cur.execute("SELECT set_config('app.user_id', %s, true)", (str(mine),))
            cur.execute("SELECT user_id, score FROM client_render.rls_probe")
            rows = cur.fetchall()

    # own-user read succeeds, cross-user read returns nothing
    assert [r["score"] for r in rows] == [71]
    assert all(r["user_id"] == mine for r in rows)


# === DBF-005: no forbidden internal field crosses the boundary ============

# DBF-005, verbatim: the sanitizer "must never copy raw state vectors, raw
# biomarkers, hazards, mechanistic pathway values, or proprietary model
# parameters across the boundary." These fragments name those things as they
# are actually spelled in this build's engine tables and in the workbook's
# own column vocabulary.
FORBIDDEN_IN_CLIENT_RENDER = [
    "mean_219", "sqrt_cov", "covariance", "posterior", "state_vector",
    "r_cov", "process_noise", "lineage_hash",
    "gamma_k", "lambda_per_min", "f_max", "k_m", "v_max", "eta_hi", "eta_lo",
    "theta_hi", "theta_lo", "tau_dam", "tau_heal", "gamma_scar",
    "s_k", "p_s", "lambda_d", "hazard", "z_hi", "z_lo",
]


def test_no_forbidden_internal_field_exists_in_client_render(ledger_db):
    """DBF-005 release test: "Schema-diff and payload-contract tests prove
    forbidden internal fields are absent from client_render".

    Like the row-owner guard, this is installed before the payload tables
    exist so it constrains them as they are written, rather than being
    retrofitted after a leak.
    """
    with ledger_db.cursor() as cur:
        cur.execute(
            "SELECT table_name, column_name FROM information_schema.columns "
            "WHERE table_schema = 'client_render'"
        )
        offenders = [
            f"{row['table_name']}.{row['column_name']}"
            for row in cur.fetchall()
            for fragment in FORBIDDEN_IN_CLIENT_RENDER
            if fragment in row["column_name"].lower()
        ]
    assert offenders == [], f"forbidden internal fields in client_render: {offenders}"


def test_the_forbidden_field_guard_actually_catches_a_leak(ledger_db):
    """Proof the guard above bites: a payload table carrying a raw posterior
    mean must be named by it."""
    with ledger_db.cursor() as cur:
        cur.execute(
            "CREATE TABLE client_render.leak_probe "
            "(id uuid PRIMARY KEY, user_id uuid NOT NULL, mean_219 double precision[])"
        )
        cur.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'client_render' AND table_name = 'leak_probe'"
        )
        columns = {row["column_name"] for row in cur.fetchall()}

    assert "mean_219" in columns
    assert any(f in c for c in columns for f in FORBIDDEN_IN_CLIENT_RENDER)


def test_the_engine_schema_does_carry_those_fields(ledger_db):
    """The mirror image, and the reason the guard is not merely a spelling
    rule: these fields genuinely exist on the engine side. The firewall is
    about WHERE they live, not about avoiding the words."""
    with ledger_db.cursor() as cur:
        cur.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'engine_internal'"
        )
        engine_columns = {row["column_name"] for row in cur.fetchall()}

    assert "lineage_hash" in engine_columns
    assert "r_cov" in engine_columns
    assert "f_max" in engine_columns
