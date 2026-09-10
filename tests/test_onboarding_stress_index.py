"""ONB-004 — 'O·O4 Stress Index', equations O4.1-O4.9.

The sheet is the best-specified of the four O-sheets imported so far: every
symbol resolves, every constant is stated, and it makes two claims that can
be checked against each other. Those cross-checks are the tests worth having,
because they are the only ones the source can actually fail.

What it also does is compute a protective adjustment and route it nowhere,
which is the same shape as O3.1's quality weighting. That is pinned here.
"""
import ast
import json
from pathlib import Path

import pytest

from sahacore.onboarding import stress_index as o4
from sahacore.onboarding.parameters import load_o4_bands, load_o4_reverse_items

DATA_DIR = Path(__file__).parent.parent / "sahacore" / "data"


@pytest.fixture(scope="module")
def sheet():
    return json.loads((DATA_DIR / "onboarding_o4.json").read_text(encoding="utf-8"))


def answers(*responses, practices=0):
    return o4.StressAnswers(item_responses=tuple(responses), practices=practices)


def executable_source() -> str:
    """stress_index.py with its docstrings and comments removed.

    The no-hardcoding rule is about what the code COMPUTES from, and every
    module in this package is required to transcribe its source equations
    verbatim in the docstring -- which is where "{4,5,7,8}" and "14-26"
    legitimately appear. A test that grepped the whole file would forbid the
    transcription the project mandates, so it reads the executable half.
    """
    path = (Path(__file__).parent.parent / "sahacore" / "onboarding"
            / "stress_index.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                                 ast.AsyncFunctionDef)):
            continue
        body = node.body
        if (body and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)):
            node.body = body[1:] or [ast.Pass()]
    return ast.unparse(ast.fix_missing_locations(tree))


CALM = answers(*([0] * 3 + [4] * 2 + [0] + [4] * 2 + [0] * 2))
STRESSED = answers(*([4] * 3 + [0] * 2 + [4] + [0] * 2 + [4] * 2))


# --- the instrument -------------------------------------------------------

def test_the_sheet_carries_ten_items_on_one_shared_scale(sheet):
    """A 0-40 total only means something if every item is scored 0-4."""
    items = sheet["items"]
    assert len(items) == 10
    assert [i["item_number"] for i in items] == list(range(1, 11))
    assert {i["scale"] for i in items} == {"0-4"}


def test_the_reverse_scored_items_are_stated_twice_and_agree(sheet):
    """THE ONE CROSS-CHECK THE SOURCE MAKES POSSIBLE.

    The sheet names its reverse-scored items in a Reverse? column AND inside
    O4.1's formula. Neither statement is more authoritative than the other,
    so if they ever disagree the PSS-10 total is simply wrong -- and the
    extractor refuses to import that sheet rather than picking a winner.

    They are 4, 5, 7 and 8, which is the published PSS-10. That matters here
    because the sheet's own header reads "CORRECTED: PSS-10, NOT PSS-4", so
    an earlier revision scored a different instrument.
    """
    flagged = {i["item_number"] for i in sheet["items"] if i["reverse_scored"]}
    formula = next(e for e in sheet["equations"]
                   if e["equation_id"] == "O4.1")["formula"]

    assert flagged == {4, 5, 7, 8}
    assert "{4,5,7,8}" in formula.replace(" ", "")
    assert load_o4_reverse_items() == flagged


def test_the_module_reads_the_reverse_set_rather_than_writing_it():
    """Which items reverse is the sheet's decision. A module that hardcoded
    the set would keep scoring PSS-4 if the sheet were corrected again."""
    source = executable_source()
    assert "load_o4_reverse_items" in source
    assert "4, 5, 7, 8" not in source
    assert "{4,5,7,8}" not in source


def test_reversing_turns_a_confident_answer_into_a_low_stress_score():
    """Item 4 is "Confident handling problems". Answering 4 -- very often --
    must score 0 towards stress, not 4.

    Only item 4 is varied here. The total is not, because the other three
    reverse-scored items answered 0 contribute 4 each: all-zeroes is a
    HIGH-stress answer sheet on three of the ten items, not a blank one.
    """
    confident = answers(0, 0, 0, 4, 0, 0, 0, 0, 0, 0)
    never_confident = answers(0, 0, 0, 0, 0, 0, 0, 0, 0, 0)

    assert o4.scored_items(confident)[3] == 0
    assert o4.scored_items(never_confident)[3] == 4
    assert o4.pss10_total(never_confident) - o4.pss10_total(confident) == 4

    # Items 5, 7 and 8 answered 0 are why neither total is zero.
    assert o4.pss10_total(confident) == 12
    assert o4.pss10_total(never_confident) == 16


def test_the_total_spans_exactly_zero_to_forty():
    assert o4.pss10_total(CALM) == 0
    assert o4.pss10_total(STRESSED) == 40


@pytest.mark.parametrize("responses", [
    (0,) * 9,          # too few
    (0,) * 11,         # too many
])
def test_a_pss10_with_the_wrong_number_of_answers_is_refused(responses):
    """Scoring nine answers would produce a total on a different scale that
    O4.2 would then divide by 40."""
    with pytest.raises(ValueError, match="10 responses"):
        o4.pss10_total(o4.StressAnswers(item_responses=responses))


def test_a_response_outside_the_scale_is_refused():
    with pytest.raises(ValueError, match="outside the 0-4 scale"):
        o4.pss10_total(answers(0, 0, 0, 0, 0, 0, 0, 0, 0, 5))


# --- O4.3, and where it goes ----------------------------------------------

def test_stress_protection_is_five_percent_a_practice_capped_at_twenty():
    assert o4.stress_protection(0) == 0.0
    assert o4.stress_protection(1) == pytest.approx(0.05)
    assert o4.stress_protection(4) == pytest.approx(0.20)
    # The cap binds at four; a fifth practice earns nothing.
    assert o4.stress_protection(5) == pytest.approx(0.20)
    assert o4.stress_protection(100) == pytest.approx(0.20)


def test_o4_3_clamps_at_zero_rather_than_going_negative():
    """max(0, ...) is in the formula, and it binds: a calm user with four
    practices would otherwise score -0.20."""
    calm_and_practising = answers(*CALM.item_responses, practices=4)
    assert o4.stress_index_raw(calm_and_practising) == 0.0
    assert o4.stress_index_adjusted(calm_and_practising) == 0.0


def test_o4_3_names_four_consumers_and_none_of_them_reads_it(sheet):
    """THE FINDING, and it is the second of this shape in two sheets.

    O4.3's Engine Target reads "O4.4, O4.5, O4.6, O4.7". None of those four
    mentions stress_idx_adj: O4.4 recomputes Theta_AL = PSS10/40 from the
    total, and O4.5 through O4.9 all read Theta_AL.

    So p_stressprot -- up to 0.20 of a 0-1 scale, a fifth of the whole range
    -- is computed and consumed by nothing. A user reporting four
    stress-management practices gets identical cortisol, inflammation,
    glucose, CVD and repair modifiers to one reporting none.

    Not corrected. Routing O4.3 into O4.4 would move five downstream
    modifiers on an authority the sheet does not give. See
    docs/parameter-gaps.md.
    """
    by_id = {e["equation_id"]: e for e in sheet["equations"]}
    assert by_id["O4.3"]["engine_target"] == "O4.4, O4.5, O4.6, O4.7"

    for equation_id in ("O4.4", "O4.5", "O4.6", "O4.7"):
        equation = by_id[equation_id]
        assert "stress_idx_adj" not in (
            equation["formula"] + " " + (equation["variables"] or "")), (
            f"{equation_id} now reads stress_idx_adj -- the finding may be "
            "resolved. Re-read the sheet and docs/parameter-gaps.md.")

    # And the consequence in the built module: practices move the adjusted
    # index and move no modifier the engine uses.
    none = answers(*STRESSED.item_responses, practices=0)
    four = answers(*STRESSED.item_responses, practices=4)
    assert o4.stress_index_adjusted(none) != o4.stress_index_adjusted(four)
    for modifier in (o4.allostatic_load, o4.cortisol_modifier,
                     o4.inflammation_modifier, o4.glucose_modifier,
                     o4.cvd_modifier, o4.repair_rate_modifier):
        assert modifier(none) == modifier(four)


def test_o4_2_and_o4_4_are_the_same_function_under_two_names(sheet):
    """stress_idx_raw = PSS10/40 and Theta_AL = PSS10/40.

    Harmless as written, and worth pinning because it is why the O4.3 break
    is easy to miss: Theta_AL reads as though it descends from the stress
    index, and it does not.
    """
    by_id = {e["equation_id"]: e for e in sheet["equations"]}
    rhs = {eid: by_id[eid]["formula"].partition("=")[2].strip().replace(" ", "")
           for eid in ("O4.2", "O4.4")}
    assert rhs["O4.2"] == rhs["O4.4"] == "PSS10/40"

    for case in (CALM, STRESSED, answers(1, 2, 3, 1, 2, 3, 1, 2, 3, 1)):
        assert o4.stress_index_raw(case) == o4.allostatic_load(case)


# --- the modifiers, and the bands that corroborate them -------------------

def test_theta_al_spans_zero_to_one():
    assert o4.allostatic_load(CALM) == 0.0
    assert o4.allostatic_load(STRESSED) == 1.0


@pytest.mark.parametrize("modifier,slope", [
    (o4.cortisol_modifier, 0.4),
    (o4.inflammation_modifier, 0.3),
    (o4.glucose_modifier, 0.3),
    (o4.cvd_modifier, 0.3),
])
def test_each_damage_modifier_is_one_at_no_stress_and_one_plus_slope_at_full(
        modifier, slope):
    assert modifier(CALM) == pytest.approx(1.0)
    assert modifier(STRESSED) == pytest.approx(1.0 + slope)


def test_repair_is_the_only_modifier_that_falls_with_stress():
    assert o4.repair_rate_modifier(CALM) == pytest.approx(1.0)
    assert o4.repair_rate_modifier(STRESSED) == pytest.approx(0.85)
    assert o4.repair_rate_modifier(STRESSED) < o4.repair_rate_modifier(CALM)


def test_the_high_band_corroborates_o4_5(sheet):
    """Row 41 says High stress is "+40% damage sensitivity", and O4.5 is
    1 + 0.4*Theta_AL, which is exactly +40% at Theta_AL = 1.

    A sheet agreeing with itself in two independently written places is
    evidence its numbers were meant, so it is checked rather than admired.
    """
    high = next(b for b in sheet["bands"] if b["stress_level"] == "High")
    assert "+40%" in high["system_response"]
    assert o4.cortisol_modifier(STRESSED) == pytest.approx(1.40)


def test_the_moderate_band_corroborates_o4_9(sheet):
    """Row 40 says "approx -5% to -10% repair efficiency across the Moderate
    band; -15% is the maximum at Theta_AL=1". O4.9 is 1 - 0.15*Theta_AL, so
    over the band's 14-26 it gives -5.25% to -9.75%, and -15% at the top."""
    moderate = next(b for b in sheet["bands"] if b["stress_level"] == "Moderate")
    assert (moderate["score_min"], moderate["score_max"]) == (14, 26)
    assert "15%" in moderate["system_response"]

    at_low_edge = 1.0 - 0.15 * (14 / 40)
    at_high_edge = 1.0 - 0.15 * (26 / 40)
    assert at_low_edge == pytest.approx(0.9475)     # -5.25%
    assert at_high_edge == pytest.approx(0.9025)    # -9.75%
    assert o4.repair_rate_modifier(STRESSED) == pytest.approx(0.85)  # -15%


# --- the bands ------------------------------------------------------------

def test_the_bands_tile_zero_to_forty_with_no_gap_and_no_overlap():
    """Every PSS-10 total must have exactly one stated interpretation."""
    bands = load_o4_bands()
    assert [b["stress_level"] for b in bands] == ["Low", "Moderate", "High"]
    assert bands[0]["score_min"] == 0
    assert bands[-1]["score_max"] == 40
    for lower, upper in zip(bands, bands[1:]):
        assert upper["score_min"] == lower["score_max"] + 1


def test_every_reachable_total_lands_in_exactly_one_band():
    bands = load_o4_bands()
    for total in range(0, 41):
        matching = [b for b in bands
                    if b["score_min"] <= total <= b["score_max"]]
        assert len(matching) == 1, (total, matching)


def test_stress_level_reads_the_boundaries_rather_than_writing_them():
    assert o4.stress_level(CALM) == "Low"
    assert o4.stress_level(STRESSED) == "High"

    source = executable_source()
    assert "load_o4_bands" in source
    for boundary in ("13", "14", "26", "27"):
        assert boundary not in source, (
            f"{boundary} is a band edge and belongs in the registry, not in "
            "the module. Where 'Moderate' ends is a clinical judgement.")


# --- the sheet as a whole -------------------------------------------------

def test_all_nine_equations_carry_their_engine_target(sheet):
    """The Engine Target column is what says where a Layer 0 output goes. It
    was silently dropped from O1 and O2 for a whole session."""
    equations = sheet["equations"]
    assert len(equations) == 9
    assert [e["equation_id"] for e in equations] == [f"O4.{n}" for n in range(1, 10)]
    for equation in equations:
        assert equation["engine_target"]


def test_o4_introduces_no_symbol_the_workbook_leaves_undefined():
    """O1 left e_WHtR, e_BMI and f_u_ref undefined and O2 left HR_Arem and
    rho_pop. O3 introduced none, and O4 introduces none either."""
    from sahacore.data.onboarding_symbols import KNOWN_UNRESOLVED, analyse

    result = analyse()
    new = sorted(set(result["unresolved"]) - set(KNOWN_UNRESOLVED))
    assert new == [], f"new undefined symbols: {new}"

    o4_equations = [e for e in result["equations"]
                    if e["sheet"] == "O·O4 Stress Index"]
    assert len(o4_equations) == 9
    for equation in o4_equations:
        assert equation["unresolved"] == [], equation
