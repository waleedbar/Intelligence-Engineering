"""Layers G and H, and the prerequisite that belongs to this phase.

Source: '★ Scoped Builds — LTMLE Bandit' -- manifest order 6.

Both scoped builds are years of dependency away. What is not far away is
shared prerequisite 1, which says the online engine must ALREADY be writing
a per-user longitudinal outcome log. That sentence is about the ledger, and
the ledger is this build's work, so it is tested here rather than deferred
to the sheet's own phase.
"""
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "sahacore" / "data"


@pytest.fixture(scope="module")
def scoped() -> dict:
    return json.loads((DATA_DIR / "scoped_builds.json").read_text(encoding="utf-8"))


# --- the contracts ---------------------------------------------------------

def test_two_scoped_builds_each_with_a_full_contract(scoped):
    """A scoped build without an I/O contract or acceptance criteria is a
    description, not a build."""
    assert [i["item_id"] for i in scoped["items"]] == ["ITEM 1", "ITEM 2"]
    required = {"Execution plane / cadence", "What & why", "Algorithm (buildable)",
                "I/O contract — INPUTS", "I/O contract — OUTPUTS",
                "Acceptance criteria", "Effort / risk"}
    for item in scoped["items"]:
        assert required <= {a["name"] for a in item["attributes"]}, item["item_id"]


def test_the_two_run_on_different_planes(scoped):
    """The distinction the sheet leads with: 'These two are NOT per-tick
    drop-ins like Layers A-F.' LTMLE is offline batch; the bandit is hybrid,
    with cheap inline selection and an offline learner."""
    planes = {}
    for item in scoped["items"]:
        plane = next(a["value"] for a in item["attributes"]
                     if a["name"] == "Execution plane / cadence")
        planes[item["item_id"]] = plane
    assert "OFFLINE BATCH" in planes["ITEM 1"]
    assert "NOT per-user, NOT per-tick" in planes["ITEM 1"]
    assert "HYBRID" in planes["ITEM 2"]


def test_eight_open_founder_decisions_each_with_a_reason(scoped):
    """'required BEFORE code starts'. None is answered here -- answering one
    would be inventing product policy."""
    decisions = scoped["open_decisions"]
    assert [d["number"] for d in decisions] == list(range(1, 9))
    for decision in decisions:
        assert decision["decision"] and decision["why_it_matters"]


def test_the_reward_proxy_is_flagged_as_the_biggest_decision(scoped):
    """Decision 5, and the sheet says so twice -- once in the decision table
    and once as an inline warning on item 2."""
    fifth = next(d for d in scoped["open_decisions"] if d["number"] == 5)
    assert "REWARD proxy" in fifth["decision"]
    assert "single biggest decision" in fifth["why_it_matters"]

    item2 = next(i for i in scoped["items"] if i["item_id"] == "ITEM 2")
    warnings = [n["text"] for n in item2["notes"] if "REWARD DESIGN" in n["text"]]
    assert warnings, "item 2's inline reward-design warning was dropped"


# --- the prerequisite that is about today ---------------------------------

def test_prerequisite_one_says_the_log_must_already_be_written(scoped):
    """The wording is the whole reason this sheet is imported in Phase 1.
    'a per-user longitudinal record the ONLINE engine must already be
    writing' -- present tense, about the engine being built now."""
    first = next(p for p in scoped["prerequisites"] if p["number"] == "1")
    assert first["name"] == "Historical outcome log"
    assert "already be writing" in first["detail"]

    eighth = next(d for d in scoped["open_decisions"] if d["number"] == 8)
    assert "outcome log is being written" in eighth["decision"]
    assert "nothing offline can start without it" in eighth["why_it_matters"]


def test_the_ledger_does_not_yet_write_that_log(scoped):
    """THE FINDING, pinned as a fact about the repo rather than an opinion.

    '★ Build Guide Python' step 1 lists what the ledger must hold: raw_events,
    event_quality, controls_u, measurements_y, bitemporal stamps, checkpoints,
    lineage hashes and replay-job keys. This build has all of them and nothing
    else -- so it matches its own step exactly, and still does not satisfy
    this prerequisite.

    The battery names the missing pieces from the other direction: I12,
    BLOCKING, asserts over served_action_event and served_warning_event.
    Neither table exists here.

    If this test starts failing because the tables appeared, that is the
    prerequisite being met -- update the status in build_scoped_builds.py.
    """
    first = next(p for p in scoped["prerequisites"] if p["number"] == "1")
    assert first["status"] == "MISSING"
    assert first["satisfied_by"] is None

    schema = "\n".join(
        path.read_text(encoding="utf-8") for path in sorted((ROOT / "sql").glob("*.sql")))
    for expected in ("engine_internal.raw_events", "engine_internal.controls_u",
                     "engine_internal.measurements_y",
                     "engine_internal.checkpoint_state"):
        assert f"CREATE TABLE IF NOT EXISTS {expected}" in schema, expected
    for absent in ("served_action_event", "served_warning_event",
                   "outcome_panel"):
        assert f"CREATE TABLE IF NOT EXISTS engine_internal.{absent}" not in schema


def test_the_battery_names_the_served_event_tables(scoped):
    """Corroboration from a second sheet: the served-event log is not an idea
    of this build's, it is what I12 asserts over."""
    battery = json.loads(
        (DATA_DIR / "validation_battery.json").read_text(encoding="utf-8"))
    i12 = next(t for t in battery["tests"] if t["test_id"] == "I12")
    assert i12["gate"] == "BLOCKING"
    assert "served_action_event" in i12["pass_criterion"]
    assert "served_warning_event" in i12["pass_criterion"]


def test_the_firewall_prerequisite_is_the_one_already_met(scoped):
    """Prerequisite 2 -- 'Both train server-side' with LTMLE's served outputs
    to H being effect estimates, never raw clinical values. That is the T-1
    firewall, which exists and is tested."""
    second = next(p for p in scoped["prerequisites"] if p["number"] == "2")
    assert second["status"] == "IN_PLACE"
    assert second["satisfied_by"] == "tests/test_firewall.py"
    assert (ROOT / second["satisfied_by"]).exists()


def test_shadow_mode_is_not_applicable_until_something_is_served(scoped):
    """Prerequisite 3 governs serving. Nothing is served -- no API, no
    service, no deployment -- so claiming it either way would be false."""
    third = next(p for p in scoped["prerequisites"] if p["number"] == "3")
    assert third["status"] == "NOT_APPLICABLE_YET"
    assert "do NOT serve to users" in third["detail"]
