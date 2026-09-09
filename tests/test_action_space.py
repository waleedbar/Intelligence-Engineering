"""The Layer H action space: 127 arms, 7 information actions, 4 phases.

Source: v39sEng2.xlsx, sheet 'Action_Space'.

'★ Build Guide Python' step 2 names Action_Space among the registries that
must load before the equations run. The care in these tests is about three
boundaries the sheet draws and code could easily blur: outcome-bearing arms
against information requests, the ontology against the activatable set, and
the prose safety note against the actual VETO registry.
"""
import json
from pathlib import Path

import pytest

DATA_DIR = Path(__file__).parent.parent / "sahacore" / "data"


@pytest.fixture(scope="module")
def space() -> dict:
    return json.loads((DATA_DIR / "action_space_127.json").read_text(encoding="utf-8"))


# --- extraction fidelity ---------------------------------------------------

def test_all_127_actions_with_contiguous_ids(space):
    assert len(space["actions"]) == 127
    assert sorted(a["action_id"] for a in space["actions"]) == list(range(1, 128))


def test_the_category_breakdown_matches_the_sheets_own_line(space):
    """The sheet states it: "81 nutrient (41 increase + 40 decrease) + 20
    activity + 15 sleep/stress + 11 timing = 127". Checked against that claim
    rather than against the extraction itself."""
    from sahacore.data.build_action_space import (
        DECLARED_CATEGORY_COUNTS, DECLARED_NUTRIENT_VERBS)

    counts: dict[str, int] = {}
    for a in space["actions"]:
        counts[a["category"]] = counts.get(a["category"], 0) + 1
    assert counts == DECLARED_CATEGORY_COUNTS
    assert sum(DECLARED_CATEGORY_COUNTS.values()) == 127

    verbs: dict[str, int] = {}
    for a in space["actions"]:
        if a["category"] == "Nutrient":
            verbs[a["action"].split()[0]] = verbs.get(a["action"].split()[0], 0) + 1
    assert verbs == DECLARED_NUTRIENT_VERBS


# --- the three boundaries --------------------------------------------------

def test_the_information_actions_are_not_among_the_127(space):
    """The sheet says this in capitals: "INFORMATION ACTIONS — SEPARATE VOI
    POLICY (NOT PART OF THE 127 OUTCOME-BEARING ACTIONS)". They are kept in
    their own table so the bandit cannot rank "resync your wearable" against
    "increase protein" by iterating one list."""
    info = space["info_actions"]
    assert len(info) == 7
    assert [i["info_id"] for i in info] == [f"INFO-{n:02d}" for n in range(1, 8)]
    assert len(space["actions"]) == 127          # unchanged by their presence

    action_ids = {str(a["action_id"]) for a in space["actions"]}
    assert not action_ids & {i["info_id"] for i in info}


def test_arm_127_is_held_and_the_hold_says_why(space):
    """The sheet's Phase 3 cell instructs, in the source data itself:

        "Action 127 (INCREASE Dietary Nitrate, nutrient 81) stays inactive
         pending VN-01…VN-07 clinical sign-off ... This is a deliberate
         safety hold, not an incomplete rollout. Do NOT write an acceptance
         test asserting 127 active arms at Phase 3, and do NOT activate arm
         127 to make the count 'full'."

    So this build keeps all 127 rows in the ontology and records the hold
    verbatim on the one arm it names. No test here asserts 127 active arms.
    """
    held = [a for a in space["actions"] if a["activation_hold"]]
    assert len(held) == 1
    assert held[0]["action_id"] == 127
    assert "Dietary Nitrate" in held[0]["action"]
    assert "deliberate safety hold" in held[0]["activation_hold"]
    assert "VN-01" in held[0]["activation_hold"]


def test_the_phase_schedule_tops_out_at_126_activatable_not_127(space):
    """The consequence of that hold, stated as the sheet states it: Phase 3's
    cumulative count is "126 / 127 — full ACTIVATABLE set, NOT the full
    ontology"."""
    phases = space["phases"]
    assert len(phases) == 4
    assert [p["cumulative_arms"].split()[0] for p in phases] == ["22", "90", "116", "126"]
    assert "NOT the full ontology" in phases[-1]["cumulative_arms"]


def test_the_veto_cross_reference_is_prose_and_is_not_a_foreign_key(space):
    """The sheet is explicit about where the gate comes from: "Layer H builds
    the action x active-rule gate from the versioned VETO registry at load
    time. Do not hard-code."

    So this column stays the note it is -- "VETO: warfarin (rule #1)",
    "Caution: oxalate nephropathy at >2g/d", "None at dietary doses" -- and
    engine_internal.veto_drug_nutrient is the authority. Parsing "#1" into a
    foreign key would hard-code exactly what the sheet forbids, and against
    the OLD source_rule_id numbering rather than the repaired canonical one.
    """
    refs = [a["veto_cross_ref"] for a in space["actions"] if a["veto_cross_ref"]]
    assert len(refs) > 100
    assert any(r.startswith("VETO:") for r in refs)
    assert any(r.startswith("Caution:") for r in refs)
    assert any("None" in r for r in refs)

    for a in space["actions"]:
        assert set(a) & {"veto_rule_id", "veto_rule_ids"} == set(), (
            "the cross-reference must not have been parsed into keys")


def test_the_warfarin_note_points_at_the_old_numbering(space):
    """Concretely why parsing it would be wrong. Action 6 reads "VETO:
    warfarin (rule #1)". That "#1" is a source_rule_id, of which 20 are
    duplicated across 339 rules -- it is not the canonical VETO-DN-0001 key,
    even though it happens to coincide for this one rule."""
    a = next(x for x in space["actions"] if x["action_id"] == 6)
    assert a["action"] == "INCREASE Vitamin K2"
    assert a["veto_cross_ref"] == "VETO: warfarin (rule #1)"


# --- the extractor refuses bad data ----------------------------------------

def test_the_builder_refuses_to_move_the_safety_hold(space):
    """The guard, proven. Attaching the hold to a different arm -- or to none
    -- must fail rather than quietly ship a nitrate arm as activatable."""
    from sahacore.data.build_action_space import check

    moved = json.loads(json.dumps(space))
    moved["actions"][126]["activation_hold"] = None
    moved["actions"][0]["activation_hold"] = "held for no stated reason"
    with pytest.raises(SystemExit, match="activation_hold"):
        check(moved)


def test_the_builder_refuses_a_missing_arm(space):
    from sahacore.data.build_action_space import check

    short = json.loads(json.dumps(space))
    short["actions"] = short["actions"][:-1]
    with pytest.raises(SystemExit, match="1..127"):
        check(short)
