"""'O·Step-by-Step Questions' — the onboarding UI contract, manifest order 70.

This sheet is what makes cross-sheet checking possible at all. Until it was
imported, an O-module's inputs could only be checked against the same
O-sheet's own Variables column -- which is the sheet agreeing with itself.

So most of these tests are not about this sheet. They hold it against the
O-sheets that consume it, in both directions.
"""
import json
from pathlib import Path

import pytest

DATA_DIR = Path(__file__).parent.parent / "sahacore" / "data"


def _load(name):
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def steps():
    return _load("step_questions.json")


@pytest.fixture(scope="module")
def o3():
    return _load("onboarding_o3.json")


@pytest.fixture(scope="module")
def o4():
    return _load("onboarding_o4.json")


def question(steps, variable):
    matching = [q for q in steps["questions"] if q["variable"] == variable]
    assert len(matching) == 1, f"{variable}: {len(matching)} rows"
    return matching[0]


# --- the sheet itself -----------------------------------------------------

def test_all_twelve_steps_are_present_and_numbered(steps):
    """It calls itself "Onboarding Questionnaire -- All 12 Steps"."""
    assert [s["step_number"] for s in steps["steps"]] == list(range(1, 13))
    for step in steps["steps"]:
        assert step["title"]


def test_every_question_reaches_a_named_destination(steps):
    """A question whose answer nothing reads is a question not worth asking.
    The Maps To column names the consumer for all of them."""
    for q in steps["questions"]:
        assert q["targets"], q
        assert q["variable"]


def test_every_step_has_at_least_one_question(steps):
    numbered = {q["step_number"] for q in steps["questions"]}
    assert numbered == set(range(1, 13))


def test_options_are_split_only_where_the_cell_lists_choices(steps):
    """'Low-carb/Keto' and 'Yoga/Tai Chi' contain slashes and are single
    options, so the split is on a SPACED slash. And a cell describing a
    control -- 'Numeric entry', 'Slider 0-8+ hours' -- yields no options at
    all, because inventing them would be inventing the UI."""
    diet = question(steps, "diet_pattern")
    assert "Low-carb/Keto" in diet["answer_options"]
    practices = question(steps, "stress_practice")
    assert "Yoga/Tai Chi" in practices["answer_options"]

    for q in steps["questions"]:
        if q["is_choice"]:
            assert len(q["answer_options"]) > 1, q
        else:
            assert q["answer_options"] == [], q
        # The raw cell is always kept, so nothing is lost either way.
        assert q["answer_options_text"]


# --- what it corroborates: O4 ---------------------------------------------

def test_the_pss10_reverse_set_is_stated_three_times_and_agrees(steps, o4):
    """THE STRONGEST CROSS-CHECK IN THE BUILD SO FAR.

    The workbook states which PSS-10 items are reverse-scored in three
    independently written places:

      1. 'O·O4 Stress Index' Reverse? column
      2. O4.1's formula, "r_i' = 4-r_i for i in {4,5,7,8}"
      3. Step 8's question text ("...(REVERSE)") and its Maps To
         ("r4 → O4 (reverse)") -- itself two statements that must agree

    All three say 4, 5, 7 and 8, which is the published PSS-10. That matters
    because O4's header reads "CORRECTED: PSS-10, NOT PSS-4", so an earlier
    revision scored a different instrument and this is the evidence the
    correction landed everywhere.
    """
    from_column = {i["item_number"] for i in o4["items"] if i["reverse_scored"]}
    formula = next(e for e in o4["equations"]
                   if e["equation_id"] == "O4.1")["formula"]
    from_ui = {int(q["variable"][1:]) for q in steps["questions"]
               if q["reverse_scored"]}

    assert from_column == from_ui == {4, 5, 7, 8}
    assert "{4,5,7,8}" in formula.replace(" ", "")


def test_step_8_asks_exactly_the_ten_items_o4_scores(steps, o4):
    """Ten questions, ten items, same numbers. A PSS-10 the UI asks nine of
    would produce a total on a different scale that O4.2 divides by 40."""
    asked = sorted(int(q["variable"][1:]) for q in steps["questions"]
                   if q["variable"].startswith("r")
                   and q["variable"][1:].isdigit())
    scored = sorted(i["item_number"] for i in o4["items"])
    assert asked == scored == list(range(1, 11))


def test_o4_3s_cap_is_exactly_the_number_of_practices_the_ui_offers(steps, o4):
    """A QUIET CORROBORATION, and neither sheet mentions the other.

    O4.3 credits 0.05 per stress-management practice, capped at 0.20 -- which
    is exactly four. Step 8 offers four practices plus "None". So the cap is
    reachable by selecting every practice and cannot be exceeded, and the two
    numbers were written on different sheets.
    """
    practices = question(steps, "stress_practice")["answer_options"]
    real = [p for p in practices if p != "None"]
    assert len(real) == 4
    assert practices[-1] == "None"

    o4_3 = next(e for e in o4["equations"] if e["equation_id"] == "O4.3")
    formula = o4_3["formula"].replace(" ", "")
    assert "0.05perpractice" in formula
    assert "cap0.20" in formula
    assert 0.05 * len(real) == pytest.approx(0.20)


def test_the_pss10_items_are_mandatory(steps):
    """A PSS-10 with an optional item cannot be totalled."""
    for q in steps["questions"]:
        if q["variable"].startswith("r") and q["variable"][1:].isdigit():
            assert q["required"] == "Mandatory", q


# --- what it corroborates: O3 ---------------------------------------------

def test_step_9s_consistency_options_match_o3_6s_scale(steps, o3):
    """O3.6 scores four ordered options 1 to 4, abbreviating two of the
    labels. The full text is here, and the count and order must match or the
    module decodes an answer the UI never offers."""
    offered = question(steps, "sched_consistency")["answer_options"]
    o3_6 = next(e for e in o3["equations"] if e["equation_id"] == "O3.6")
    scale = o3_6["ordinal_scale"]

    assert len(offered) == len(scale) == 4
    assert [s["value"] for s in scale] == [1, 2, 3, 4]
    # O3 writes 'Somewhat' and 'Fairly'; the UI writes them out in full.
    for option, scored in zip(offered, scale):
        assert option.startswith(scored["option"]), (option, scored)


def test_step_9_collects_what_o3_reads(steps):
    sleep = question(steps, "sleep_hrs")
    quality = question(steps, "sleep_quality")
    assert sleep["targets"] == ["O3"]
    assert quality["targets"] == ["O3"]
    assert sleep["required"] == "Mandatory"
    assert quality["required"] == "Mandatory"


def test_the_sleep_slider_stops_where_o3_5s_upper_branch_begins(steps):
    """RECORDED, NOT RESOLVED. Step 9 collects sleep with a "Slider 0-8+
    hours", and O3.5 has a third branch for h > 9: min(1, (h-9)/2).

    Whether that branch is reachable depends on what "8+" lets a user select,
    which the sheet does not say. If the slider stops at 8 the branch is dead
    and the healthy window's upper edge never binds. Flagged in
    docs/parameter-gaps.md rather than assumed either way.
    """
    assert question(steps, "sleep_hrs")["answer_options_text"] == \
        "Slider 0-8+ hours"


# --- what every O-module's inputs actually are ----------------------------

def test_the_variables_the_o_modules_declare_are_collected_somewhere(steps):
    """onboarding_symbols.DECLARED_INPUTS was written by hand, with a comment
    saying a parser could not tell a user's answer from any other name. That
    was true only while this sheet was unimported -- its Maps To column says
    exactly that, for every input.

    This does not yet replace the hand-written set, because the two use
    different spellings for the same answer (the UI's 'sleep_quality' is
    O3's 'quality_rating', its 'sched_consistency' is 'consistency_score').
    Bridging those is a decision to record, in the style of
    build_eq_param_fk.ALIASES, not something to infer from resemblance -- so
    what is asserted here is only that the UI collects something for each
    O-module this build has implemented.
    """
    consumers = {t for q in steps["questions"] for t in q["targets"]}
    for module in ("O1", "O2", "O3", "O4", "O5"):
        assert module in consumers, module
