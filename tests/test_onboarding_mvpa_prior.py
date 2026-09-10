"""ONB-002, the physical-activity prior.

Authorities: 'O·O2 MVPA Prior' (order 72) and 'P1 Activities 50' (order 46).
QA required by 'O · Onboarding Canonical': "range 0..100; monotone MET-min".

Six of the sheet's eight equations are implemented. The other two are pinned
as gaps with the symbol each waits on, so "not implemented" stays a fact
about the workbook rather than a gap in the effort.
"""
import json
from pathlib import Path

import pytest

from sahacore.onboarding import mvpa_prior as o2
from sahacore.onboarding.parameters import load_activity_mets, load_o2_encoding

DATA_DIR = Path(__file__).parent.parent / "sahacore" / "data"


@pytest.fixture(scope="module")
def sheet() -> dict:
    return json.loads((DATA_DIR / "onboarding_o2.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def catalogue() -> dict:
    return json.loads((DATA_DIR / "activities_50.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def encoding() -> dict:
    return load_o2_encoding()


def _answers(encoding, frequency_mod, frequency_vig, duration, sitting=0.0):
    return o2.ActivityAnswers(
        moderate_sessions_per_week=encoding[("Frequency", frequency_mod)],
        vigorous_sessions_per_week=encoding[("Frequency", frequency_vig)],
        minutes_per_session=encoding[("Duration", duration)],
        sitting_hours_per_day=sitting,
    )


# --- the ordinal encoding --------------------------------------------------

def test_the_encoding_is_read_from_the_sheet(encoding, sheet):
    """Eleven options over three fields, each with the sheet's own reason."""
    assert len(encoding) == 11
    declared = {(r["field"], r["option"]): r["numeric_value"]
                for r in sheet["input_encoding"]}
    assert encoding == declared


def test_the_duration_midpoints_are_conservative_not_arithmetic(sheet):
    """'<30 min' maps to 20, not 15; '>60 min' to 75. The sheet calls both
    'Conservative midpoint', and the choice matters: it decides whether an
    unbounded answer is read generously or cautiously."""
    by_option = {r["option"]: r for r in sheet["input_encoding"]
                 if r["field"] == "Duration"}
    assert by_option["<30 min"]["numeric_value"] == 20
    assert by_option["<30 min"]["source"] == "Conservative midpoint"
    assert by_option["30-60 min"]["numeric_value"] == 45
    assert by_option["30-60 min"]["source"] == "Midpoint"
    assert by_option[">60 min"]["numeric_value"] == 75
    assert by_option[">60 min"]["source"] == "Conservative midpoint"


def test_the_frequency_midpoints_are_ordered(encoding):
    values = [encoding[("Frequency", option)]
              for option in ("0", "1-2", "3-4", "5+")]
    assert values == [0, 1.5, 3.5, 5.5]
    assert values == sorted(values)


# --- O2.1, O2.2 -----------------------------------------------------------

def test_o2_1_counts_vigorous_minutes_double(encoding):
    """MVPA_wk = (f_mod*dur) + 2*(f_vig*dur). The doubling is the WHO
    MVPA-equivalent convention, and it is what separates O2.1 from a plain
    minute count."""
    moderate_only = _answers(encoding, "3-4", "0", "30-60 min")
    vigorous_only = _answers(encoding, "0", "3-4", "30-60 min")
    assert o2.mvpa_minutes_per_week(moderate_only) == pytest.approx(3.5 * 45)
    assert (o2.mvpa_minutes_per_week(vigorous_only)
            == pytest.approx(2 * o2.mvpa_minutes_per_week(moderate_only)))


def test_o2_1_is_zero_when_nothing_is_reported(encoding):
    none = _answers(encoding, "0", "0", "<30 min")
    assert o2.mvpa_minutes_per_week(none) == 0.0
    assert o2.met_minutes_per_week(none) == 0.0


def test_o2_2_and_o2_7_divide_by_seven(encoding):
    answers = _answers(encoding, "3-4", "1-2", "30-60 min")
    weekly = o2.mvpa_minutes_per_week(answers)
    assert o2.mvpa_minutes_per_day(weekly) == pytest.approx(weekly / 7)
    met_weekly = o2.met_minutes_per_week(answers)
    assert o2.met_minutes_per_day(met_weekly) == pytest.approx(met_weekly / 7)


# --- O2.3, the deficit index ----------------------------------------------

def test_o2_3_is_bounded_zero_to_one_and_clamps_above_the_target():
    """e_MVPA = 1 - min(1, MVPA_wk/300). The min() is what stops a very
    active user producing a negative deficit."""
    assert o2.mvpa_deficit_index(0) == 1.0
    assert o2.mvpa_deficit_index(150) == pytest.approx(0.5)
    assert o2.mvpa_deficit_index(300) == 0.0
    assert o2.mvpa_deficit_index(3000) == 0.0
    for weekly in (0, 75, 150, 299, 300, 1000):
        assert 0.0 <= o2.mvpa_deficit_index(weekly) <= 1.0


def test_o2_3_falls_as_activity_rises():
    values = [o2.mvpa_deficit_index(w) for w in (0, 100, 200, 300)]
    assert values == sorted(values, reverse=True)


def test_the_deficit_denominator_is_the_who_target(sheet):
    """300 is annotated '300 = WHO upper target' on the sheet, so it belongs
    to the equation rather than being a tunable."""
    o2_3 = next(e for e in sheet["equations"] if e["equation_id"] == "O2.3")
    assert "300" in o2_3["formula"]
    assert "WHO upper target" in o2_3["variables"]


# --- O2.6: MET-minutes, and the QA's 'monotone MET-min' -------------------

def test_o2_6_weights_vigorous_by_met_not_by_two(encoding):
    """O2.1 doubles vigorous minutes; O2.6 weights them 7.5 against 4.5, a
    ratio of 1.67. Neither is a rounding of the other, and a caller that
    needs one must not take the other."""
    moderate = _answers(encoding, "3-4", "0", "30-60 min")
    vigorous = _answers(encoding, "0", "3-4", "30-60 min")
    ratio = o2.met_minutes_per_week(vigorous) / o2.met_minutes_per_week(moderate)
    assert ratio == pytest.approx(7.5 / 4.5)
    assert ratio != pytest.approx(2.0)


def test_met_minutes_are_monotone_in_every_input(encoding):
    """The canonical sheet's QA: 'monotone MET-min'. More sessions, longer
    sessions, or harder sessions must never lower the total."""
    base = _answers(encoding, "1-2", "1-2", "30-60 min")
    more_sessions = _answers(encoding, "3-4", "1-2", "30-60 min")
    longer = _answers(encoding, "1-2", "1-2", ">60 min")
    harder = _answers(encoding, "1-2", "3-4", "30-60 min")
    for greater in (more_sessions, longer, harder):
        assert o2.met_minutes_per_week(greater) > o2.met_minutes_per_week(base)

    ladder = [o2.met_minutes_per_week(_answers(encoding, option, "0", "30-60 min"))
              for option in ("0", "1-2", "3-4", "5+")]
    assert ladder == sorted(ladder)


def test_a_realistic_week_lands_where_it_should(encoding):
    """3-4 moderate and 1-2 vigorous sessions of 30-60 min: 292.5 MVPA
    minutes, just under the WHO 300 target, and 1215 MET-min/week -- well
    above the WHO minimum of 600."""
    answers = _answers(encoding, "3-4", "1-2", "30-60 min", sitting=8)
    assert o2.mvpa_minutes_per_week(answers) == pytest.approx(292.5)
    assert o2.mvpa_deficit_index(292.5) == pytest.approx(0.025)
    assert o2.met_minutes_per_week(answers) == pytest.approx(1215.0)
    assert o2.sedentary_penalty(answers.sitting_hours_per_day) == 0.15


# --- O2.8, the sedentary penalty ------------------------------------------

def test_o2_8_is_a_step_above_six_hours():
    """eta_sed = I(sitting_hrs > 6) * 0.15. Strictly greater, so exactly six
    hours does not fire, and there is nothing between 0 and 0.15."""
    assert o2.sedentary_penalty(0) == 0.0
    assert o2.sedentary_penalty(6) == 0.0
    assert o2.sedentary_penalty(6.01) == 0.15
    assert o2.sedentary_penalty(14) == 0.15
    assert set(o2.sedentary_penalty(h) for h in range(0, 15)) == {0.0, 0.15}


def test_the_encoding_agrees_with_o2_8(encoding):
    """The Activity options carry the same 0.15, and only the sedentary one
    is non-zero."""
    assert encoding[("Activity", "Sedentary")] == 0.15
    for option in ("Lightly Active", "Active", "Very Active"):
        assert encoding[("Activity", option)] == 0


# --- the MET catalogue ----------------------------------------------------

def test_fifty_activities_with_sleep_anchoring_the_scale(catalogue):
    activities = catalogue["activities"]
    assert len(activities) == 50
    by_id = {a["activity_id"]: a for a in activities}
    assert by_id["sleep"]["met"] == 1
    assert min(a["met"] for a in activities) == 1
    assert max(a["met"] for a in activities) == 16.8


def test_bouts_use_the_catalogue_and_refuse_unknown_activities():
    """An unknown activity is an error, not a zero: a silently dropped bout
    understates activity, which biases the deficit index the wrong way."""
    mets = load_activity_mets()
    assert o2.met_minutes_from_bouts([("walk_brisk", 30)], mets) == pytest.approx(4.8 * 30)
    assert o2.met_minutes_from_bouts([], mets) == 0.0
    assert o2.met_minutes_from_bouts(
        [("walk_brisk", 30), ("jog_general", 20)], mets) == pytest.approx(4.8 * 30 + 7.5 * 20)
    with pytest.raises(KeyError):
        o2.met_minutes_from_bouts([("parasailing", 30)], mets)


def test_cluster_impacts_are_signed(catalogue):
    """Sitting quietly is negative on C1 and C2; walking is positive. Losing
    the sign would turn sedentary behaviour into a benefit."""
    by_id = {a["activity_id"]: a for a in catalogue["activities"]}
    assert by_id["sedentary"]["cluster_impact"]["C1"] < 0
    assert by_id["sedentary"]["cluster_impact"]["C2"] < 0
    assert by_id["walk_mod"]["cluster_impact"]["C1"] > 0
    assert by_id["walk_mod"]["cluster_impact"]["C2"] > 0


def test_the_catalogue_carries_six_of_the_twelve_clusters_it_promises(catalogue):
    """THE FINDING. The banner reads '50-Activity Catalog — MET Values +
    12-Cluster Impact Weights'; the columns stop at C6 Oxidative -- not blank
    cells, no columns at all. C7 through C12 are absent for every activity.

    Left absent rather than filled with zeros: a zero would read as 'this
    activity does not affect methylation', which the sheet does not claim.
    """
    assert catalogue["clusters_declared"] == 12
    assert catalogue["clusters_present"] == 6
    assert "12-Cluster" in catalogue["banner"]
    assert catalogue["cluster_ids"] == ["C1", "C2", "C3", "C4", "C5", "C6"]
    for activity in catalogue["activities"]:
        assert set(activity["cluster_impact"]) == {"C1", "C2", "C3", "C4", "C5", "C6"}


def test_six_intensity_labels_disagree_with_the_compendium(catalogue):
    """Recorded, not enforced. The sheet cites the Compendium for its MET
    VALUES and does not say its labels follow the Compendium's bands, so
    holding them to 3.0 and 6.0 would impose a rule the source never claims.

    It still matters: O2.6 splits activity by these labels while weighting
    with 4.5 and 7.5 -- the midpoints of the Compendium's bands.
    """
    disagreements = catalogue["outside_compendium_bands"]
    assert len(disagreements) == 6
    ids = {d["activity_id"] for d in disagreements}
    assert ids == {"cycle_stat", "tennis", "vacuum", "standing_work",
                   "pilates", "tai_chi"}
    for row in disagreements:
        assert row["sheet_intensity"] != row["compendium_intensity"]


# --- the two equations that are not implemented ---------------------------

def test_six_of_eight_equations_are_computable(sheet):
    computable = [e["equation_id"] for e in sheet["equations"] if e["computable"]]
    blocked = [e["equation_id"] for e in sheet["equations"] if not e["computable"]]
    assert computable == ["O2.1", "O2.2", "O2.3", "O2.6", "O2.7", "O2.8"]
    assert blocked == ["O2.4", "O2.5"]


def test_pa_benefit_has_two_incompatible_definitions_and_neither_resolves(sheet):
    """THE FINDING.

    The authority sheet: PA_benefit = 100*(1 - HR_Arem), with HR_Arem a
    'hazard ratio from dose-response curve, Anchored at 150-300 min/wk zone'
    -- described, never given.

    'O · Onboarding Canonical' and 'EQ · Canonical Build Rows', identically:
    PA_benefit = 100*(1-exp(-MET_min_week/K_PA)) -- a saturating exponential,
    a different function, whose K_PA appears in exactly those two cells and
    in neither parameter registry.

    Not implemented, because implementing either means inventing a
    dose-response curve, and PA_benefit feeds Layer C's repair rate.
    """
    o2_4 = next(e for e in sheet["equations"] if e["equation_id"] == "O2.4")
    assert o2_4["computable"] is False
    assert o2_4["unresolved"]["missing_symbol"] == "HR_Arem"
    assert "HR_Arem" in o2_4["formula"]

    conflict = o2_4["unresolved"]["conflicting_definition"]
    assert conflict["missing_symbol"] == "K_PA"
    assert "exp(" in conflict["formula"]
    assert len(conflict["declared_by"]) == 2

    # The module must not have quietly implemented either one.
    assert not hasattr(o2, "pa_benefit")
    assert not hasattr(o2, "modified_repair_rate")


def test_o2_5_waits_on_a_parameter_that_is_in_no_registry(sheet):
    o2_5 = next(e for e in sheet["equations"] if e["equation_id"] == "O2.5")
    assert o2_5["computable"] is False
    assert o2_5["unresolved"]["missing_symbol"] == "rho_pop"

    for filename in ("parameter_registry_192.json", "param_registry_ext20.json"):
        rows = json.loads((DATA_DIR / filename).read_text(encoding="utf-8"))
        assert not [r for r in rows if r.get("symbol") == "rho_pop"], filename
