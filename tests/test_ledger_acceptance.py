"""Step 1's acceptance tests, run against a real PostgreSQL.

'★ Build Guide Python' row A3 states step 1's acceptance test as exactly two
scenarios: "duplicate event no-op; late event replay". Both are also named,
RELEASE_BLOCKING, in the 'Replay Contract' section F battery:

    RT-02  "Same lab delivered twice"          -> "Second delivery is a no-op"
           failure meaning: "Duplicate evidence stacking"
    RT-01  "Late inflammatory lab inside 14-day lag"
    AUD-01 "Query what engine knew before late result"
           -> "System-time view returns old decision context; event-time
               current view returns revised physiology"
           failure meaning: "Bitemporal audit collapsed"

These run against Postgres rather than a mock because what they assert IS
database behaviour: a UNIQUE constraint deciding a race, a trigger refusing
an UPDATE, a CHECK rejecting an 80-long dose vector. A mock that agreed with
every one of them would prove nothing about the deployed engine.
"""
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import psycopg
import pytest

from sahacore.ledger import (
    ROUTINE,
    SUPPORT_POINT,
    SUPPORT_WINDOWED,
    active_event_quality,
    best_current_history,
    event_uuid_for,
    history_known_at,
    ingest_event,
    lag,
    open_replay_job,
    record_event_quality,
    record_measurement,
    replay_policy,
    routine_lag_days,
    select_replay_checkpoint,
    write_checkpoint,
    write_control_vector,
)
from sahacore.ledger.checkpoints import NoEligibleCheckpoint
from sahacore.ledger.controls import ControlVectorShapeError

UTC = timezone.utc


@pytest.fixture
def user_id() -> uuid.UUID:
    return uuid.uuid4()


@contextmanager
def rejected(conn, error):
    """Assert the database refuses what happens inside, and unwind only that
    statement.

    A rejected statement poisons its transaction, so the test's own setup
    rows would be lost to a plain rollback. Wrapping the attempt in a nested
    transaction (a SAVEPOINT) releases just the failed statement, which lets
    a test check both that a bad write is refused AND that the good rows
    around it survived -- the shape most of these invariants actually need.
    """
    with pytest.raises(error), conn.transaction():
        yield


def _log_meal(conn, user_id, *, source_event_id, occurred_at, ingested_at, payload=None):
    return ingest_event(
        conn,
        adapter_source_id="test-adapter",
        source_event_id=source_event_id,
        user_id=user_id,
        event_type="meal",
        payload=payload if payload is not None else {"items": ["oats"]},
        occurred_at=occurred_at,
        ingested_at=ingested_at,
    )


# === ACCEPTANCE 1: "duplicate event no-op" (RT-02) ========================

def test_a_duplicate_delivery_is_a_no_op(ledger_db, user_id):
    """RT-02 and U-Ledger A10: "Idempotent no-op on second delivery",
    prohibited: "Second Kalman update"."""
    drawn = datetime(2026, 9, 1, 7, 30, tzinfo=UTC)
    received = datetime(2026, 9, 3, 9, 0, tzinfo=UTC)

    def deliver():
        return ingest_event(
            ledger_db,
            adapter_source_id="lab-partner-a",
            source_event_id="ORDER-8891",
            user_id=user_id,
            event_type="lab",
            payload={"analyte": "hs-CRP", "value": 4.8, "unit": "mg/L"},
            specimen_at=drawn,
            ingested_at=received,
        )

    first = deliver()
    second = deliver()

    assert not first.is_duplicate
    assert second.is_duplicate

    # the second delivery added nothing at all
    assert second.event_uuid == first.event_uuid
    assert second.ingest_seq == first.ingest_seq
    assert second.lineage_hash == first.lineage_hash

    with ledger_db.cursor() as cur:
        cur.execute(
            "SELECT count(*) AS n FROM engine_internal.raw_events WHERE user_id = %s",
            (user_id,),
        )
        assert cur.fetchone()["n"] == 1


def test_a_duplicate_carrying_a_different_payload_does_not_overwrite_the_original(
    ledger_db, user_id
):
    """DataMap I3: "the original fact is never overwritten". A second
    delivery under the same source identifiers is rejected wholesale -- it
    does not update the row and it does not report its own payload back, so
    a caller cannot mistake it for an accepted revision."""
    occurred = datetime(2026, 9, 8, 12, 0, tzinfo=UTC)
    ingested = datetime(2026, 9, 8, 12, 5, tzinfo=UTC)

    first = _log_meal(
        ledger_db, user_id, source_event_id="MEAL-1",
        occurred_at=occurred, ingested_at=ingested, payload={"items": ["oats"]},
    )
    second = _log_meal(
        ledger_db, user_id, source_event_id="MEAL-1",
        occurred_at=occurred, ingested_at=ingested, payload={"items": ["cake"]},
    )

    assert second.is_duplicate
    assert second.lineage_hash == first.lineage_hash
    with ledger_db.cursor() as cur:
        cur.execute(
            "SELECT payload_json FROM engine_internal.raw_events WHERE event_uuid = %s",
            (first.event_uuid,),
        )
        assert cur.fetchone()["payload_json"] == {"items": ["oats"]}


def test_the_event_uuid_is_derived_from_the_source_identifiers():
    """So the same physical observation maps to the same primary key in
    every process and after a rebuild from the same facts -- which is what
    makes the no-op survive a replay that reconstructs the ledger."""
    assert event_uuid_for("lab-a", "ORDER-1") == event_uuid_for("lab-a", "ORDER-1")
    assert event_uuid_for("lab-a", "ORDER-1") != event_uuid_for("lab-b", "ORDER-1")
    # the separator is not forgeable by moving a delimiter between fields
    assert event_uuid_for("a|b", "c") != event_uuid_for("a", "b|c")


def test_a_correction_is_a_new_event_and_leaves_the_corrected_fact_intact(
    ledger_db, user_id
):
    """Step 2: "A correction is a new event linked by
    correction_of_event_id; never overwrite the old fact.\""""
    original = _log_meal(
        ledger_db, user_id, source_event_id="MEAL-2",
        occurred_at=datetime(2026, 9, 8, 12, 0, tzinfo=UTC),
        ingested_at=datetime(2026, 9, 8, 12, 5, tzinfo=UTC),
        payload={"items": ["oats"], "grams": 300},
    )
    correction = ingest_event(
        ledger_db,
        adapter_source_id="test-adapter",
        source_event_id="MEAL-2-CORR",
        user_id=user_id,
        event_type="correction",
        payload={"items": ["oats"], "grams": 80},
        occurred_at=datetime(2026, 9, 8, 12, 0, tzinfo=UTC),
        ingested_at=datetime(2026, 9, 9, 8, 0, tzinfo=UTC),
        correction_of_event_id=original.event_uuid,
    )

    assert not correction.is_duplicate
    assert correction.event_uuid != original.event_uuid
    with ledger_db.cursor() as cur:
        cur.execute(
            "SELECT payload_json, correction_of_event_id "
            "FROM engine_internal.raw_events WHERE event_uuid IN (%s, %s) "
            "ORDER BY ingest_seq",
            (original.event_uuid, correction.event_uuid),
        )
        rows = cur.fetchall()
    assert rows[0]["payload_json"]["grams"] == 300  # untouched
    assert rows[0]["correction_of_event_id"] is None
    assert rows[1]["correction_of_event_id"] == original.event_uuid


def test_an_admitted_fact_cannot_be_updated_or_deleted(ledger_db, user_id):
    """'★ Signal Memory Bank' B6: raw events are "IMMUTABLE -- append-only",
    enforced by a trigger so no code path, migration or console session can
    rewrite one."""
    event = _log_meal(
        ledger_db, user_id, source_event_id="MEAL-3",
        occurred_at=datetime(2026, 9, 8, 12, 0, tzinfo=UTC),
        ingested_at=datetime(2026, 9, 8, 12, 5, tzinfo=UTC),
    )

    for statement in (
        "UPDATE engine_internal.raw_events SET quality = 'tampered' WHERE event_uuid = %s",
        "DELETE FROM engine_internal.raw_events WHERE event_uuid = %s",
    ):
        with rejected(ledger_db, psycopg.errors.RaiseException), ledger_db.cursor() as cur:
            cur.execute(statement, (event.event_uuid,))


# === ACCEPTANCE 2: "late event replay" (RT-01 + AUD-01) ==================

def test_a_late_lab_replays_from_a_checkpoint_that_precedes_its_evidence(
    ledger_db, user_id
):
    """The full step-1 half of RT-01: a lab drawn on the 1st and received on
    the 10th must (a) be classified ROUTINE inside the configured lag,
    (b) select a durable checkpoint STRICTLY BEFORE the evidence-support
    time, not the later one taken after the draw, and (c) leave a ReplayJob
    receipt naming that checkpoint."""
    drawn = datetime(2026, 9, 1, 7, 30, tzinfo=UTC)
    received = datetime(2026, 9, 10, 9, 0, tzinfo=UTC)

    before = write_checkpoint(
        ledger_db, user_id=user_id,
        effective_at=datetime(2026, 8, 31, 0, 0, tzinfo=UTC),
        knowledge_at=datetime(2026, 8, 31, 0, 5, tzinfo=UTC),
        model_shape_version="S2-219",
    )
    after = write_checkpoint(
        ledger_db, user_id=user_id,
        effective_at=datetime(2026, 9, 5, 0, 0, tzinfo=UTC),
        knowledge_at=datetime(2026, 9, 5, 0, 5, tzinfo=UTC),
        model_shape_version="S2-219",
    )

    event = ingest_event(
        ledger_db,
        adapter_source_id="lab-partner-a",
        source_event_id="ORDER-9001",
        user_id=user_id,
        event_type="lab",
        payload={"analyte": "hs-CRP", "value": 6.1, "unit": "mg/L"},
        specimen_at=drawn,
        ingested_at=received,
    )
    assert event.effective_at == drawn  # G7: lab uses specimen_at
    assert event.knowledge_at == received

    measurement = record_measurement(
        ledger_db,
        user_id=user_id,
        measurement_type="hs_crp",
        value=6.1,
        unit="mg/L",
        r_cov=0.25,
        source_event_id=event.event_uuid,
        effective_at=event.effective_at,
        knowledge_at=event.knowledge_at,
        ingested_at=received,
        specimen_at=drawn,
        is_lab=True,
        parent_event_hash=event.lineage_hash,
    )

    # (a) inside the configured fixed lag -> routine replay
    lag_days = lag(event.effective_at, event.knowledge_at)
    assert lag_days == pytest.approx(9.0625)
    policy = replay_policy(
        lag_days=lag_days, routine_lag_days=routine_lag_days(ledger_db)
    )
    assert policy == ROUTINE

    # (b) the LATEST DURABLE checkpoint STRICTLY BEFORE the support time
    checkpoint = select_replay_checkpoint(
        ledger_db,
        user_id=user_id,
        evidence_support_start=measurement.evidence_support_start,
    )
    assert checkpoint.checkpoint_id == before
    assert checkpoint.checkpoint_id != after
    assert checkpoint.effective_at < measurement.evidence_support_start

    # (c) the receipt
    job = open_replay_job(
        ledger_db,
        user_id=user_id,
        trigger_event_id=event.event_uuid,
        effective_at=event.effective_at,
        knowledge_at=event.knowledge_at,
        replay_horizon=timedelta(days=14),
        policy=policy,
        checkpoint_id=checkpoint.checkpoint_id,
    )
    with ledger_db.cursor() as cur:
        cur.execute(
            "SELECT policy, checkpoint_id, status FROM engine_internal.replay_job "
            "WHERE replay_job_id = %s",
            (job,),
        )
        row = cur.fetchone()
    assert row["policy"] == ROUTINE
    assert row["checkpoint_id"] == checkpoint.checkpoint_id
    assert row["status"] == "PENDING"


def test_a_windowed_assay_rewinds_behind_its_whole_window(ledger_db, user_id):
    """Step 3's E_WINDOWED clause. An HbA1c drawn on 1 September is evidence
    about the preceding 90 days, so a checkpoint taken in August -- before
    the draw but INSIDE the window -- is not eligible; only one preceding
    the window's start is."""
    drawn = datetime(2026, 9, 1, 7, 30, tzinfo=UTC)

    inside_window = write_checkpoint(
        ledger_db, user_id=user_id,
        effective_at=datetime(2026, 8, 20, tzinfo=UTC),
        knowledge_at=datetime(2026, 8, 20, tzinfo=UTC),
        model_shape_version="S2-219",
    )
    before_window = write_checkpoint(
        ledger_db, user_id=user_id,
        effective_at=datetime(2026, 5, 1, tzinfo=UTC),
        knowledge_at=datetime(2026, 5, 1, tzinfo=UTC),
        model_shape_version="S2-219",
    )

    event = ingest_event(
        ledger_db,
        adapter_source_id="lab-partner-a",
        source_event_id="ORDER-9002",
        user_id=user_id,
        event_type="lab",
        payload={"analyte": "HbA1c", "value": 5.9, "unit": "%"},
        specimen_at=drawn,
        ingested_at=datetime(2026, 9, 3, tzinfo=UTC),
    )
    measurement = record_measurement(
        ledger_db,
        user_id=user_id,
        measurement_type="hba1c",
        value=5.9,
        unit="%",
        r_cov=0.04,
        source_event_id=event.event_uuid,
        effective_at=event.effective_at,
        knowledge_at=event.knowledge_at,
        ingested_at=datetime(2026, 9, 3, tzinfo=UTC),
        specimen_at=drawn,
        is_lab=True,
        support_class=SUPPORT_WINDOWED,
        support_window_days=90.0,
        parent_event_hash=event.lineage_hash,
    )

    checkpoint = select_replay_checkpoint(
        ledger_db, user_id=user_id,
        evidence_support_start=measurement.evidence_support_start,
    )
    assert checkpoint.checkpoint_id == before_window
    assert checkpoint.checkpoint_id != inside_window


def test_a_checkpoint_at_the_exact_support_instant_is_not_eligible(ledger_db, user_id):
    """G9 says "checkpoint.as_of_effective_time < evidence_support_start" --
    strictly before. A checkpoint taken at that instant already contains
    inferred history for it."""
    t = datetime(2026, 9, 1, 7, 30, tzinfo=UTC)
    write_checkpoint(
        ledger_db, user_id=user_id, effective_at=t, knowledge_at=t,
        model_shape_version="S2-219",
    )
    with pytest.raises(NoEligibleCheckpoint):
        select_replay_checkpoint(ledger_db, user_id=user_id, evidence_support_start=t)


def test_a_non_durable_checkpoint_is_not_a_replay_start_point(ledger_db, user_id):
    """Step 3: "the latest DURABLE checkpoint"."""
    write_checkpoint(
        ledger_db, user_id=user_id,
        effective_at=datetime(2026, 8, 31, tzinfo=UTC),
        knowledge_at=datetime(2026, 8, 31, tzinfo=UTC),
        model_shape_version="S2-219",
        durable=False,
    )
    with pytest.raises(NoEligibleCheckpoint):
        select_replay_checkpoint(
            ledger_db, user_id=user_id,
            evidence_support_start=datetime(2026, 9, 1, tzinfo=UTC),
        )


def test_a_checkpoint_cannot_be_mutated_by_a_later_one(ledger_db, user_id):
    """G19: "immutable checkpoint; newer checkpoint never mutates older
    one\"."""
    checkpoint = write_checkpoint(
        ledger_db, user_id=user_id,
        effective_at=datetime(2026, 8, 31, tzinfo=UTC),
        knowledge_at=datetime(2026, 8, 31, tzinfo=UTC),
        model_shape_version="S2-219",
    )
    with rejected(ledger_db, psycopg.errors.RaiseException), ledger_db.cursor() as cur:
        cur.execute(
            "UPDATE engine_internal.checkpoint_state SET posterior_version = 'v2' "
            "WHERE checkpoint_id = %s",
            (checkpoint,),
        )


# --- AUD-01: the two views must not collapse ------------------------------

def test_the_two_views_differ_appropriately_for_a_late_lab(ledger_db, user_id):
    """AUD-01 (RELEASE_BLOCKING) and step 10 (G16). The lab was drawn on the
    1st and received on the 10th. Asked what happened in early September,
    the event-time view now includes it. Asked what the engine knew on the
    5th -- when a warning might have been served -- the system-time view
    must not, or the audit trail claims knowledge the engine did not have."""
    drawn = datetime(2026, 9, 1, 7, 30, tzinfo=UTC)
    received = datetime(2026, 9, 10, 9, 0, tzinfo=UTC)
    decision_time = datetime(2026, 9, 5, 12, 0, tzinfo=UTC)

    _log_meal(
        ledger_db, user_id, source_event_id="MEAL-EARLY",
        occurred_at=datetime(2026, 9, 1, 8, 0, tzinfo=UTC),
        ingested_at=datetime(2026, 9, 1, 8, 5, tzinfo=UTC),
    )
    late_lab = ingest_event(
        ledger_db,
        adapter_source_id="lab-partner-a",
        source_event_id="ORDER-9003",
        user_id=user_id,
        event_type="lab",
        payload={"analyte": "hs-CRP", "value": 6.1, "unit": "mg/L"},
        specimen_at=drawn,
        ingested_at=received,
    )

    window = {
        "effective_from": datetime(2026, 9, 1, tzinfo=UTC),
        "effective_to": datetime(2026, 9, 8, tzinfo=UTC),
    }
    current = best_current_history(ledger_db, user_id=user_id, **window)
    as_known_then = history_known_at(
        ledger_db, user_id=user_id, knowledge_cutoff=decision_time, **window
    )

    current_ids = {row["event_uuid"] for row in current}
    known_ids = {row["event_uuid"] for row in as_known_then}

    # event-time current view returns the revised physiology ...
    assert late_lab.event_uuid in current_ids
    # ... system-time view returns the old decision context
    assert late_lab.event_uuid not in known_ids
    assert known_ids < current_ids
    assert known_ids  # the meal was known on the 5th and stays known


def test_the_event_time_view_is_ordered_for_deterministic_replay(ledger_db, user_id):
    """Step 4: replay is "ordered by effective_at, then ingestion sequence as
    the tie-breaker", so two events sharing an instant still replay in one
    fixed order. G10 requires that determinism: "same inputs + versions
    produce identical posterior hashes"."""
    same_instant = datetime(2026, 9, 8, 12, 0, tzinfo=UTC)
    for n in range(3):
        _log_meal(
            ledger_db, user_id, source_event_id=f"TIE-{n}",
            occurred_at=same_instant,
            ingested_at=same_instant + timedelta(minutes=n),
        )
    rows = best_current_history(
        ledger_db, user_id=user_id,
        effective_from=same_instant,
        effective_to=same_instant + timedelta(minutes=1),
    )
    assert len(rows) == 3
    assert [r["effective_at"] for r in rows] == [same_instant] * 3
    seqs = [r["ingest_seq"] for r in rows]
    assert seqs == sorted(seqs)


# === the ledger's own structural invariants ==============================

def test_a_control_vector_must_carry_exactly_81_doses(ledger_db, user_id):
    """DataMap I5: "81 nutrient doses present". The Replay Contract's
    section E correction "Nutrient count" names 80 as the pre-nitrate
    defect, so an 80-long vector must be impossible to store."""
    event = _log_meal(
        ledger_db, user_id, source_event_id="MEAL-CTRL",
        occurred_at=datetime(2026, 9, 8, 12, 0, tzinfo=UTC),
        ingested_at=datetime(2026, 9, 8, 12, 5, tzinfo=UTC),
    )
    args = dict(
        user_id=user_id,
        effective_time=datetime(2026, 9, 8, 12, 0, tzinfo=UTC),
        parent_event_ids=[event.event_uuid],
        parent_event_hashes=[event.lineage_hash],
        as_of_effective_time=datetime(2026, 9, 8, 12, 0, tzinfo=UTC),
        as_of_knowledge_time=datetime(2026, 9, 8, 12, 5, tzinfo=UTC),
    )
    with pytest.raises(ControlVectorShapeError, match="80"):
        write_control_vector(ledger_db, dose_vector_81=[0.0] * 80, **args)

    written = write_control_vector(ledger_db, dose_vector_81=[0.0] * 81, **args)
    assert written.control_version == 1


def test_the_table_itself_rejects_an_80_long_vector(ledger_db, user_id):
    """The Python guard above is a diagnosis; this is the guarantee. It has
    to hold against every writer, including a future loader or a console
    session, not only against sahacore.ledger.controls."""
    event = _log_meal(
        ledger_db, user_id, source_event_id="MEAL-CTRL-RAW",
        occurred_at=datetime(2026, 9, 8, 12, 0, tzinfo=UTC),
        ingested_at=datetime(2026, 9, 8, 12, 5, tzinfo=UTC),
    )
    with rejected(ledger_db, psycopg.errors.CheckViolation), ledger_db.cursor() as cur:
        cur.execute(
            """
            INSERT INTO engine_internal.controls_u (
                user_id, effective_time, control_version, dose_vector_81,
                parent_event_ids, as_of_effective_time, as_of_knowledge_time,
                lineage_hash
            ) VALUES (%s, now(), 1, %s, %s, now(), now(), 'sha256:x')
            """,
            (user_id, [0.0] * 80, [event.event_uuid]),
        )


def test_recomputing_a_control_vector_supersedes_rather_than_overwrites(
    ledger_db, user_id
):
    """DataMap G5: "versioned and recomputed from immutable events on
    replay". The old belief about what was consumed stays auditable."""
    event = _log_meal(
        ledger_db, user_id, source_event_id="MEAL-CTRL-2",
        occurred_at=datetime(2026, 9, 8, 12, 0, tzinfo=UTC),
        ingested_at=datetime(2026, 9, 8, 12, 5, tzinfo=UTC),
    )
    t = datetime(2026, 9, 8, 12, 0, tzinfo=UTC)
    args = dict(
        user_id=user_id, effective_time=t,
        parent_event_ids=[event.event_uuid],
        parent_event_hashes=[event.lineage_hash],
        as_of_effective_time=t,
        as_of_knowledge_time=datetime(2026, 9, 8, 12, 5, tzinfo=UTC),
    )
    v1 = write_control_vector(ledger_db, dose_vector_81=[1.0] * 81, **args)
    v2 = write_control_vector(ledger_db, dose_vector_81=[2.0] * 81, **args)

    assert (v1.control_version, v2.control_version) == (1, 2)
    assert v1.lineage_hash != v2.lineage_hash

    with ledger_db.cursor() as cur:
        cur.execute(
            "SELECT control_version, status FROM engine_internal.controls_u "
            "WHERE user_id = %s AND effective_time = %s ORDER BY control_version",
            (user_id, t),
        )
        rows = cur.fetchall()
    assert [(r["control_version"], r["status"]) for r in rows] == [
        (1, "SUPERSEDED"),
        (2, "ACTIVE"),
    ]


def test_one_source_event_yields_one_active_measurement_per_type(ledger_db, user_id):
    """DataMap I6: "same source measurement applied once per active replay
    lineage", and U-Ledger A15's reason: independent reuse of one
    source_event_id "creates false precision"."""
    drawn = datetime(2026, 9, 1, 7, 30, tzinfo=UTC)
    received = datetime(2026, 9, 3, tzinfo=UTC)
    event = ingest_event(
        ledger_db,
        adapter_source_id="lab-partner-a",
        source_event_id="ORDER-9004",
        user_id=user_id,
        event_type="lab",
        payload={"analyte": "hs-CRP", "value": 6.1},
        specimen_at=drawn,
        ingested_at=received,
    )
    common = dict(
        user_id=user_id, measurement_type="hs_crp", unit="mg/L", r_cov=0.25,
        source_event_id=event.event_uuid, effective_at=drawn,
        knowledge_at=received, ingested_at=received, specimen_at=drawn,
        is_lab=True, parent_event_hash=event.lineage_hash,
    )
    record_measurement(ledger_db, value=6.1, **common)
    with rejected(ledger_db, psycopg.errors.UniqueViolation):
        record_measurement(ledger_db, value=6.1, measurement_version=2, **common)


def test_a_measurement_needs_a_positive_observation_noise(ledger_db, user_id):
    """A zero R would claim a perfect sensor and make Layer E's gain
    singular. The DataMap lists R_cov as a core field of measurements_y and
    of nothing else -- controls carry no noise at all, which is the
    structural form of "controls are never treated as measurements"."""
    event = _log_meal(
        ledger_db, user_id, source_event_id="MEAL-R",
        occurred_at=datetime(2026, 9, 8, 12, 0, tzinfo=UTC),
        ingested_at=datetime(2026, 9, 8, 12, 5, tzinfo=UTC),
    )
    with rejected(ledger_db, psycopg.errors.CheckViolation):
        record_measurement(
            ledger_db,
            user_id=user_id, measurement_type="weight", value=70.0, unit="kg",
            r_cov=0.0, source_event_id=event.event_uuid,
            effective_at=datetime(2026, 9, 8, 12, 0, tzinfo=UTC),
            knowledge_at=datetime(2026, 9, 8, 12, 5, tzinfo=UTC),
            ingested_at=datetime(2026, 9, 8, 12, 5, tzinfo=UTC),
            support_class=SUPPORT_POINT,
            parent_event_hash=event.lineage_hash,
        )


def test_controls_u_has_no_place_to_put_observation_noise(ledger_db):
    """The prohibition made structural rather than documentary: there is no
    R_cov column on controls_u, so no code path can turn a logged control
    into an observation that updates the filter."""
    with ledger_db.cursor() as cur:
        cur.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema = 'engine_internal' AND table_name = 'controls_u'"
        )
        columns = {row["column_name"] for row in cur.fetchall()}
    assert "r_cov" not in columns
    assert "dose_vector_81" in columns


def test_an_out_of_lag_replay_cannot_be_recorded_without_its_reason(ledger_db, user_id):
    """Step 11 G17: "ReplayJob records policy, approver/reason and horizon";
    RT-05's failure meaning is "Silent partial replay". The database refuses
    a non-routine receipt that does not say why."""
    event = _log_meal(
        ledger_db, user_id, source_event_id="MEAL-LATE",
        occurred_at=datetime(2026, 6, 1, 12, 0, tzinfo=UTC),
        ingested_at=datetime(2026, 9, 8, 12, 0, tzinfo=UTC),
    )
    args = dict(
        user_id=user_id, trigger_event_id=event.event_uuid,
        effective_at=event.effective_at, knowledge_at=event.knowledge_at,
        replay_horizon=timedelta(days=99),
    )
    with rejected(ledger_db, psycopg.errors.CheckViolation):
        open_replay_job(ledger_db, policy="CURRENT_TIME_ANCHOR_ONLY", **args)


def test_a_deep_replay_cannot_be_recorded_without_an_approver(ledger_db, user_id):
    """Step 11 B17: "run an APPROVED deep replay"."""
    event = _log_meal(
        ledger_db, user_id, source_event_id="MEAL-DEEP",
        occurred_at=datetime(2026, 6, 1, 12, 0, tzinfo=UTC),
        ingested_at=datetime(2026, 9, 8, 12, 0, tzinfo=UTC),
    )
    checkpoint = write_checkpoint(
        ledger_db, user_id=user_id,
        effective_at=datetime(2026, 5, 1, tzinfo=UTC),
        knowledge_at=datetime(2026, 5, 1, tzinfo=UTC),
        model_shape_version="S2-219",
    )
    args = dict(
        user_id=user_id, trigger_event_id=event.event_uuid,
        effective_at=event.effective_at, knowledge_at=event.knowledge_at,
        replay_horizon=timedelta(days=99), checkpoint_id=checkpoint,
        reason="retrospective inflammatory lab beyond L_smooth",
    )
    with rejected(ledger_db, psycopg.errors.CheckViolation):
        open_replay_job(ledger_db, policy="DEEP_REPLAY", **args)

    approved = open_replay_job(ledger_db, policy="DEEP_REPLAY", approver="dr-ali", **args)
    assert approved is not None


def test_a_replay_that_revises_history_must_name_its_checkpoint(ledger_db, user_id):
    """Step 3 + I19. Only CURRENT_TIME_ANCHOR_ONLY -- which explicitly
    declines to revise the past -- may have no checkpoint."""
    event = _log_meal(
        ledger_db, user_id, source_event_id="MEAL-NOCP",
        occurred_at=datetime(2026, 9, 1, 12, 0, tzinfo=UTC),
        ingested_at=datetime(2026, 9, 8, 12, 0, tzinfo=UTC),
    )
    args = dict(
        user_id=user_id, trigger_event_id=event.event_uuid,
        effective_at=event.effective_at, knowledge_at=event.knowledge_at,
        replay_horizon=timedelta(days=14),
    )
    with rejected(ledger_db, psycopg.errors.CheckViolation):
        open_replay_job(ledger_db, policy="ROUTINE", **args)

    anchor_only = open_replay_job(
        ledger_db,
        policy="CURRENT_TIME_ANCHOR_ONLY",
        reason="event beyond routine lag; past not revised",
        **args,
    )
    assert anchor_only is not None


def test_a_clock_skewed_event_is_admitted_only_when_it_is_marked(ledger_db, user_id):
    """Section B's effective_at validation: "not after knowledge_at except
    clock-error quarantine". The escape exists, and it is not silent."""
    quarantined = _log_meal(
        ledger_db, user_id, source_event_id="MEAL-SKEW",
        occurred_at=datetime(2026, 9, 9, 12, 0, tzinfo=UTC),
        ingested_at=datetime(2026, 9, 8, 12, 0, tzinfo=UTC),
    )
    assert quarantined.clock_quarantined

    with rejected(ledger_db, psycopg.errors.CheckViolation), ledger_db.cursor() as cur:
        cur.execute(
            """
            INSERT INTO engine_internal.raw_events (
                event_uuid, adapter_source_id, source_event_id, user_id, event_type,
                effective_at, knowledge_at, ingested_at, payload_json,
                clock_quarantined, lineage_hash
            ) VALUES (
                gen_random_uuid(), 'test-adapter', 'MEAL-SKEW-UNMARKED', %s, 'meal',
                '2026-09-09T12:00:00Z', '2026-09-08T12:00:00Z', '2026-09-08T12:00:00Z',
                '{}'::jsonb, FALSE, 'sha256:x'
            )
            """,
            (user_id,),
        )


def test_a_lab_row_cannot_be_stored_with_an_effective_at_that_is_not_its_specimen_time(
    ledger_db, user_id
):
    """The database's own copy of G7's "lab uses specimen_at", so an adapter
    that bypasses resolve_times still cannot date a lab from its upload."""
    with rejected(ledger_db, psycopg.errors.CheckViolation), ledger_db.cursor() as cur:
        cur.execute(
            """
            INSERT INTO engine_internal.raw_events (
                event_uuid, adapter_source_id, source_event_id, user_id, event_type,
                effective_at, knowledge_at, specimen_at, ingested_at, payload_json,
                lineage_hash
            ) VALUES (
                gen_random_uuid(), 'lab-partner-a', 'ORDER-BAD', %s, 'lab',
                '2026-09-20T09:00:00Z', '2026-09-20T09:05:00Z',
                '2026-09-01T07:30:00Z', '2026-09-20T09:05:00Z', '{}'::jsonb,
                'sha256:x'
            )
            """,
            (user_id,),
        )


def test_a_rescored_event_gets_a_new_quality_version_not_an_edit(ledger_db, user_id):
    """DataMap G4: "updates create new quality version".

    raw_events is append-only, so a re-scored photo cannot edit the event it
    describes -- it writes a new verdict and supersedes the old one. That is
    what keeps "what did the engine think of this reading when it acted on
    it?" answerable after the re-score.
    """
    event = _log_meal(
        ledger_db, user_id, source_event_id="MEAL-Q",
        occurred_at=datetime(2026, 9, 8, 12, 0, tzinfo=UTC),
        ingested_at=datetime(2026, 9, 8, 12, 5, tzinfo=UTC),
    )
    first = record_event_quality(
        ledger_db, event_uuid=event.event_uuid, source_type="photo_estimate",
        confidence=0.42, missingness=0.3,
        knowledge_at=datetime(2026, 9, 8, 12, 5, tzinfo=UTC),
        parent_event_hash=event.lineage_hash,
    )
    second = record_event_quality(
        ledger_db, event_uuid=event.event_uuid, source_type="user_confirmed",
        confidence=0.95, missingness=0.0,
        knowledge_at=datetime(2026, 9, 8, 18, 0, tzinfo=UTC),
        parent_event_hash=event.lineage_hash,
    )

    assert (first.quality_version, second.quality_version) == (1, 2)
    assert first.lineage_hash != second.lineage_hash

    active = active_event_quality(ledger_db, event.event_uuid)
    assert active["quality_version"] == 2
    assert active["source_type"] == "user_confirmed"

    with ledger_db.cursor() as cur:
        cur.execute(
            "SELECT quality_version, status, confidence FROM engine_internal.event_quality "
            "WHERE event_uuid = %s ORDER BY quality_version",
            (event.event_uuid,),
        )
        rows = cur.fetchall()
    # the earlier, less confident verdict is superseded -- not deleted
    assert [(r["quality_version"], r["status"]) for r in rows] == [
        (1, "SUPERSEDED"), (2, "ACTIVE"),
    ]
    assert rows[0]["confidence"] == pytest.approx(0.42)


def test_a_confidence_outside_zero_to_one_is_refused(ledger_db, user_id):
    """confidence is a probability; missingness is a fraction. Neither can
    exceed 1 without making Layer E's noise widening meaningless."""
    event = _log_meal(
        ledger_db, user_id, source_event_id="MEAL-Q2",
        occurred_at=datetime(2026, 9, 8, 12, 0, tzinfo=UTC),
        ingested_at=datetime(2026, 9, 8, 12, 5, tzinfo=UTC),
    )
    with rejected(ledger_db, psycopg.errors.CheckViolation):
        record_event_quality(
            ledger_db, event_uuid=event.event_uuid, source_type="photo_estimate",
            confidence=1.4,
            knowledge_at=datetime(2026, 9, 8, 12, 5, tzinfo=UTC),
            parent_event_hash=event.lineage_hash,
        )
