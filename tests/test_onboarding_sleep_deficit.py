"""ONB-003, the sleep prior.

Authority: 'O·O3 Sleep Deficit' -- manifest order 73.
QA required by 'O · Onboarding Canonical': "deficit zero when sleep>=target".

All eight equations are implemented -- the first of the three O-sheets with
no symbol the workbook leaves undefined. What these tests pin instead is the
one place the sheet disagrees with itself: O3.1 and O3.5 both measure sleep
shortfall and do not agree.
"""
import json
from pathlib import Path

import pytest

from sahacore.onboarding import sleep_deficit as o3
from sahacore.onboarding.parameters import load_o3_consistency

DATA_DIR = Path(__file__).parent.parent / "sahacore" / "data"


@pytest.fixture(scope="module")
def sheet() -> dict:
    return json.loads((DATA_DIR / "onboarding_o3.json").read_text(encoding="utf-8"))


# --- the QA the canonical sheet asks for ----------------------------------

def test_deficit_is_zero_when_sleep_meets_the_target():
    """'deficit zero when sleep>=target' -- the acceptance test 'O · Onboarding
    Canonical' names for ONB-003. One-sided by construction: the max() is
    what stops extra sleep producing a negative deficit."""
    assert o3.deficit_hours(7) == 0.0
    assert o3.deficit_hours(8) == 0.0
    assert o3.deficit_hours(11) == 0.0
    assert o3.deficit_hours(6) == 1.0
    assert o3.deficit_hours(4.5) == 2.5


def test_all_eight_equations_carry_their_engine_target(sheet):
    equations = sheet["equations"]
    assert [e["equation_id"] for e in equations] == [f"O3.{n}" for n in range(1, 9)]
    for equation in equations:
        assert equation["engine_target"], equation["equation_id"]

    by_id = {e["equation_id"]: e for e in equations}
    assert "Z3 Inflammation" in by_id["O3.2"]["engine_target"]
    assert "Z6" in by_id["O3.3"]["engine_target"]
    assert "Z10" in by_id["O3.4"]["engine_target"]
    assert by_id["O3.8"]["engine_target"].startswith("Layer E")


# --- O3.2, O3.3, O3.4: the three Layer-C modifiers ------------------------

def test_o3_2_raises_inflammation_with_deficit_and_never_below_one():
    """k_inflam_mod = 1 + 0.081*deficit. A modifier that dipped below 1 would
    mean short sleep REDUCED inflammation."""
    assert o3.inflammation_modifier(7) == 1.0
    assert o3.inflammation_modifier(9) == 1.0
    assert o3.inflammation_modifier(6) == pytest.approx(1.081)
    assert o3.inflammation_modifier(4) == pytest.approx(1 + 0.081 * 3)
    for hours in (0, 3, 5, 7, 9, 12):
        assert o3.inflammation_modifier(hours) >= 1.0


def test_o3_3_falls_with_deficit_and_stays_inside_the_declared_range(sheet):
    """The sheet declares 0.7-1.0. That bottom is reached at a deficit of
    6.67 hours -- more than a whole night short -- so the range holds across
    every plausible answer without needing a clamp."""
    declared = next(e for e in sheet["equations"]
                    if e["equation_id"] == "O3.3")["value_range"]
    assert declared == "0.7-1.0"
    assert o3.insulin_resistance_modifier(7) == 1.0
    assert o3.insulin_resistance_modifier(6) == pytest.approx(0.955)
    for hours in (1, 3, 5, 7, 9):
        assert 0.7 <= o3.insulin_resistance_modifier(hours) <= 1.0


def test_o3_4_is_a_step_at_one_hour_of_deficit(sheet):
    """FSR_mod = 1 - 0.18*I(deficit > 1). Strictly greater, so a deficit of
    exactly one hour does not fire, and there is nothing between the two
    values -- which is what the sheet's range '0.82 or 1.0' says."""
    declared = next(e for e in sheet["equations"]
                    if e["equation_id"] == "O3.4")["value_range"]
    assert declared == "0.82 or 1.0"
    assert o3.fractional_synthesis_modifier(7) == 1.0
    assert o3.fractional_synthesis_modifier(6) == 1.0        # deficit exactly 1
    assert o3.fractional_synthesis_modifier(5.9) == pytest.approx(0.82)
    assert o3.fractional_synthesis_modifier(4) == pytest.approx(0.82)
    values = {round(o3.fractional_synthesis_modifier(h / 2), 2)
              for h in range(0, 25)}
    assert values == {0.82, 1.0}


# --- O3.5: the two-sided index -------------------------------------------

def test_o3_5_is_zero_across_the_healthy_window_and_rises_both_sides():
    for hours in (7, 7.5, 8, 8.5, 9):
        assert o3.sleep_deficit_index(hours) == 0.0
    assert o3.sleep_deficit_index(6) == pytest.approx(0.5)
    assert o3.sleep_deficit_index(5) == pytest.approx(1.0)
    assert o3.sleep_deficit_index(10) == pytest.approx(0.5)
    assert o3.sleep_deficit_index(11) == pytest.approx(1.0)


def test_o3_5_saturates_rather_than_growing_without_bound():
    """min(1, ...) on both sides. Two hours out is already the maximum, so an
    implausible answer cannot dominate the composite prior."""
    for hours in (0, 1, 3, 13, 20, 24):
        assert 0.0 <= o3.sleep_deficit_index(hours) <= 1.0
    assert o3.sleep_deficit_index(0) == 1.0
    assert o3.sleep_deficit_index(24) == 1.0


# --- O3.1 against O3.5: the disagreement ----------------------------------

def test_the_two_sleep_shortfall_measures_disagree_above_the_target(sheet):
    """THE FINDING. O3.1's SDS and O3.5's sleep_def both measure sleep
    shortfall, and only one of them is two-sided.

    SDS = (7 - sleep_hrs)/7 * quality_factor is not clamped, so at nine
    hours it is NEGATIVE -- against its own declared range of 0-1. sleep_def
    is zero there, which is what the seven-to-nine healthy window says.

    Neither is corrected. They are implemented under their own names so a
    caller cannot take one for the other, and O3.1's engine target -- O3.2,
    O3.3, O3.4 and O11 -- says which consumers get which.
    """
    declared = next(e for e in sheet["equations"]
                    if e["equation_id"] == "O3.1")["value_range"]
    assert declared == "0-1"

    long_sleeper = o3.SleepAnswers(sleep_hours=9, quality_rating=1,
                                   consistency_score=4)
    assert o3.sleep_deficit_score(long_sleeper) == pytest.approx(-2 / 7)
    assert o3.sleep_deficit_score(long_sleeper) < 0
    assert o3.sleep_deficit_index(9) == 0.0

    # They agree only where both are measuring a shortfall below the target.
    short = o3.SleepAnswers(sleep_hours=6, quality_rating=1, consistency_score=4)
    assert o3.sleep_deficit_score(short) > 0
    assert o3.sleep_deficit_index(6) > 0


def test_sds_scales_the_shortfall_by_quality():
    """quality_factor = 1 - (rating-1)/4: one at the worst rating, zero at the
    best. So the same short night counts for nothing if the user rates their
    sleep 5 out of 5 -- which is what makes SDS a quality-weighted deficit
    rather than a clock reading."""
    assert o3.quality_factor(1) == 1.0
    assert o3.quality_factor(5) == 0.0
    assert o3.quality_factor(3) == pytest.approx(0.5)

    worst = o3.SleepAnswers(sleep_hours=5, quality_rating=1, consistency_score=1)
    best = o3.SleepAnswers(sleep_hours=5, quality_rating=5, consistency_score=1)
    assert o3.sleep_deficit_score(worst) == pytest.approx(2 / 7)
    assert o3.sleep_deficit_score(best) == 0.0


def test_o3_1_names_three_consumers_and_none_of_them_read_it(sheet):
    """THE FINDING, and it is the one that costs something.

    O3.1's Engine Target column reads "O3.2, O3.3, O3.4, O11". Those first
    three are on this sheet, and not one of them mentions SDS. All three
    compute from deficit_hrs = max(0, 7 - sleep_hrs) -- the raw clock
    shortfall, with no quality weighting at all.

    So the quality_factor that makes SDS worth computing is declared to flow
    into inflammation, insulin resistance and FSR, and in fact reaches none of
    them. Two users who both sleep five hours, one rating their sleep 1/5 and
    the other 5/5, get identical Z3, Z6 and Z10 modifiers; their SDS values,
    2/7 and 0, differ by the whole range of the score and are consumed by
    nothing on this sheet.

    Not corrected. Either O3.2-O3.4 should read SDS and do not, or O3.1's
    engine target names consumers it does not have -- and which of those is
    true decides whether sleep quality affects Layer C at all. That is a
    question for the sheet's author, not a bug to patch. O11 is unimported,
    so it may yet be SDS's only real consumer.
    """
    by_id = {e["equation_id"]: e for e in sheet["equations"]}
    assert by_id["O3.1"]["engine_target"] == "O3.2, O3.3, O3.4, O11"

    for equation_id in ("O3.2", "O3.3", "O3.4"):
        equation = by_id[equation_id]
        text = equation["formula"] + " " + (equation["variables"] or "")
        assert "SDS" not in text, (
            f"{equation_id} now reads SDS. If the sheet was corrected, this "
            "finding is resolved -- re-read O3.1's engine target and "
            "docs/parameter-gaps.md before deleting the test.")
        assert "deficit_hrs" in text or "deficit" in text

    # And the consequence, in the built module: quality moves SDS and moves
    # none of the three modifiers.
    poor = o3.SleepAnswers(sleep_hours=5, quality_rating=1, consistency_score=1)
    good = o3.SleepAnswers(sleep_hours=5, quality_rating=5, consistency_score=1)
    assert o3.sleep_deficit_score(poor) != o3.sleep_deficit_score(good)
    for modifier in (o3.inflammation_modifier, o3.insulin_resistance_modifier,
                     o3.fractional_synthesis_modifier):
        assert modifier(poor.sleep_hours) == modifier(good.sleep_hours)


# --- O3.6 and O3.7 --------------------------------------------------------

def test_the_consistency_scale_is_read_from_the_sheet():
    """Four ordered options, written inline in O3.6's own formula cell rather
    than in an encoding table. What an answer is worth is the sheet's
    decision, so the module reads it."""
    scale = load_o3_consistency()
    assert scale == {"Very Inconsistent": 1, "Somewhat": 2,
                     "Fairly": 3, "Very Consistent": 4}
    assert list(scale.values()) == sorted(scale.values())


def test_o3_6_maps_the_four_options_onto_zero_to_one():
    scale = load_o3_consistency()
    assert o3.schedule_consistency_index(scale["Very Inconsistent"]) == 0.0
    assert o3.schedule_consistency_index(scale["Very Consistent"]) == 1.0
    assert o3.schedule_consistency_index(scale["Somewhat"]) == pytest.approx(1 / 3)
    for score in scale.values():
        assert 0.0 <= o3.schedule_consistency_index(score) <= 1.0


def test_e_sleepqual_is_defined_by_the_sheet_and_read_not_invented(sheet):
    """O3.7's Variables cell says "e_sleepqual=(5-quality)/4" -- the sheet
    defines its own composite input, which is exactly what O1.9 fails to do
    for e_WHtR and e_BMI. So this one is derived, and those two are
    arguments."""
    o3_7 = next(e for e in sheet["equations"] if e["equation_id"] == "O3.7")
    assert "e_sleepqual=(5-quality)/4" in o3_7["variables"].replace(" ", "")
    assert o3.sleep_quality_index(5) == 0.0
    assert o3.sleep_quality_index(1) == 1.0
    assert o3.sleep_quality_index(3) == pytest.approx(0.5)


def test_o3_7_mixes_two_badness_indices_with_one_goodness_index():
    """THE FINDING, and it came out of writing this test rather than out of
    reading the sheet.

    O3.7 is mu_sleep = 0.5*sleep_def + 0.3*e_sleepqual + 0.2*e_sched. The
    first two run 0 = good, 1 = bad. The third runs the other way: O3.6 is
    (consistency_score - 1)/3, and 'Very Consistent' is the HIGHEST score, so
    e_sched is 1 for the best possible schedule.

    A perfectly regular sleeper therefore ADDS 0.2 to a composite that
    otherwise measures how bad their sleep is. The best case scores 0.2 and
    the worst 0.8, so neither end of the sheet's declared 0-1 range is
    reachable.

    Not corrected. Flipping a term changes what a Layer E state prior means,
    which is the workbook author's call. Reported in docs/parameter-gaps.md.
    """
    assert sum(o3._SLEEP_PRIOR_WEIGHTS.values()) == pytest.approx(1.0)

    best = o3.SleepAnswers(sleep_hours=8, quality_rating=5, consistency_score=4)
    worst = o3.SleepAnswers(sleep_hours=3, quality_rating=1, consistency_score=1)

    # Each term on its own, so the odd one out is visible rather than inferred.
    assert o3.sleep_deficit_index(8) == 0.0 and o3.sleep_deficit_index(3) == 1.0
    assert o3.sleep_quality_index(5) == 0.0 and o3.sleep_quality_index(1) == 1.0
    assert o3.schedule_consistency_index(4) == 1.0
    assert o3.schedule_consistency_index(1) == 0.0

    assert o3.composite_sleep_prior(best) == pytest.approx(0.2)
    assert o3.composite_sleep_prior(worst) == pytest.approx(0.8)

    # The composite stays inside [0, 1] -- it is the ENDS that are unreachable,
    # not the bound that is broken.
    for answers in (best, worst,
                    o3.SleepAnswers(5.5, 2, 2), o3.SleepAnswers(10, 4, 3)):
        assert 0.0 <= o3.composite_sleep_prior(answers) <= 1.0


def test_a_more_consistent_schedule_raises_the_sleep_prior():
    """The consequence, stated as behaviour: holding sleep and quality fixed,
    answering 'Very Consistent' instead of 'Very Inconsistent' moves mu_sleep
    UP by 0.2 -- toward whatever end of the scale bad sleep sits at."""
    scale = load_o3_consistency()
    steady = o3.SleepAnswers(7.5, 3, scale["Very Consistent"])
    erratic = o3.SleepAnswers(7.5, 3, scale["Very Inconsistent"])
    assert (o3.composite_sleep_prior(steady)
            - o3.composite_sleep_prior(erratic)) == pytest.approx(0.2)


def test_a_realistic_answer_lands_where_it_should():
    """5.5 hours, quality 2 of 5, somewhat consistent."""
    answers = o3.SleepAnswers(sleep_hours=5.5, quality_rating=2,
                              consistency_score=load_o3_consistency()["Somewhat"])
    assert o3.deficit_hours(5.5) == 1.5
    assert o3.inflammation_modifier(5.5) == pytest.approx(1.1215)
    assert o3.fractional_synthesis_modifier(5.5) == pytest.approx(0.82)
    assert o3.sleep_deficit_index(5.5) == pytest.approx(0.75)
    assert o3.composite_sleep_prior(answers) == pytest.approx(0.5 * 0.75
                                                             + 0.3 * 0.75
                                                             + 0.2 * (1 / 3))
    assert o3.sleep_minutes(5.5) == 330.0


# --- the symbol check, now covering three sheets --------------------------

def test_o3_introduces_no_symbol_the_workbook_leaves_undefined():
    """The first O-sheet of the three for which this is true. Checked here as
    well as in test_onboarding_symbols_resolve so that a future edit to O3
    cannot quietly add one."""
    from sahacore.data.onboarding_symbols import analyse

    result = analyse()
    o3_holes = {name: used for name, used in result["unresolved"].items()
                if any(e.startswith("O3.") for e in used)}
    assert o3_holes == {}
