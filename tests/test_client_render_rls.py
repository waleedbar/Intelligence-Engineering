"""Row-owner protection on the presentation schema.

SIGDB 13_DB_TABLES states one rule, identically, on all 33 declared tables:

    "user_id = authenticated subject; service bypass separated"

These tests exercise it as the two roles that matter, against real rows,
rather than reading the catalogue. A policy that exists and does not bite is
worse than none, because the catalogue says it is there.

The `ledger_db` fixture rolls its connection back after every test, so the
rows seeded here never outlive the test that wrote them.
"""
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest

CLIENT_TABLES = [
    "api_snapshot",
    "signal_value_scalar",
    "signal_value_vector",
    "signal_vector_member",
    "signal_time_series_point",
    "feature_payload",
    "ui_plan",
]

# 13_DB_TABLES names thirteen client_render tables; 14_DB_COLUMNS gives
# columns for these seven. The other six are declared and uncolumned, and are
# deliberately not built -- see docs/parameter-gaps.md.
DECLARED_WITHOUT_COLUMNS = {
    "signal_availability",
    "science_packet",
    "share_receipt",
    "consent_receipt",
    "notification_settings",
    "audit_receipt_public",
}

# Fresh per test rather than two fixed constants. A test that asserts an
# absolute row count is otherwise hostage to anything already committed in
# the database it runs against -- which is exactly how these first failed,
# against rows left behind by hand-probing the policies.
@pytest.fixture
def USER_A():
    return uuid.uuid4()


@pytest.fixture
def USER_B():
    return uuid.uuid4()


pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL is not set; RLS tests need a real PostgreSQL")


def _snapshot(cur, user_id, *, tag, expired=False, product="TWIN"):
    """Insert one snapshot as the owning role and return its id."""
    snapshot_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    generated = now - timedelta(hours=2) if expired else now
    expires = now - timedelta(hours=1) if expired else now + timedelta(hours=1)
    cur.execute(
        "INSERT INTO client_render.api_snapshot "
        "(snapshot_id, user_id, product, schema_version, payload_json, "
        " generated_at, data_through, expires_at, availability_status, "
        " confidence_tier, lineage_ref, key_id, payload_hash, signature) "
        "VALUES (%s, %s, %s, 'v1', '{}', %s, %s, %s, 'available', 'high', "
        "        gen_random_uuid(), 'key-1', %s, 'sig')",
        (snapshot_id, user_id, product, generated, generated, expires,
         f"hash-{tag}"),
    )
    return snapshot_id


@pytest.fixture
def as_role(ledger_db):
    """Run a statement as another role, inside a savepoint.

    The savepoint is what makes an EXPECTED permission error harmless: it
    propagates out of `transaction()`, which unwinds to the savepoint and
    leaves the connection usable. Same shape as `as_app_consumer` in
    tests/test_firewall.py, with an authenticated subject added.

    `SET LOCAL` means both the role and the subject revert with the
    savepoint, so neither leaks into the next statement.
    """
    def run(sql, *, role="app_consumer", subject=None, params=None):
        with ledger_db.transaction():
            with ledger_db.cursor() as cur:
                cur.execute(f"SET LOCAL ROLE {role}")
                if subject is not None:
                    # set_config(..., is_local => true) is SET LOCAL in
                    # function form. The statement form takes no bound
                    # parameter, and building it by string interpolation
                    # would put a caller-supplied value into SQL text.
                    cur.execute(
                        "SELECT set_config('sahacore.subject_id', %s, true)",
                        (str(subject),))
                cur.execute(sql, params or ())
                return cur.fetchall()
    return run


# === the rule is installed on every table =================================

def test_every_client_render_table_has_both_halves_of_the_rule(ledger_db):
    """"service bypass separated" is not decoration: a table with only a
    subject policy has no service access, and one with only a service policy
    is invisible to the client it exists for."""
    with ledger_db.cursor() as cur:
        cur.execute("SELECT * FROM client_render.table_protection")
        rows = {r["table_name"]: r for r in cur.fetchall()}

    assert set(rows) == set(CLIENT_TABLES)
    for name, row in rows.items():
        assert row["rls_enabled"], name
        assert row["subject_policies"] >= 1, name
        assert row["service_policies"] >= 1, name


def test_the_uncolumned_tables_were_not_invented(ledger_db):
    """SIGDB declares thirteen and columns seven. The six it leaves
    uncolumned are not built: a table name is not a schema, and this is the
    boundary where guessing is least acceptable."""
    with ledger_db.cursor() as cur:
        cur.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'client_render'")
        built = {r["tablename"] for r in cur.fetchall()}

    assert built == set(CLIENT_TABLES)
    assert not (built & DECLARED_WITHOUT_COLUMNS)


# === the subject predicate ================================================

def test_a_connection_with_no_subject_sees_nothing(ledger_db, as_role, USER_A, USER_B):
    """FAIL CLOSED. current_subject() is NULL when the GUC is unset, and
    `user_id = NULL` is never true -- so an unauthenticated connection gets
    an empty result rather than everything."""
    with ledger_db.cursor() as cur:
        _snapshot(cur, USER_A, tag="none-a")
        _snapshot(cur, USER_B, tag="none-b")

    rows = as_role("SELECT count(*) AS n FROM client_render.api_snapshot")
    assert rows[0]["n"] == 0


def test_a_subject_sees_its_own_rows_and_only_its_own(ledger_db, as_role, USER_A, USER_B):
    with ledger_db.cursor() as cur:
        _snapshot(cur, USER_A, tag="own-a")
        _snapshot(cur, USER_B, tag="own-b")

    for subject in (USER_A, USER_B):
        rows = as_role("SELECT user_id FROM client_render.api_snapshot",
                       subject=subject)
        assert len(rows) == 1
        assert rows[0]["user_id"] == subject


def test_asking_for_another_subject_by_name_returns_nothing(ledger_db, as_role, USER_A, USER_B):
    """The failure a WHERE clause cannot cause: authenticated as A, asking
    explicitly for B's rows. RLS ANDs its predicate onto the query, so the
    request is not denied -- it is empty."""
    with ledger_db.cursor() as cur:
        _snapshot(cur, USER_B, tag="cross-b")

    rows = as_role(
        "SELECT count(*) AS n FROM client_render.api_snapshot WHERE user_id = %s",
        subject=USER_A, params=(USER_B,))
    assert rows[0]["n"] == 0


# === expiry is part of the client predicate ===============================

def test_an_expired_snapshot_is_unreadable_by_its_own_owner(ledger_db, as_role, USER_A):
    """14_DB_COLUMNS calls expires_at a "Hard client expiry". Enforced in the
    policy rather than the serializer, so a query that forgets the filter
    still cannot serve a stale payload."""
    with ledger_db.cursor() as cur:
        _snapshot(cur, USER_A, tag="live", product="TWIN")
        _snapshot(cur, USER_A, tag="dead", product="PULSE", expired=True)

    rows = as_role("SELECT product FROM client_render.api_snapshot",
                   subject=USER_A)
    assert [r["product"] for r in rows] == ["TWIN"]


def test_the_service_still_sees_the_expired_row(ledger_db, as_role, USER_A):
    """"expires_at + bounded audit" retention needs something able to read
    what the client no longer can, to sweep or audit it.

    This is also the test that caught a real defect: engine_writer held
    INSERT and UPDATE on client_render and never SELECT, so its service
    policy -- `FOR ALL ... USING (true)` -- looked like full access and was
    not. A policy filters a grant; it never creates one.
    """
    with ledger_db.cursor() as cur:
        _snapshot(cur, USER_A, tag="svc-live")
        _snapshot(cur, USER_A, tag="svc-dead", product="PULSE", expired=True)

    rows = as_role(
        "SELECT count(*) AS n FROM client_render.api_snapshot WHERE user_id = %s",
        role="engine_writer", params=(USER_A,))
    assert rows[0]["n"] == 2


# === ownership is a chain =================================================

def test_a_child_row_is_visible_exactly_when_its_parent_is(ledger_db, as_role, USER_A, USER_B):
    """Only api_snapshot carries user_id. The children reach it through
    snapshot_id, and because the parent is itself RLS-protected that subquery
    is filtered by the same policy under the same role -- so the subject test
    AND the expiry test are inherited rather than restated six times."""
    with ledger_db.cursor() as cur:
        live = _snapshot(cur, USER_A, tag="chain-live")
        dead = _snapshot(cur, USER_A, tag="chain-dead", product="PULSE",
                         expired=True)
        other = _snapshot(cur, USER_B, tag="chain-other")
        for snapshot, value in ((live, 74.0), (dead, 51.0), (other, 42.0)):
            cur.execute(
                "INSERT INTO client_render.signal_value_scalar "
                "(snapshot_id, signal_id, number_value, value_status) "
                "VALUES (%s, 'SIG0001', %s, 'available')",
                (snapshot, value))

    rows = as_role("SELECT number_value FROM client_render.signal_value_scalar",
                   subject=USER_A)
    assert [r["number_value"] for r in rows] == [74.0]


def test_the_two_step_chain_holds_for_vector_members(ledger_db, as_role, USER_A, USER_B):
    """signal_vector_member reaches user_id through vector then snapshot --
    two hops, both RLS-protected."""
    with ledger_db.cursor() as cur:
        for user, value, tag in ((USER_A, 74.0, "vec-a"), (USER_B, 42.0, "vec-b")):
            snapshot = _snapshot(cur, user, tag=tag)
            vector_id = uuid.uuid4()
            cur.execute(
                "INSERT INTO client_render.signal_value_vector "
                "(vector_id, snapshot_id, signal_id, axis_id, expected_count, "
                " order_version) "
                "VALUES (%s, %s, 'SIG0100', 'PROCESS_CLUSTER', 12, 'v1')",
                (vector_id, snapshot))
            cur.execute(
                "INSERT INTO client_render.signal_vector_member "
                "(vector_id, member_order, member_id, number_value, "
                " band_token, availability_status) "
                "VALUES (%s, 1, 'C01', %s, 'build', 'available')",
                (vector_id, value))

    rows = as_role("SELECT number_value FROM client_render.signal_vector_member",
                   subject=USER_A)
    assert [r["number_value"] for r in rows] == [74.0]


# === the client role cannot write ========================================

@pytest.mark.parametrize("statement", [
    "INSERT INTO client_render.signal_value_scalar "
    "(snapshot_id, signal_id, value_status) "
    "VALUES (gen_random_uuid(), 'SIG0001', 'unavailable')",
    "UPDATE client_render.api_snapshot SET confidence_tier = 'high'",
    "DELETE FROM client_render.signal_value_scalar",
])
def test_the_consumer_cannot_write_to_the_presentation_schema(
        as_role, statement, USER_A):
    """Read-only by GRANT, not merely by policy. The subject policy is FOR
    SELECT and no write grant exists, so a write is refused before RLS is
    consulted at all."""
    import psycopg

    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        as_role(statement, subject=USER_A)


def test_the_consumer_still_cannot_reach_the_engine_schema(as_role, USER_A):
    """FW03, restated here because this migration granted new privileges and
    the question "did that widen anything" deserves an answer in the same
    file."""
    import psycopg

    with pytest.raises(psycopg.errors.InsufficientPrivilege):
        as_role("SELECT count(*) FROM engine_internal.raw_events",
                subject=USER_A)


# === the enums the payload columns are checked against ====================

@pytest.mark.parametrize("column,bad_value", [
    ("availability_status", "maybe"),
    ("confidence_tier", "pretty_sure"),
    ("product", "SAHATWIN"),
])
def test_a_value_outside_the_declared_enum_is_refused(
        ledger_db, column, bad_value, USER_A):
    """16_ENUMS is the public codebook and its note is explicit: "Additions
    require a schema version and client compatibility decision." A token the
    client has no rendering for must not reach the client."""
    import psycopg

    with ledger_db.cursor() as cur:
        snapshot = _snapshot(cur, USER_A, tag=f"enum-{column}")

    with pytest.raises(psycopg.errors.CheckViolation):
        with ledger_db.transaction():
            with ledger_db.cursor() as cur:
                cur.execute(
                    f"UPDATE client_render.api_snapshot SET {column} = %s "
                    "WHERE snapshot_id = %s",
                    (bad_value, snapshot))


def test_an_available_value_must_actually_carry_one(ledger_db, USER_A):
    """FW08 FAIL_CLOSED at the column level: a scalar marked `available`
    with all three value columns null is a fabricated availability."""
    import psycopg

    with ledger_db.cursor() as cur:
        snapshot = _snapshot(cur, USER_A, tag="fw08")

    with pytest.raises(psycopg.errors.CheckViolation):
        with ledger_db.transaction():
            with ledger_db.cursor() as cur:
                cur.execute(
                    "INSERT INTO client_render.signal_value_scalar "
                    "(snapshot_id, signal_id, value_status) "
                    "VALUES (%s, 'SIG0001', 'available')",
                    (snapshot,))
