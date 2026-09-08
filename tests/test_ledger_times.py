"""The two clocks, against 'Replay Contract' section A step 1 and section B.

Acceptance test cell G7, in full: "effective_at<=knowledge_at; lab uses
specimen_at; timezone normalized to UTC" -- one test each, plus the named
clock-error escape and the "do not use as" prohibitions from section B.
"""
from datetime import datetime, timedelta, timezone

import pytest

from sahacore.ledger.times import (
    ClockResolutionError,
    lag,
    resolve_times,
)

UTC = timezone.utc
AMMAN = timezone(timedelta(hours=3))  # Asia/Amman standard offset


def test_a_lab_takes_its_effective_at_from_specimen_at():
    """B21: "Laboratory default: specimen_at." The lab was drawn on the 1st
    and uploaded on the 20th; physiology was affected on the 1st."""
    times = resolve_times(
        event_type="lab",
        specimen_at=datetime(2026, 9, 1, 7, 30, tzinfo=UTC),
        occurred_at=datetime(2026, 9, 20, 9, 0, tzinfo=UTC),
        ingested_at=datetime(2026, 9, 20, 9, 5, tzinfo=UTC),
    )
    assert times.effective_at == datetime(2026, 9, 1, 7, 30, tzinfo=UTC)
    assert times.knowledge_at == datetime(2026, 9, 20, 9, 5, tzinfo=UTC)
    assert not times.clock_quarantined


def test_a_lab_without_a_specimen_time_is_refused():
    """G23 warns that observed_at is not "a universal replacement for
    specimen_at", and B21's "do not use as" for effective_at is "The date the
    result was uploaded". With neither available there is no admissible
    physiological time, so the event must be refused rather than dated from
    its upload."""
    with pytest.raises(ClockResolutionError, match="specimen_at"):
        resolve_times(
            event_type="lab",
            observed_at=datetime(2026, 9, 20, 9, 0, tzinfo=UTC),
            ingested_at=datetime(2026, 9, 20, 9, 5, tzinfo=UTC),
        )


def test_a_non_lab_event_prefers_the_adapter_defined_physiological_time():
    """A7: "otherwise the adapter-defined event time"."""
    times = resolve_times(
        event_type="meal",
        adapter_effective_at=datetime(2026, 9, 8, 12, 0, tzinfo=UTC),
        occurred_at=datetime(2026, 9, 8, 18, 0, tzinfo=UTC),
        ingested_at=datetime(2026, 9, 8, 18, 5, tzinfo=UTC),
    )
    assert times.effective_at == datetime(2026, 9, 8, 12, 0, tzinfo=UTC)


def test_a_non_lab_event_falls_back_to_occurred_at_then_observed_at():
    """B21 for occurred_at; B23 for observed_at, which "may equal
    effective_at for real-time sensors"."""
    ingested = datetime(2026, 9, 8, 18, 5, tzinfo=UTC)

    by_occurrence = resolve_times(
        event_type="meal",
        occurred_at=datetime(2026, 9, 8, 12, 0, tzinfo=UTC),
        observed_at=datetime(2026, 9, 8, 17, 0, tzinfo=UTC),
        ingested_at=ingested,
    )
    assert by_occurrence.effective_at == datetime(2026, 9, 8, 12, 0, tzinfo=UTC)

    by_observation = resolve_times(
        event_type="wearable",
        observed_at=datetime(2026, 9, 8, 17, 0, tzinfo=UTC),
        ingested_at=ingested,
    )
    assert by_observation.effective_at == datetime(2026, 9, 8, 17, 0, tzinfo=UTC)


def test_an_event_with_no_physiological_time_at_all_is_refused():
    """B21's prohibition, applied to the general case: ingested_at is a
    knowledge clock and may never stand in for an event time."""
    with pytest.raises(ClockResolutionError, match="no physiological time"):
        resolve_times(
            event_type="meal", ingested_at=datetime(2026, 9, 8, 18, 5, tzinfo=UTC)
        )


def test_knowledge_at_is_the_ingestion_time_unless_acceptance_was_later():
    """B22: "When the engine first accepted the information, normally
    ingested_at." An event held and accepted later has a knowledge_at of
    when it was accepted -- that is when the engine could first have acted
    on it."""
    occurred = datetime(2026, 9, 8, 12, 0, tzinfo=UTC)
    ingested = datetime(2026, 9, 8, 12, 5, tzinfo=UTC)
    accepted = datetime(2026, 9, 9, 3, 0, tzinfo=UTC)

    assert resolve_times(
        event_type="meal", occurred_at=occurred, ingested_at=ingested
    ).knowledge_at == ingested
    assert resolve_times(
        event_type="meal", occurred_at=occurred, ingested_at=ingested, accepted_at=accepted
    ).knowledge_at == accepted


# --- G7 clause 3: "timezone normalized to UTC" ----------------------------

def test_timestamps_are_normalised_to_utc():
    """The same instant expressed in Amman local time and in UTC must
    resolve to the same effective_at."""
    local = resolve_times(
        event_type="meal",
        occurred_at=datetime(2026, 9, 8, 15, 0, tzinfo=AMMAN),
        ingested_at=datetime(2026, 9, 8, 15, 5, tzinfo=AMMAN),
    )
    as_utc = resolve_times(
        event_type="meal",
        occurred_at=datetime(2026, 9, 8, 12, 0, tzinfo=UTC),
        ingested_at=datetime(2026, 9, 8, 12, 5, tzinfo=UTC),
    )
    assert local.effective_at == as_utc.effective_at
    assert local.effective_at.tzinfo is UTC
    assert local.effective_at == datetime(2026, 9, 8, 12, 0, tzinfo=UTC)


def test_a_naive_timestamp_is_refused_rather_than_assumed_to_be_utc():
    """Assuming a zone would silently move a meal by up to a day. The event
    is refused so the adapter is fixed instead."""
    with pytest.raises(ClockResolutionError, match="no timezone"):
        resolve_times(
            event_type="meal",
            occurred_at=datetime(2026, 9, 8, 12, 0),
            ingested_at=datetime(2026, 9, 8, 12, 5, tzinfo=UTC),
        )


# --- G7 clause 1: "effective_at<=knowledge_at" ----------------------------

def test_a_normal_event_satisfies_effective_at_before_knowledge_at():
    times = resolve_times(
        event_type="sleep",
        occurred_at=datetime(2026, 9, 8, 2, 0, tzinfo=UTC),
        ingested_at=datetime(2026, 9, 8, 8, 0, tzinfo=UTC),
    )
    assert times.effective_at <= times.knowledge_at
    assert not times.clock_quarantined


def test_a_future_dated_event_is_quarantined_not_dropped_and_not_silently_kept():
    """Section B's validation for effective_at: "not after knowledge_at
    EXCEPT clock-error quarantine". A device with a skewed clock must still
    be admitted -- an event the ledger refuses can never be corrected or
    replayed -- but it is flagged, and sql/009_ledger.sql accepts such a row
    only when the flag is set."""
    times = resolve_times(
        event_type="activity",
        occurred_at=datetime(2026, 9, 9, 12, 0, tzinfo=UTC),
        ingested_at=datetime(2026, 9, 8, 12, 0, tzinfo=UTC),
    )
    assert times.clock_quarantined
    assert times.effective_at > times.knowledge_at


# --- the lag that step 11 classifies -------------------------------------

def test_lag_measures_how_late_the_fact_arrived_in_days():
    """Step 11 compares this against the configured fixed lag L_smooth."""
    assert lag(
        datetime(2026, 9, 1, tzinfo=UTC), datetime(2026, 9, 20, tzinfo=UTC)
    ) == pytest.approx(19.0)
    assert lag(
        datetime(2026, 9, 8, 12, 0, tzinfo=UTC), datetime(2026, 9, 8, 12, 0, tzinfo=UTC)
    ) == 0.0
