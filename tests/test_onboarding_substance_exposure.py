"""ONB-005 — 'O·O5 Substance Exposure', equations O5.1-O5.7.

The first O-sheet imported AFTER its own UI contract, so for the first time
an O-module's inputs can be checked against what the interface collects
rather than against the same sheet that declared them. Three of the four
findings here exist only because that check is now possible.
"""
import ast
import json
from pathlib import Path

import pytest

from sahacore.onboarding import substance_exposure as o5
from sahacore.onboarding.parameters import load_o5_encoding, load_o5_ssb_midpoints

DATA_DIR = Path(__file__).parent.parent / "sahacore" / "data"


def _load(name):
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def sheet():
    return _load("onboarding_o5.json")


@pytest.fixture(scope="module")
def ui():
    return _load("step_questions.json")


def ui_options(ui, variable):
    matching = [q for q in ui["questions"] if q["variable"] == variable]
    assert len(matching) == 1, variable
    return matching[0]["answer_options"]


# --- the sheet ------------------------------------------------------------

def test_all_seven_equations_carry_their_engine_target(sheet):
    equations = sheet["equations"]
    assert [e["equation_id"] for e in equations] == [f"O5.{n}" for n in range(1, 8)]
    for equation in equations:
        assert equation["engine_target"]
        assert equation["variables"]


def test_the_four_encodings_are_read_not_written():
    """Every one of these turns an answer into a number, and every one is the
    sheet's judgement. A module that wrote them would be re-deciding what a
    user's answer is worth."""
    assert load_o5_encoding("pack_years") == {
        "Never": 0, "Former(>1yr)": 2, "Former(<1yr)": 5,
        "Occasional": 5, "Daily": 20}
    assert load_o5_encoding("tobacco_idx") == {
        "Never": 0, "Former(>1yr)": 0.15, "Former(<1yr)": 0.35,
        "Occasional": 0.5, "Daily": 1.0}
    assert load_o5_encoding("units_week") == {
        "0": 0, "1-3": 2, "4-7": 5.5, "8+": 10}
    assert load_o5_ssb_midpoints() == (0, 0.5, 1.75, 3)

    source = (Path(__file__).parent.parent / "sahacore" / "onboarding"
              / "substance_exposure.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef)):
            continue
        body = node.body
        if (body and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)):
            node.body = body[1:] or [ast.Pass()]
    executable = ast.unparse(ast.fix_missing_locations(tree))
    for value in ("0.15", "0.35", "1.75", "5.5"):
        assert value not in executable, (
            f"{value} is an encoded answer and belongs in the registry")


# --- what corroborates ----------------------------------------------------

def test_o5_2s_alcohol_midpoints_are_the_true_midpoints_of_the_ui_bands(ui):
    """THE CONTROL FOR FINDING 1. The sheet demonstrably knows how to write a
    midpoint, which is what makes O5.5's numbers a discrepancy rather than a
    convention this build failed to understand."""
    bands = ui_options(ui, "drinks_wk")
    encoded = load_o5_encoding("units_week")
    assert bands == ["0", "1-3", "4-7", "8+ drinks"]

    assert encoded["1-3"] == pytest.approx((1 + 3) / 2)
    assert encoded["4-7"] == pytest.approx((4 + 7) / 2)
    assert encoded["0"] == 0
    # '8+' is open, so 10 is a choice rather than a computable midpoint.
    assert encoded["8+"] == 10


def test_o5_3s_ceiling_matches_its_declared_range(sheet):
    """k_ox is multiplicative, so its ceiling is the product of the two
    ceilings: 1.4 * 1.1 = 1.54, against a declared '1.0-1.5+'."""
    worst = o5.oxidative_rate_constant("Daily", 10)
    assert worst == pytest.approx(1.4 * 1.1)
    assert worst == pytest.approx(1.54)

    declared = next(e for e in sheet["equations"]
                    if e["equation_id"] == "O5.3")["value_range"]
    assert declared.startswith("1.0-1.5")

    assert o5.oxidative_rate_constant("Never", 0) == pytest.approx(1.0)


# --- finding 1: O5.5's midpoints are not midpoints ------------------------

def test_o5_5s_midpoints_are_not_the_midpoints_of_step_3s_bands(ui):
    """THE FINDING WITH A PRICE ON IT.

    Step 3 offers 0 / 1-2 / 3-4 / 5+ sugary drinks a day. O5.5 declares
    "(midpoint: 0/0.5/1.75/3)". Two of the four disagree with the bands they
    must correspond to, and the sheet calls them midpoints.

    It changes a Layer C input. e_SSB = min(1, SSB_serv_day/1.5), so a user
    answering "1-2" is recorded at a THIRD of maximum glycation exposure
    rather than at maximum. Only that band's outcome differs -- 3-4
    saturates either way -- but it is likely the commonest non-zero answer.
    """
    bands = ui_options(ui, "SSB_serv")
    declared = load_o5_ssb_midpoints()
    assert bands == ["0", "1-2", "3-4", "5+"]
    assert len(declared) == len(bands)

    assert declared[1] == 0.5 and (1 + 2) / 2 == 1.5
    assert declared[2] == 1.75 and (3 + 4) / 2 == 3.5

    assert o5.ssb_exposure_index(declared[1]) == pytest.approx(1 / 3)
    assert o5.ssb_exposure_index(1.5) == pytest.approx(1.0)
    # The third band saturates under either reading, so only the second moves.
    assert o5.ssb_exposure_index(declared[2]) == pytest.approx(1.0)
    assert o5.ssb_exposure_index(3.5) == pytest.approx(1.0)


def test_e_ssb_saturates_and_never_leaves_zero_to_one():
    for servings in (0, 0.5, 1.5, 3, 10, 100):
        assert 0.0 <= o5.ssb_exposure_index(servings) <= 1.0
    assert o5.ssb_exposure_index(0) == 0.0


# --- finding 2: the five categories are not what the UI collects ----------

def test_the_ui_offers_no_former_option_so_the_five_categories_are_a_join(ui):
    """O5.1 and O5.7 both map Never / Former(>1yr) / Former(<1yr) /
    Occasional / Daily. Step 10 asks two questions and neither offers
    "Former": smoke_status is Yes daily / Yes occasionally / No, and
    quit_time is Within last year / More than a year ago / Never.

    So "No" plus "Within last year" is presumably Former(<1yr) -- and no
    sheet says so. The module takes the joined category and cannot perform
    the join, which is the honest position while the rule is missing.
    """
    smoke_status = ui_options(ui, "smoke_status")
    quit_time = ui_options(ui, "quit_time")
    assert smoke_status == ["Yes daily", "Yes occasionally", "No"]
    assert quit_time == ["Within last year", "More than a year ago", "Never"]
    assert not any("Former" in o for o in smoke_status + quit_time)

    categories = set(load_o5_encoding("pack_years"))
    assert categories == {"Never", "Former(>1yr)", "Former(<1yr)",
                          "Occasional", "Daily"}
    assert len(categories) > len(smoke_status)


# --- finding 3: two indices, two rankings ---------------------------------

def test_o5_1_and_o5_7_rank_the_same_five_categories_differently():
    """One smoking answer feeds two indices on two scales, and they disagree
    about whether a recent ex-smoker is worse than an occasional smoker.

    pack_years ties them at 5. tobacco_idx puts Former(<1yr) at 0.35 below
    Occasional at 0.5. Not corrected -- which ordering is right is a
    clinical judgement, and the two feed different Layer C targets.
    """
    pack = load_o5_encoding("pack_years")
    tobacco = load_o5_encoding("tobacco_idx")
    assert set(pack) == set(tobacco)

    assert pack["Former(<1yr)"] == pack["Occasional"] == 5
    assert tobacco["Former(<1yr)"] < tobacco["Occasional"]

    # Same answer, opposite verdicts on which of the two is worse.
    assert (o5.tobacco_exposure_index("Former(<1yr)")
            == o5.tobacco_exposure_index("Occasional"))
    assert (o5.tobacco_index("Former(<1yr)")
            < o5.tobacco_index("Occasional"))


def test_both_tobacco_indices_are_monotone_over_the_severity_order():
    """Never is lowest and Daily highest in both, whatever they do between."""
    for lookup in (o5.pack_years, o5.tobacco_index):
        assert lookup("Never") == 0
        assert lookup("Daily") == max(
            lookup(c) for c in load_o5_encoding("pack_years"))


# --- finding 4: O5.6's male branch ---------------------------------------

def test_o5_6s_male_branch_is_unreachable_under_the_only_encoding_there_is(ui):
    """THE FINDING, and it needed the UI contract to see.

    O5.6 is min(1, max(0, (drinks_wk - T)/T)) with T = 7 for females and 14
    for males. The UI asks about alcohol ONCE, so drinks_wk and units_week
    are the same answer, and units_week's largest encoded value is 10.

    A male therefore scores 0 on every answer the interface accepts, and a
    female tops out at 0.43. Both are declared 0-1.

    Implemented as written. The module keeps drinks_wk and units_week as
    separate arguments precisely so this stays visible rather than baked in
    -- the sheet never states they are the same quantity, and bridging two
    names on a resemblance is what this repo refuses to do.
    """
    assert len(ui_options(ui, "drinks_wk")) == 4
    highest = max(load_o5_encoding("units_week").values())
    assert highest == 10

    for band_value in load_o5_encoding("units_week").values():
        assert o5.alcohol_sex_index(band_value, "Male") == 0.0
    assert o5.alcohol_sex_index(highest, "Female") == pytest.approx(3 / 7)

    # Both branches do work on values the UI cannot produce.
    assert o5.alcohol_sex_index(28, "Male") == pytest.approx(1.0)
    assert o5.alcohol_sex_index(14, "Female") == pytest.approx(1.0)


def test_o5_6_refuses_a_sex_it_has_no_threshold_for():
    with pytest.raises(KeyError, match="O5.6 gives thresholds"):
        o5.alcohol_sex_index(10, "Unspecified")


# --- the remaining equations ---------------------------------------------

def test_o5_1_and_o5_2_are_one_at_no_exposure_and_rise_with_it():
    assert o5.tobacco_exposure_index("Never") == pytest.approx(1.0)
    assert o5.tobacco_exposure_index("Daily") == pytest.approx(1.4)
    assert o5.alcohol_exposure_index(0) == pytest.approx(1.0)
    assert o5.alcohol_exposure_index(10) == pytest.approx(1.1)


def test_o5_4_is_a_step_at_eight_drinks_a_week():
    assert o5.gsh_depletion_factor(7.9) == 0.0
    assert o5.gsh_depletion_factor(8) == 0.8
    assert o5.gsh_depletion_factor(100) == 0.8
    # The UI's top band encodes to 10, so the step IS reachable -- unlike
    # O5.6's male threshold.
    assert o5.gsh_depletion_factor(load_o5_encoding("units_week")["8+"]) == 0.8


def test_o5_introduces_no_symbol_the_workbook_leaves_undefined():
    from sahacore.data.onboarding_symbols import (
        KNOWN_BROKEN_ROUTINGS, KNOWN_UNRESOLVED, analyse,
    )

    result = analyse()
    new = sorted(set(result["unresolved"]) - set(KNOWN_UNRESOLVED))
    assert new == [], f"new undefined symbols: {new}"

    broken = sorted({r["equation_id"] for r in result["broken_routings"]}
                    - set(KNOWN_BROKEN_ROUTINGS))
    assert broken == [], f"new broken routings: {broken}"
