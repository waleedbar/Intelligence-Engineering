"""ONB-006 — 'O·O6 Family History', equations O6.1-O6.11.

The best-sourced sheet in the build: every relative risk names the study it
came from, which no other O-sheet does for any constant. It also states each
risk four times, so most of what is worth testing here is the sheet against
itself, and the arithmetic recomputed rather than trusted.
"""
import json
import math
from pathlib import Path

import pytest

from sahacore.onboarding import family_history as o6
from sahacore.onboarding.parameters import (
    load_o6_pathways, load_o6_relative_risks, load_o6_shifts,
)

DATA_DIR = Path(__file__).parent.parent / "sahacore" / "data"


def _load(name):
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def sheet():
    return _load("onboarding_o6.json")


@pytest.fixture(scope="module")
def ui():
    return _load("step_questions.json")


# --- provenance -----------------------------------------------------------

def test_every_relative_risk_names_its_source(sheet):
    """WORTH SAYING BECAUSE MOST OF docs/parameter-gaps.md IS THE OPPOSITE.

    O1's e_WHtR has no formula, O2's HR_Arem is a curve nobody drew, O5's SSB
    midpoints are not midpoints. Here every number cites a study.
    """
    conditions = sheet["conditions"]
    assert len(conditions) == 6
    for condition in conditions:
        assert condition["source"], condition
        assert condition["relative_risk"] > 1.0
        assert condition["z_pathway_codes"]

    sources = {c["source"] for c in conditions}
    assert "EPIC-InterAct consortium" in sources
    assert "AHA journal meta-analysis" in sources


# --- the arithmetic, recomputed ------------------------------------------

def test_every_log_relative_risk_is_recomputed_not_trusted(sheet):
    for condition in sheet["conditions"]:
        computed = math.log(condition["relative_risk"])
        assert computed == pytest.approx(condition["log_relative_risk"],
                                         abs=1e-3), condition


def test_the_t2d_tolerance_is_1e_3_because_its_risk_is_a_rounded_e(sheet):
    """THE ONE ROW THAT NEEDS EXPLAINING, and the same shape already recorded
    for the bistability guard: each column is rounded independently.

    ln(2.72) = 1.000632, which rounds to 1.001, and the sheet writes 1.000.
    That is not an error -- the relative risk is *e*, whose log is exactly 1,
    and 2.72 is e rounded for display. So the ln column is the exact one and
    the RR column is the rounded one, which is why the module reads the
    sheet's pre-computed log rather than recomputing ln(2.72).
    """
    t2d = next(c for c in sheet["conditions"] if c["condition"] == "Type 2 Diabetes")
    assert t2d["relative_risk"] == 2.72
    assert t2d["log_relative_risk"] == 1.000

    assert math.log(2.72) == pytest.approx(1.000632, abs=1e-6)
    assert round(math.log(2.72), 3) == 1.001          # not what the sheet says
    assert math.log(math.e) == 1.0                    # what it means
    assert round(math.e, 2) == 2.72

    # Every other row is simply correct rounding to three decimals, which is
    # an error of at most 5e-4. T2D's 6.3e-4 is the only one that is not, and
    # the reason is above.
    for condition in sheet["conditions"]:
        error = abs(math.log(condition["relative_risk"])
                    - condition["log_relative_risk"])
        if condition["condition"] == "Type 2 Diabetes":
            assert error > 5e-4
        else:
            assert error <= 5e-4, condition


def test_the_module_uses_the_sheets_log_not_its_own(sheet):
    """For T2D the two differ in the third decimal, and the sheet's declared
    range ('0 or 1.000') was written against its own."""
    assert o6.condition_shift("FH_T2D", present=True) == 1.000
    assert o6.condition_shift("FH_T2D", present=True) != math.log(2.72)
    assert o6.condition_shift("FH_T2D", present=False) == 0.0


# --- four statements of each risk ----------------------------------------

def test_each_risk_is_stated_four_times_and_all_four_agree(sheet):
    """Inside the formula as ln(RR), again pre-computed, again in the
    Variables cell, and again in the reference table. Nothing here rests on
    one cell."""
    by_log = {c["log_relative_risk"]: c for c in sheet["conditions"]}
    per_condition = [e for e in sheet["equations"] if e["indicator"]]
    assert len(per_condition) == 6

    for equation in per_condition:
        assert equation["rr_in_formula"] == equation["rr_in_variables"]
        assert math.log(equation["rr_in_formula"]) == pytest.approx(
            equation["log_in_formula"], abs=1e-3)
        table_row = by_log[equation["log_in_formula"]]
        assert table_row["relative_risk"] == equation["rr_in_formula"]


def test_the_registry_carries_all_six_risks_and_shifts():
    risks, shifts = load_o6_relative_risks(), load_o6_shifts()
    assert set(risks) == set(shifts) == {
        "FH_T2D", "FH_CVD", "FH_stroke", "FH_colon", "FH_breast", "FH_AD"}
    for indicator, risk in risks.items():
        assert risk > 1.0
        assert shifts[indicator] > 0


# --- against the UI contract ---------------------------------------------

def test_step_6_collects_exactly_the_six_histories_the_equations_read(ui):
    """In BOTH directions. A history collected and never read is a question
    asked for nothing; one read and never collected is an equation that
    cannot run."""
    asked = {q["variable"] for q in ui["questions"]
             if q["variable"].startswith("FH_")}
    read = set(load_o6_shifts())
    assert asked == read

    step_6 = {q["step_number"] for q in ui["questions"]
              if q["variable"].startswith("FH_")}
    assert step_6 == {6}


# --- the equations --------------------------------------------------------

def test_o6_1_is_zero_without_a_history_and_ln_rr_with_one():
    assert o6.log_hazard_shift(False, 2.0) == 0.0
    assert o6.log_hazard_shift(True, 2.0) == pytest.approx(math.log(2.0))
    # RR = 1 is no shift even when the history is present.
    assert o6.log_hazard_shift(True, 1.0) == 0.0


def test_o6_1_refuses_a_relative_risk_with_no_logarithm():
    with pytest.raises(ValueError, match="has no logarithm"):
        o6.log_hazard_shift(True, 0)


def test_all_shifts_are_zero_for_a_user_with_no_family_history():
    clean = o6.FamilyHistory()
    assert not clean.any_positive()
    assert set(o6.all_shifts(clean).values()) == {0.0}


def test_a_single_history_moves_only_its_own_shift():
    diabetic_family = o6.FamilyHistory(FH_T2D=True)
    shifts = o6.all_shifts(diabetic_family)
    assert shifts["FH_T2D"] == 1.000
    assert [v for k, v in shifts.items() if k != "FH_T2D"] == [0.0] * 5


def test_o6_9s_phi_is_the_standard_normal_cdf():
    """Phi is named and not defined on the sheet, so it is the textbook one --
    checked at points anyone can verify rather than against a table."""
    assert o6.liability_probability(0, 0, 0, 1) == pytest.approx(0.5)
    assert o6.liability_probability(1, 0, 0, 1) == pytest.approx(0.8413447, abs=1e-6)
    assert o6.liability_probability(-1, 0, 0, 1) == pytest.approx(0.1586553, abs=1e-6)
    # l = g + e, so the split does not matter to the probability.
    assert (o6.liability_probability(0.6, 0.4, 0, 1)
            == pytest.approx(o6.liability_probability(0.4, 0.6, 0, 1)))


def test_o6_9_refuses_a_zero_sigma():
    with pytest.raises(ValueError, match="divides by it"):
        o6.liability_probability(1, 0, 0, 0)


def test_o6_8_reduces_to_the_prior_when_the_observation_is_the_mean():
    """mu_post = mu + Sigma_12 Sigma_22^-1 (x2 - mu_2): if x2 == mu_2 the
    update is exactly zero, whatever the covariances are."""
    assert o6.pearson_aitken_posterior(3.0, 0.8, 1.25, 2.0, 2.0) == 3.0
    assert o6.pearson_aitken_posterior(3.0, 0.8, 1.25, 3.0, 2.0) == pytest.approx(4.0)


def test_o6_8_and_o6_9_take_every_missing_input_as_an_argument():
    """THE HONEST FORM FOR A FORMULA WITH NO DATA.

    The sheet names Sigma_12, Sigma_22, mu_2, the liability threshold and
    sigma, and supplies not one of them for any condition. Their mathematics
    is standard and complete; only the values are missing. So they are
    arguments, exactly as O1.9's e_WHtR is -- a module that invented a
    covariance block would be inventing the prior.
    """
    import inspect

    pearson = inspect.signature(o6.pearson_aitken_posterior).parameters
    assert set(pearson) == {"mu", "sigma_12", "sigma_22_inverse", "x2", "mu_2"}
    assert all(p.default is inspect.Parameter.empty for p in pearson.values())

    liability = inspect.signature(o6.liability_probability).parameters
    assert set(liability) == {"genetic", "environmental", "threshold", "sigma"}
    assert all(p.default is inspect.Parameter.empty for p in liability.values())


def test_o6_10_raises_sensitivity_by_thirty_percent_or_not_at_all():
    assert o6.eta_sensitivity(0.5, False) == pytest.approx(0.5)
    assert o6.eta_sensitivity(0.5, True) == pytest.approx(0.65)


def test_o6_10s_relevance_map_is_read_from_the_rr_table(sheet):
    """O6.10 says "FH_relevant per pathway" and gives no mapping. The RR
    table's Z-Pathway Affected column is the only statement of it in the
    workbook, so it is read rather than assembled."""
    pathways = load_o6_pathways()
    assert pathways["FH_T2D"] == ("Z1", "Z6")
    assert pathways["FH_CVD"] == ("Z7",)
    assert pathways["FH_AD"] == ("Z5",)

    assert o6.relevant_pathways(o6.FamilyHistory()) == frozenset()
    assert o6.relevant_pathways(o6.FamilyHistory(FH_T2D=True)) == {"Z1", "Z6"}
    assert o6.relevant_pathways(
        o6.FamilyHistory(FH_T2D=True, FH_CVD=True)) == {"Z1", "Z6", "Z7"}


def test_o6_11_inflates_variance_and_refuses_to_decide_which_history(sheet):
    """THE FINDING. "sigma2_base * 1.5 if FH positive" does not say WHICH of
    the six histories, and the two readings differ materially:

      * any of six ticked  -> a user with one distant relative gets the whole
                              prior inflated, on every pathway
      * this pathway's own -> only the pathways that history touches

    So `variance_inflation` takes an explicit boolean rather than a
    FamilyHistory. Choosing would be inventing the prior.
    """
    assert o6.variance_inflation(0.04, False) == pytest.approx(0.04)
    assert o6.variance_inflation(0.04, True) == pytest.approx(0.06)

    import inspect
    assert set(inspect.signature(o6.variance_inflation).parameters) == {
        "sigma2_base", "fh_positive"}

    o6_11 = next(e for e in sheet["equations"] if e["equation_id"] == "O6.11")
    assert "if FH positive" in o6_11["formula"]
    # The sheet names no particular history in the formula.
    assert not any(indicator in o6_11["formula"] for indicator in load_o6_shifts())


def test_o6_introduces_no_symbol_or_routing_that_has_not_been_reported():
    from sahacore.data.onboarding_symbols import (
        KNOWN_BROKEN_ROUTINGS, KNOWN_UNRESOLVED, analyse,
    )

    result = analyse()
    new = sorted(set(result["unresolved"]) - set(KNOWN_UNRESOLVED))
    assert new == [], f"new undefined symbols: {new}"

    broken = sorted({r["equation_id"] for r in result["broken_routings"]}
                    - set(KNOWN_BROKEN_ROUTINGS))
    assert broken == [], f"new broken routings: {broken}"
