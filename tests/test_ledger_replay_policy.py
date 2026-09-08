"""The fixed-lag policy and evidence-support times -- the two pure decisions
behind 'Replay Contract' steps 3 and 11.
"""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from sahacore.ledger.jobs import (
    CURRENT_TIME_ANCHOR_ONLY,
    DEEP_REPLAY,
    ROUTINE,
    replay_policy,
)
from sahacore.ledger.measurements import (
    SUPPORT_POINT,
    SUPPORT_WINDOWED,
    SupportWindowError,
    earliest_evidence_support_start,
    evidence_support_start,
)

UTC = timezone.utc
POLICY_FILE = Path(__file__).parent.parent / "sahacore" / "data" / "ledger_replay_policy.json"


@pytest.fixture(scope="module")
def policy() -> dict:
    rows = json.loads(POLICY_FILE.read_text(encoding="utf-8"))
    assert len(rows) == 1, "exactly one lag policy is seeded"
    return rows[0]


# --- step 11: the three-way policy ----------------------------------------

def test_an_event_inside_the_configured_lag_is_a_routine_replay():
    """B17: "Inside the configured fixed lag, use routine replay.\""""
    assert replay_policy(lag_days=3.0, routine_lag_days=14.0) == ROUTINE


def test_the_boundary_day_is_still_inside_the_lag():
    """The window is L_smooth days of history, so a fact exactly L_smooth
    days late is the last one the routine buffer covers."""
    assert replay_policy(lag_days=14.0, routine_lag_days=14.0) == ROUTINE


def test_an_event_outside_the_lag_is_never_quietly_routine():
    """B17's prohibition, and RT-05's failure meaning: "Silent partial
    replay". There is deliberately no branch that returns ROUTINE here."""
    for approved in (True, False):
        assert (
            replay_policy(lag_days=14.001, routine_lag_days=14.0, deep_replay_approved=approved)
            != ROUTINE
        )


def test_outside_the_lag_an_approved_deep_replay_is_the_only_way_to_revise_history():
    """B17: "run an APPROVED deep replay from a durable checkpoint or record
    CURRENT_TIME_ANCHOR_ONLY". Without approval the engine must decline to
    revise the past and say so."""
    assert (
        replay_policy(lag_days=45.0, routine_lag_days=14.0, deep_replay_approved=True)
        == DEEP_REPLAY
    )
    assert (
        replay_policy(lag_days=45.0, routine_lag_days=14.0, deep_replay_approved=False)
        == CURRENT_TIME_ANCHOR_ONLY
    )


def test_the_seeded_window_sits_inside_the_published_parameter_range(policy):
    """'P1 Parameters 134+' row 129 gives L_smooth as 7-14 days. The seeded
    value must lie inside its own published range, and must name it."""
    assert policy["l_smooth_min_days"] == 7.0
    assert policy["l_smooth_max_days"] == 14.0
    assert policy["l_smooth_min_days"] <= policy["l_smooth_days"] <= policy["l_smooth_max_days"]
    assert "129" in policy["param_row"] and "L_smooth" in policy["param_row"]


def test_the_seeded_window_covers_the_release_test_the_contract_names(policy):
    """RT-01 (RELEASE_BLOCKING) is "Late inflammatory lab inside 14-day lag".
    A configured window below 14 days would classify that scenario as
    out-of-lag and the release test could not run as written."""
    assert replay_policy(lag_days=14.0, routine_lag_days=policy["l_smooth_days"]) == ROUTINE


def test_the_window_is_not_hardcoded_in_the_ledger_package(policy):
    """Standing convention in this codebase: a tunable is read from the
    registry, never written into a .py file. L_smooth is tunable ("Tune
    against latency and retrospective accuracy"), so no ledger module may
    contain its value as a literal -- `replay_policy` takes it as an
    argument and `routine_lag_days` reads it from the seeded table.

    Checked by parsing each module rather than by scanning text, so the
    docstrings that cite the parameter row on purpose do not trip it."""
    import ast

    window = policy["l_smooth_days"]
    ledger_dir = Path(__file__).parent.parent / "sahacore" / "ledger"
    for module in sorted(ledger_dir.glob("*.py")):
        tree = ast.parse(module.read_text(encoding="utf-8"))
        literals = [
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, (int, float))
            and not isinstance(node.value, bool)
        ]
        assert window not in literals, f"{module.name} hardcodes the lag window {window}"


# --- step 3: evidence-support times ---------------------------------------

def test_a_point_measurement_supports_only_its_own_instant():
    """Step 3: "For point measurements this may equal effective_at.\""""
    t = datetime(2026, 9, 8, 7, 0, tzinfo=UTC)
    assert evidence_support_start(effective_at=t, support_class=SUPPORT_POINT) == t


def test_a_windowed_measurement_supports_a_span_before_its_specimen_time():
    """Step 3: "for E_WINDOWED measurements it precedes specimen_at." An
    HbA1c drawn today is evidence about the ~90 days before today."""
    drawn = datetime(2026, 9, 8, 7, 0, tzinfo=UTC)
    start = evidence_support_start(
        effective_at=drawn, support_class=SUPPORT_WINDOWED, support_window_days=90.0
    )
    assert start == drawn - timedelta(days=90)
    assert start < drawn


def test_a_windowed_measurement_without_its_window_is_refused():
    """Defaulting the window to zero would collapse the measurement to a
    point and leave the very window it describes unrevised -- step 3's named
    failure: "A checkpoint after any time represented by the new observation
    already contains the wrong inferred history.\""""
    with pytest.raises(SupportWindowError):
        evidence_support_start(
            effective_at=datetime(2026, 9, 8, tzinfo=UTC), support_class=SUPPORT_WINDOWED
        )


def test_the_replay_rewinds_to_the_earliest_support_time_across_the_evidence():
    """Step 3 rewinds to "the EARLIEST evidence-support time", not to each
    measurement's own: a batch containing one windowed assay must rewind
    behind that assay's whole window."""

    class Stub:
        def __init__(self, start):
            self.evidence_support_start = start

    point = Stub(datetime(2026, 9, 8, tzinfo=UTC))
    windowed = Stub(datetime(2026, 6, 10, tzinfo=UTC))
    assert earliest_evidence_support_start([point, windowed]) == windowed.evidence_support_start
