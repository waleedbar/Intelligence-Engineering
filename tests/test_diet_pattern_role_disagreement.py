"""What a dietary pattern is FOR, according to two sheets that disagree.

O·O7 makes the pattern supply the mean of every nutrient's initial state:

    O7.1  C_f(0)_i ~ N(mu_pattern_i, sigma2_pattern_i)

'P1 DataMap' row 125 gives the same answer a different job -- "Adjusts w_i,
F_bio, gamma_ij defaults" -- and assigns the BASELINE INTAKE to the four
food-frequency questions instead, routing them into B2, the fast compartment
ODE that produces the very states O7.1 claims to initialise.

Which matters because it changes the size of the gap from 648 numbers to 8
sets of modifiers -- the same shape O8 and O9 already use, and which the
workbook does supply. See docs/parameter-gaps.md.

Read from the loaded DataMap registry rather than restated, so if either side
is ever corrected this fails and the finding gets rewritten.
"""
import json
from pathlib import Path

import pytest

DATA_DIR = Path(__file__).parent.parent / "sahacore" / "data"


def _load(name):
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def onboarding_fields():
    return {f["engine_variable"]: f for f in _load("datamap.json")["onboarding_fields"]}


@pytest.fixture(scope="module")
def o7():
    return _load("onboarding_o7.json")


def test_o7_makes_the_pattern_supply_the_mean(o7):
    o7_1 = next(e for e in o7["equations"] if e["equation_id"] == "O7.1")
    assert "mu_pattern" in o7_1["formula"]
    assert o7_1["engine_target"] == "Layer E: x_hat(0)[1..81]"


def test_the_datamap_makes_it_adjust_weights_instead(onboarding_fields):
    """THE DISAGREEMENT. Not a mean anywhere in it."""
    diet = onboarding_fields["diet_type"]
    feeds = diet["mapping_logic"]

    assert "w" in feeds and "F_bio" in feeds, feeds
    assert "gamma" in feeds.lower() or "γ" in feeds, feeds
    # The word the O7 reading would need, and which is absent.
    assert "mean" not in feeds.lower()
    assert "prior" not in feeds.lower()


def test_the_datamap_sources_the_baseline_from_the_servings_questions(
        onboarding_fields):
    """And routes them into B2 -- the fast compartment ODE, which produces
    exactly the 81 states O7.1 says it initialises."""
    for field in ("fruit_servings", "veg_servings"):
        row = onboarding_fields[field]
        assert row["mapping_logic"].startswith("Baseline"), row
        assert "B2" in row["equations"], row


def test_the_two_readings_route_to_different_equations(onboarding_fields):
    """The pattern goes to absorption/emptying/clearance; the servings go to
    the compartment that holds the state. They are not the same claim."""
    pattern_eqs = set(onboarding_fields["diet_type"]["equations"].split(","))
    serving_eqs = set(onboarding_fields["fruit_servings"]["equations"].split(","))

    pattern_eqs = {e.strip() for e in pattern_eqs}
    serving_eqs = {e.strip() for e in serving_eqs}

    assert "B4" in pattern_eqs          # total clearance
    assert "A5" in pattern_eqs          # gastric emptying
    assert "B2" not in pattern_eqs      # NOT the state-bearing compartment
    assert "B2" in serving_eqs          # which the servings DO reach
