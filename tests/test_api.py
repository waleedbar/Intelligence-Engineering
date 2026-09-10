"""The HTTP surface: liveness, readiness, and event ingestion.

Driven through Starlette's TestClient -- which is an httpx.Client over an
ASGI transport -- rather than a live socket, so these need no port, no
running server and no cleanup, and they exercise the real application object
rather than a test double of it.

The health tests run everywhere. The ingestion tests need a database and
skip without one, the same way the ledger's own acceptance tests do.
"""
import os
import uuid

import httpx
import pytest
from fastapi.testclient import TestClient

from sahacore.api import app

DATABASE_CONFIGURED = bool(os.environ.get("DATABASE_URL"))
needs_database = pytest.mark.skipif(
    not DATABASE_CONFIGURED, reason="DATABASE_URL is not set")


@pytest.fixture
def client():
    with TestClient(app, base_url="http://sahacore") as client:
        # A real HTTP client against the real app, not a mock of either.
        assert isinstance(client, httpx.Client)
        yield client


def an_event(**overrides):
    """A valid event, unique per call unless told otherwise.

    `occurred_at` is not optional in practice for a meal: 'Replay Contract'
    section B refuses to resolve an event that carries no physiological
    time, because a filter updated at the moment of DELIVERY rather than the
    moment of OBSERVATION is measuring the network. A real adapter always
    sends one.
    """
    event = {
        "adapter_source_id": "test-adapter",
        "source_event_id": f"evt-{uuid.uuid4()}",
        "user_id": str(uuid.uuid4()),
        "event_type": "meal",
        "payload": {"kcal": 640, "note": "lunch"},
        "occurred_at": "2026-09-10T12:30:00Z",
    }
    event.update(overrides)
    return event


# --- liveness -------------------------------------------------------------

def test_health_is_200_whatever_the_database_is_doing(client):
    """A liveness probe that fails on a database blip restarts a perfectly
    good container and makes the outage worse. So /health reports the
    database's condition in the body and still answers 200."""
    response = client.get("/health")
    assert response.status_code == 200

    body = response.json()
    assert body["service"] == "sahacore"
    assert body["status"] in {"ok", "degraded"}
    assert "database" in body


def test_health_reports_what_it_found_rather_than_asserting_it(client):
    body = client.get("/health").json()["database"]
    assert body["configured"] is DATABASE_CONFIGURED
    if DATABASE_CONFIGURED:
        assert body["reachable"] is True
        assert body["migrations_applied"] > 0
        assert body["detail"] is None
    else:
        assert body["reachable"] is False
        assert body["migrations_applied"] is None
        assert body["detail"] == "DATABASE_URL is not set"


def test_a_failing_probe_reports_a_class_name_not_a_connection_string(monkeypatch):
    """A health endpoint is often the least authenticated thing a service
    exposes, and a psycopg connection error carries the DSN it failed on.
    So the probe reports the exception's CLASS NAME and nothing else.

    Forced here rather than waited for: this is the branch that only runs
    when the database is already broken.
    """
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://sahacore:hunter2@nonexistent.invalid:5432/saha")

    with TestClient(app, base_url="http://sahacore") as client:
        body = client.get("/health").json()

    assert body["status"] == "degraded"
    database = body["database"]
    assert database["configured"] is True
    assert database["reachable"] is False

    # The class name, and nothing that could carry the DSN.
    assert " " not in database["detail"]
    rendered = repr(body).lower()
    for secret in ("hunter2", "postgresql://", "nonexistent.invalid", "5432"):
        assert secret not in rendered


# --- readiness ------------------------------------------------------------

def test_readiness_answers_503_when_the_ledger_cannot_serve(client):
    """Readiness is a different question from liveness: it decides whether
    traffic should be sent here. An ingestion request against an unmigrated
    database is a 500 waiting to happen, so this refuses traffic first."""
    response = client.get("/health/ready")
    body = response.json()

    if DATABASE_CONFIGURED:
        assert response.status_code == 200
        assert body["status"] == "ready"
        assert body["database"]["migrations_applied"] > 0
    else:
        assert response.status_code == 503
        assert body["status"] == "not_ready"


def test_liveness_and_readiness_disagree_when_there_is_no_database(client):
    """The whole reason there are two endpoints. Without a database the
    process is alive and must not be restarted, and is not ready and must
    not be sent traffic."""
    if DATABASE_CONFIGURED:
        pytest.skip("both are healthy when a database is configured")
    assert client.get("/health").status_code == 200
    assert client.get("/health/ready").status_code == 503


# --- the wire contract ----------------------------------------------------

def test_the_caller_cannot_set_the_knowledge_clock():
    """THE ONE PLACE THIS API DEPARTS FROM ingest_event's SIGNATURE.

    `ingested_at` records when THIS SYSTEM learned a fact. A caller able to
    set it could backdate a late delivery so a replay believes the engine
    knew something it did not. It is stamped server-side and is not a field
    on the request model at all.
    """
    from sahacore.api.schemas import EventIn

    assert "ingested_at" not in EventIn.model_fields

    # Every other clock IS the source's to state: those describe when the
    # observation happened, not when we heard about it.
    for clock in ("occurred_at", "specimen_at", "observed_at",
                  "adapter_effective_at", "accepted_at"):
        assert clock in EventIn.model_fields


def test_an_unknown_field_is_rejected_rather_than_ignored(client):
    """Including ingested_at, which is the one a caller is most likely to
    try. Pydantic rejects it because ingest_event is called with **model_dump
    -- an ignored field would silently become a fact nobody sent."""
    response = client.post(
        "/v1/events", json=an_event(ingested_at="2020-01-01T00:00:00Z"))
    assert response.status_code == 422


@pytest.mark.parametrize("missing", [
    "adapter_source_id", "source_event_id", "user_id", "event_type", "payload",
])
def test_a_missing_required_field_is_a_422(client, missing):
    event = an_event()
    del event[missing]
    assert client.post("/v1/events", json=event).status_code == 422


def test_a_malformed_user_id_is_a_422(client):
    response = client.post("/v1/events", json=an_event(user_id="not-a-uuid"))
    assert response.status_code == 422


def test_ingestion_refuses_rather_than_500s_without_a_database(client):
    """503, not 500: the request is fine and the service cannot serve it."""
    if DATABASE_CONFIGURED:
        pytest.skip("a database is configured")
    response = client.post("/v1/events", json=an_event())
    assert response.status_code == 503
    assert "DATABASE_URL" in response.json()["detail"]


@needs_database
def test_an_event_with_no_physiological_time_is_a_422_not_a_500(client):
    """The ledger refuses to resolve an event whose only timestamp is its
    delivery -- ingestion time is explicitly not a physiological one. That is
    a malformed event, so it is the caller's 422 rather than our 500, and the
    ledger's own message says which clock is missing.
    """
    timeless = an_event()
    del timeless["occurred_at"]

    response = client.post("/v1/events", json=timeless)
    assert response.status_code == 422

    detail = response.json()["detail"]
    assert "occurred_at" in detail
    assert "ingested_at is explicitly not one" in detail


# --- ingestion, against a real ledger -------------------------------------

@needs_database
def test_a_new_event_is_created_and_a_replay_of_it_is_not(client):
    """HTTP CARRIES THE LEDGER'S IDEMPOTENCY.

    'Replay Contract' section F, RT-02 (RELEASE_BLOCKING) requires a second
    delivery of the same fact to be a no-op. An adapter that retries needs to
    be able to tell that its retry was absorbed rather than double-counted,
    so the second delivery answers 200 rather than 201.
    """
    event = an_event()

    first = client.post("/v1/events", json=event)
    assert first.status_code == 201
    created = first.json()
    assert created["is_duplicate"] is False

    second = client.post("/v1/events", json=event)
    assert second.status_code == 200
    duplicate = second.json()
    assert duplicate["is_duplicate"] is True

    # The second response describes the ORIGINAL row, not the resubmission.
    assert duplicate["event_uuid"] == created["event_uuid"]
    assert duplicate["ingest_seq"] == created["ingest_seq"]
    assert duplicate["lineage_hash"] == created["lineage_hash"]


@needs_database
def test_a_duplicate_carrying_a_different_payload_changes_nothing(client):
    """"never overwrite the old fact". A second delivery under the same
    identifiers does not update the row and does not report the new payload
    back as though it had been accepted."""
    event = an_event()
    created = client.post("/v1/events", json=event).json()

    rewritten = dict(event, payload={"kcal": 99999, "note": "tampered"})
    second = client.post("/v1/events", json=rewritten)

    assert second.status_code == 200
    assert second.json()["lineage_hash"] == created["lineage_hash"]


@needs_database
def test_the_event_uuid_is_derived_not_random(client):
    """Same source identifiers, same primary key -- in any process and after
    a rebuild from the same facts. That is what makes a duplicate detectable
    across a replay."""
    from sahacore.ledger.ingest import event_uuid_for

    event = an_event()
    created = client.post("/v1/events", json=event).json()

    assert created["event_uuid"] == str(event_uuid_for(
        event["adapter_source_id"], event["source_event_id"]))


@needs_database
def test_two_different_events_get_different_rows(client):
    first = client.post("/v1/events", json=an_event()).json()
    second = client.post("/v1/events", json=an_event()).json()

    assert first["event_uuid"] != second["event_uuid"]
    assert second["ingest_seq"] > first["ingest_seq"]


@needs_database
def test_the_event_actually_reaches_the_table(client):
    """The endpoint commits. A response that reported success without a
    committed row would pass every test above."""
    from sahacore.db import get_connection

    event = an_event()
    created = client.post("/v1/events", json=event).json()

    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT event_type, payload_json, ingested_at "
                "FROM engine_internal.raw_events WHERE event_uuid = %s",
                (created["event_uuid"],))
            row = cur.fetchone()
    finally:
        conn.close()

    assert row is not None
    assert row["event_type"] == event["event_type"]
    assert row["payload_json"] == event["payload"]
    # Stamped by the server, so it is set even though no caller sent one.
    assert row["ingested_at"] is not None
