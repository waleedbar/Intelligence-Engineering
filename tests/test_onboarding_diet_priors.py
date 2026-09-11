"""ONB-007 — 'O·O7 Diet Pattern Priors', equations O7.1-O7.4.

The sheet that specifies the starting value of 81 of the engine's 219 states
and supplies not one number towards it. Most of these tests pin that absence,
because an absence nothing asserts is an absence that gets filled in by
accident later.
"""
import json
from pathlib import Path

import pytest

from sahacore.onboarding import diet_priors as o7
from sahacore.onboarding.parameters import load_o7_patterns

DATA_DIR = Path(__file__).parent.parent / "sahacore" / "data"


def _load(name):
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def sheet():
    return _load("onboarding_o7.json")


@pytest.fixture(scope="module")
def ui():
    return _load("step_questions.json")


# --- the headline finding -------------------------------------------------

def test_o7_1_specifies_81_states_and_gives_no_means(sheet):
    """THE FINDING, and it is the largest gap in the build.

    O7.1 is C_f(0)_i ~ N(mu_pattern_i, sigma2_pattern_i) and its engine
    target is 'Layer E: x_hat(0)[1..81]' -- the starting value of every
    nutrient the engine tracks. Eight patterns x 81 nutrients = 648 MEANS,
    and the sheet gives none.

    What it gives is prose, one line per pattern.

    648 rather than 1,296: this test used to count the variances as missing
    too. They are not -- see the test below. The mean is the gap.
    """
    o7_1 = next(e for e in sheet["equations"] if e["equation_id"] == "O7.1")
    assert o7_1["engine_target"] == "Layer E: x_hat(0)[1..81]"
    assert "mu_pattern" in o7_1["formula"]
    assert "sigma2_pattern" in o7_1["formula"]
    # The sheet declining to give a range is itself the evidence.
    assert o7_1["value_range"] == "varies per nutrient"

    # 8 patterns x 81 nutrients.
    nutrients = _load("nutrients_81.json")
    rows = nutrients if isinstance(nutrients, list) else next(
        v for v in nutrients.values() if isinstance(v, list))
    assert len(rows) == 81
    assert len(sheet["patterns"]) * len(rows) == 648

    # And the nutrient registry has no baseline-intake column to hold them.
    columns = set(rows[0])
    for absent in ("mu_pattern", "baseline_intake", "expected_intake",
                   "sigma2_pattern"):
        assert absent not in columns


def test_the_variance_half_is_supplied_by_another_module():
    """THE CORRECTION, pinned so it cannot quietly revert.

    An earlier version of this build reported 1,296 absent numbers -- 8 x 81
    x (mean, variance). The variance is not absent. 'O·O12-O14 State Init'
    O13.2 reads:

        "PK state variances | sigma^2 = (0.3-0.5)^2 per typed
         nutrient/exposure prior unless a stronger source exists | [1..162]"

    One rule for all 162 PK states, pattern-independent -- the width of a
    prior is a state-initialisation concern that the workbook assigns to O13,
    never to O7.

    HOW THE MISS HAPPENED, which is the part worth keeping: the search that
    concluded "none of them" looked for the SYMBOL sigma2_pattern, which
    really does appear only on O·O7 and its duplicate. O13.2 supplies the
    same quantity under a different name in another module, so a symbol
    search could not see it. A name search answers "is this name used
    elsewhere", not "is this number known".

    This test states the correction rather than reading the sheet, because
    ONB-012-014 are not imported yet. When they are, it should be rewritten
    to read O13.2 from the extracted JSON -- and it will fail here first,
    which is the point.
    """
    import sahacore.onboarding.diet_priors as module

    assert "O13.2" in module.__doc__
    assert "0.3-0.5" in module.__doc__
    # And the refusal must not claim the variance is missing.
    with pytest.raises(o7.PriorNotSupplied) as raised:
        o7.nutrient_prior("Mediterranean", "N01")
    assert "1,296" not in str(raised.value)
    assert "648 means" in str(raised.value)


def test_nutrient_prior_refuses_rather_than_inventing_one():
    """A stub returning 0.0, or a population average, would put an invented
    initial condition into 81 states and nothing downstream could tell.

    The refusal is a distinct exception type so it cannot be mistaken for a
    mistyped nutrient id, and so the day it is fixed the fix is greppable.
    """
    with pytest.raises(o7.PriorNotSupplied, match="648 means"):
        o7.nutrient_prior("Mediterranean", "N01")
    with pytest.raises(LookupError):
        o7.nutrient_prior("Vegan", "N42")


def test_the_pattern_table_is_prose_and_stays_prose(sheet):
    """If numbers ever appear in the nutrient-shift column, that is the
    missing prior table arriving and it must be read, not absorbed."""
    import re
    standalone = re.compile(r"(?<![A-Za-z0-9-])\d")
    for pattern in sheet["patterns"]:
        assert pattern["key_nutrient_shifts"]
        assert not standalone.search(pattern["key_nutrient_shifts"]), pattern
        assert pattern["typical_deficiencies"]

    # 'omega-3' and 'B12' must NOT count as numbers -- the digits are part of
    # the nutrient's name, the same trap as the hyphen in 'dose-response'.
    assert not standalone.search("High omega-3, olive oil, fiber")
    assert not standalone.search("B12, Iron (heme), Zinc, Omega-3")
    assert standalone.search("250 mg omega-3")


# --- the three-way disagreement about the pattern list --------------------

def test_the_sheet_declares_two_patterns_absent_from_the_interface(sheet):
    """It knows. DASH and Carnivore are marked 'Not in current UI' by the
    sheet's own column, which is worth crediting."""
    declared = {p["pattern"] for p in sheet["patterns"]
                if p["ui_status"] == "DECLARED_NOT_IN_UI"}
    assert declared == {"DASH", "Carnivore"}


def test_the_interface_offers_a_pattern_the_sheet_never_heard_of(sheet, ui):
    """THE FINDING THE SHEET DOES NOT KNOW ABOUT.

    Step 3 offers six diet options. This sheet describes eight patterns and
    'P1 DataMap' row 125 says "Radio (8 options)". None of the eight is
    Intermittent Fasting, and the interface offers it -- so a user who
    selects it gets no prior, no nutrient shift and no deficiency list.
    """
    offered = next(q for q in ui["questions"]
                   if q["variable"] == "diet_pattern")["answer_options"]
    assert "Intermittent Fasting" in offered
    assert len(offered) == 6
    assert len(sheet["patterns"]) == 8

    described = {p["pattern"] for p in sheet["patterns"]}
    labelled = {p["ui_label"] for p in sheet["patterns"]}
    assert "Intermittent Fasting" not in described
    assert "Intermittent Fasting" not in labelled
    assert "Intermittent Fasting" in sheet["ui_options_no_pattern_claims"]

    with pytest.raises(o7.PriorNotSupplied, match="no dietary pattern"):
        o7.pattern_for_ui_option("Intermittent Fasting")


def test_two_more_labels_are_near_misses_and_are_not_bridged(sheet):
    """'Mediterranean Diet' plainly means the interface's 'Mediterranean',
    and 'Low-carb/Ketogenic' its 'Low-carb/Keto'. Matching on "plainly means"
    is the inference this build refuses -- the same one refused for f_u_ref
    and for standing_hrs -- so both are recorded rather than bridged.

    They are a DIFFERENT kind of problem from Intermittent Fasting, which has
    no candidate at all, and the distinction is the point of recording them.
    """
    unclaimed = sheet["ui_options_no_pattern_claims"]
    assert set(unclaimed) == {"Low-carb/Keto", "Mediterranean",
                              "Intermittent Fasting"}

    labels = {p["ui_label"] for p in sheet["patterns"]}
    assert "Mediterranean Diet" in labels        # the near-miss
    assert "Low-carb/Ketogenic" in labels        # the other one

    # Exact matches still work.
    assert o7.pattern_for_ui_option("Vegetarian").pattern == "Vegetarian"
    assert o7.pattern_for_ui_option("Vegan").pattern == "Vegan"
    assert o7.pattern_for_ui_option("Paleo").pattern == "Paleo"


def test_the_catalogue_is_readable_as_objects():
    patterns = o7.patterns()
    assert len(patterns) == 8
    assert [p.pattern for p in patterns][0] == "Standard/Balanced"
    assert all(p.key_nutrient_shifts and p.typical_deficiencies
               for p in patterns)
    assert {p.ui_status for p in patterns} <= {
        "MATCHES_UI_EXACTLY", "DECLARED_NOT_IN_UI",
        "LABEL_DOES_NOT_MATCH_ANY_UI_OPTION"}
    assert load_o7_patterns()[0]["pattern"] == "Standard/Balanced"


# --- what IS buildable ----------------------------------------------------

def test_o7_2_adds_precisions_and_narrows_with_every_day():
    """sigma2_post = 1/(1/sigma2_prior + k/sigma2_obs). Precision-weighted and
    correct as written -- it needs no missing constant, only the two
    variances and the day count."""
    prior, observed = 4.0, 1.0

    # With no observations the posterior is exactly the prior.
    assert o7.posterior_variance(prior, observed, 0) == pytest.approx(prior)

    # Each day adds one unit of observation precision.
    assert o7.posterior_variance(prior, observed, 1) == pytest.approx(1 / (0.25 + 1))
    assert o7.posterior_variance(prior, observed, 4) == pytest.approx(1 / (0.25 + 4))

    # And it narrows monotonically.
    variances = [o7.posterior_variance(prior, observed, k) for k in range(0, 30)]
    assert variances == sorted(variances, reverse=True)
    assert variances[-1] < variances[0]


def test_o7_2_refuses_a_non_positive_variance():
    with pytest.raises(ValueError, match="must be positive"):
        o7.posterior_variance(0, 1.0, 5)
    with pytest.raises(ValueError, match="must be positive"):
        o7.posterior_variance(1.0, -1, 5)


def test_prior_weight_falls_from_one_and_makes_o7_3_checkable():
    prior, observed = 4.0, 1.0
    assert o7.prior_weight(prior, observed, 0) == pytest.approx(1.0)

    weights = [o7.prior_weight(prior, observed, k) for k in range(0, 30)]
    assert weights == sorted(weights, reverse=True)
    assert weights[-1] < 0.05


def test_o7_3_reports_the_sheets_schedule_and_names_the_gap_between():
    """The sheet gives day 7 and day 14 and says nothing about days 8-13, so
    they are named rather than assigned to a side.

    And the schedule is NOT a computation: which source actually dominates
    depends on the ratio of the two variances, and O7.1 supplies neither.
    """
    assert o7.dominant_source(0) == "prior"
    assert o7.dominant_source(7) == "prior"
    assert o7.dominant_source(8) == "transition"
    assert o7.dominant_source(13) == "transition"
    assert o7.dominant_source(14) == "logs"
    assert o7.dominant_source(90) == "logs"

    with pytest.raises(ValueError):
        o7.dominant_source(-1)


def test_o7_4_divides_by_ten_and_the_band_encoding_is_missing(sheet, ui):
    """DQI = (fruit_serv + veg_serv)/10, declared 0-1.

    The interface collects BANDS -- '0 / 1-2 / 3-4 / 5+' -- and no sheet in
    the workbook says what they are worth. O5.2 gives midpoints for alcohol
    and O5.5 gives (wrong) ones for sugary drinks; fruit and vegetables get
    none. So the declared 0-1 range cannot be verified, and the function
    takes servings rather than a band.
    """
    assert o7.diet_quality_index(0, 0) == 0.0
    assert o7.diet_quality_index(5, 5) == pytest.approx(1.0)
    assert o7.diet_quality_index(1, 2) == pytest.approx(0.3)

    for variable in ("fruit_serv", "veg_serv"):
        question = next(q for q in ui["questions"]
                        if q["variable"] == variable)
        assert question["answer_options"] == ["0", "1-2", "3-4", "5+"]

    # Nothing in the O-sheet registries encodes those bands.
    from sahacore.onboarding.parameters import load_o5_encoding
    for encodes in ("pack_years", "units_week", "tobacco_idx"):
        assert "fruit" not in str(load_o5_encoding(encodes)).lower()

    o7_4 = next(e for e in sheet["equations"] if e["equation_id"] == "O7.4")
    assert o7_4["value_range"] == "0-1"


def test_o7_introduces_no_symbol_or_routing_that_has_not_been_reported():
    from sahacore.data.onboarding_symbols import (
        KNOWN_BROKEN_ROUTINGS, KNOWN_UNRESOLVED, analyse,
    )

    result = analyse()
    new = sorted(set(result["unresolved"]) - set(KNOWN_UNRESOLVED))
    assert new == [], f"new undefined symbols: {new}"

    broken = sorted({r["equation_id"] for r in result["broken_routings"]}
                    - set(KNOWN_BROKEN_ROUTINGS))
    assert broken == [], f"new broken routings: {broken}"
