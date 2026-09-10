"""ONB-010 — 'O·O10 Goal Priority Wts'.

The cleanest agreement any O-sheet has with the interface, and one weight
assigned from a question whose answers it cannot use.
"""
import json
from pathlib import Path

import pytest

from sahacore.onboarding import goal_weights as o10

DATA_DIR = Path(__file__).parent.parent / "sahacore" / "data"


def _load(name):
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def sheet():
    return _load("onboarding_o10.json")


# --- provenance and self-agreement ---------------------------------------

def test_every_goal_cites_a_guideline(sheet):
    """Only 'O·O6 Family History' does this too."""
    goals = sheet["goals"]
    assert len(goals) == 8
    for goal in goals:
        assert goal["source"], goal
        assert goal["key_nutrient_targets"]
        assert goal["z_pathways"]

    sources = {g["source"] for g in goals}
    assert "AHA; REDUCE-IT" in sources
    assert "ADA 2024" in sources


def test_the_two_tables_agree_about_the_primary_weight(sheet):
    """Every goal row states 2.5, and the rules table gives Primary = 2.5
    independently."""
    ladder = o10.weight_ladder()
    primary = ladder["Primary (1st selected)"]
    assert primary == 2.5
    for goal in sheet["goals"]:
        assert goal["weight"] == primary


def test_the_ladder_descends_and_its_baseline_is_exactly_one():
    """The baseline being exactly 1.0 is what makes pi_k a multiplier on a
    reward term rather than a rescaling of everything -- a user who ranks
    nothing gets the unweighted reward, not a shrunken one."""
    ladder = o10.weight_ladder()
    assert list(ladder.values()) == [2.5, 2.0, 1.5, 1.0]
    assert ladder["Unselected"] == 1.0

    assert o10.weight_for(1) == 2.5
    assert o10.weight_for(2) == 2.0
    assert o10.weight_for(3) == 1.5
    assert o10.weight_for(None) == 1.0


def test_a_fourth_rank_is_refused_rather_than_folded_into_the_baseline():
    """The sheet gives three rungs and a baseline. Silently treating a
    4th-ranked goal as unselected would be this build deciding that ranking
    it meant nothing."""
    with pytest.raises(ValueError, match="has no rung"):
        o10.weight_for(4)
    with pytest.raises(ValueError, match="has no rung"):
        o10.weight_for(0)


# --- against the UI contract ---------------------------------------------

def test_step_11s_eight_options_are_this_sheets_eight_rows(sheet):
    """THE CLEANEST ALIGNMENT ANY O-SHEET HAS. Six match exactly and two are
    truncations of the UI's label -- 'Immunity & Inflammation Control' ->
    'Immunity & Inflammation'. Nothing is unmatched in either direction."""
    statuses = {g["goal_area"]: g["ui_status"] for g in sheet["goals"]}
    assert len(sheet["step_11_options"]) == 8
    assert sum(1 for s in statuses.values()
               if s == "MATCHES_STEP_11_EXACTLY") == 6
    assert sum(1 for s in statuses.values()
               if s == "PREFIX_OF_A_STEP_11_OPTION") == 2
    assert "MATCHES_NO_STEP_11_OPTION" not in statuses.values()

    assert statuses["Immunity & Inflammation"] == "PREFIX_OF_A_STEP_11_OPTION"
    assert statuses["Fertility & Hormone"] == "PREFIX_OF_A_STEP_11_OPTION"

    # And every Step 11 option resolves.
    for option in sheet["step_11_options"]:
        assert o10.goal_for_ui_option(option).weight == 2.5


def test_step_4s_seven_answers_are_not_goal_areas(sheet):
    """THE FINDING. The rules table assigns the Primary weight -- pi_k = 2.5,
    the heaviest rung -- from the "Highest priority goal from Step 4/11".

    Step 4 offers Weight Loss, Muscle Gain, Energy Levels, Digestive Health,
    Chronic Condition, Manage Benefits and Healthy Aging. Not one is a goal
    area here, so "Weight Loss" has no pi_k, no nutrient targets and no
    Z-pathways.
    """
    step_4 = sheet["step_4_options"]
    assert len(step_4) == 7
    assert "Weight Loss" in step_4

    named = {g["goal_area"] for g in sheet["goals"]}
    assert not (named & set(step_4))

    for answer in step_4:
        with pytest.raises(o10.NotAGoalArea, match="not one of this sheet"):
            o10.goal_for_ui_option(answer)

    # And the rule really does still name Step 4.
    primary = next(r for r in sheet["rules"]
                   if r["priority_level"].startswith("Primary"))
    assert "Step 4" in primary["assignment_rule"]


# --- what the weights multiply -------------------------------------------

def test_the_engine_equation_names_a_term_that_is_an_open_decision(sheet):
    """pi_k is settled and r_k is not. '★ Scoped Builds — LTMLE Bandit' lists
    the bandit's reward proxy as an open founder decision, with its own note
    calling it "the single biggest decision"."""
    primary = next(r for r in sheet["rules"]
                   if r["priority_level"].startswith("Primary"))
    assert "r_k" in primary["engine_equation"]
    assert "pi_k" in primary["engine_equation"]

    scoped = _load("scoped_builds.json")
    reward = [d for d in scoped["open_decisions"]
              if "reward" in d["decision"].lower()]
    assert reward, "the reward proxy is no longer an open founder decision"


def test_the_weighted_reward_composes_and_refuses_what_is_not_a_goal():
    """H1: r_t^pi = SUM(pi_k * r_k). The caller supplies r_k because the
    workbook does not."""
    rewards = {"Heart Health": 1.0, "Bone Health": 1.0, "Gut Health": 1.0}

    # Nothing ranked: every term at the baseline.
    assert o10.weighted_reward(rewards) == pytest.approx(3.0)

    # Ranked first and second: 2.5 + 2.0 + 1.0.
    ranked = o10.weighted_reward(rewards, ("Heart Health", "Bone Health"))
    assert ranked == pytest.approx(5.5)
    assert ranked > o10.weighted_reward(rewards)

    with pytest.raises(o10.NotAGoalArea):
        o10.weighted_reward({"Weight Loss": 1.0})


def test_the_catalogue_reads_back_as_objects():
    goals = o10.goal_areas()
    assert len(goals) == 8
    heart = o10.goal_for_ui_option("Heart Health")
    assert heart.z_pathways == ("Z7", "Z12", "Z13")
    assert heart.source == "AHA; REDUCE-IT"
    assert "Omega-3" in heart.key_nutrient_targets
