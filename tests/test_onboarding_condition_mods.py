"""ONB-008 — 'O·O8 Condition Modifiers'.

The only O-sheet with no numbered equations, and the one whose most important
content is a single sentence of prose. Most of these tests are about that
sentence and about the four gates, because both are instructions that a
careless read would drop.
"""
import json
import math
from pathlib import Path

import pytest

from sahacore.onboarding import condition_mods as o8

DATA_DIR = Path(__file__).parent.parent / "sahacore" / "data"


def _load(name):
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def sheet():
    return _load("onboarding_o8.json")


@pytest.fixture(scope="module")
def ui():
    return _load("step_questions.json")


# --- the compatibility rule ----------------------------------------------

def test_the_rule_is_captured_verbatim(sheet):
    rule = sheet["compatibility_rule"]
    for fragment in ("ODDS multiplier", "logit", "sigmoid", "F_max", "[0,1]"):
        assert fragment in rule, fragment
    assert o8.compatibility_rule() == rule


def test_with_no_shifts_the_rule_returns_f_base_exactly():
    """The identity a compatible rewrite has to satisfy. If it did not, the
    transformation would be a different model rather than a safe way to
    express the same one."""
    for f_base, f_max in [(0.4, 0.9), (0.05, 1.0), (0.75, 0.8)]:
        assert o8.bounded_absorption(f_base, f_max) == pytest.approx(f_base)


def test_a_multiplier_becomes_a_log_odds_shift():
    assert o8.delta_logit_from_multiplier(1.0) == 0.0
    assert o8.delta_logit_from_multiplier(math.e) == pytest.approx(1.0)
    assert o8.delta_logit_from_multiplier(2.0) == pytest.approx(math.log(2))
    # Below one it reduces absorption.
    assert o8.delta_logit_from_multiplier(0.5) < 0


def test_a_zero_or_negative_multiplier_is_refused_not_clamped():
    """'Absorbs nothing' is a different claim from a large negative shift, and
    the sheet does not make it."""
    for bad in (0, -1.0):
        with pytest.raises(ValueError, match="no logarithm"):
            o8.delta_logit_from_multiplier(bad)


def test_the_rule_stays_inside_the_bound_where_direct_multiplication_does_not():
    """THE WHOLE POINT OF THE RULE, in one comparison.

    F_base 0.8 multiplied by 1.5 is 1.2 -- not a fraction of anything, and
    the sheet forbids it in the same sentence that gives the alternative.
    Through log-odds it is 0.83, still inside F_max.
    """
    naive = 0.8 * 1.5
    assert naive > 1.0

    bounded = o8.apply_multipliers(0.8, 0.9, (1.5,))
    assert bounded == pytest.approx(0.830769, abs=1e-6)
    assert 0.8 < bounded < 0.9


@pytest.mark.parametrize("multiplier", [1.5, 10.0, 1000.0, 1e9])
def test_no_multiplier_however_large_can_escape_f_max(multiplier):
    f_max = 0.9
    result = o8.apply_multipliers(0.4, f_max, (multiplier,))
    assert 0.0 < result < f_max


def test_shifts_compose_by_addition_in_log_odds():
    """Two multipliers applied together must equal their product applied once
    -- that is what makes the sum in the formula the right operation."""
    together = o8.apply_multipliers(0.4, 0.9, (1.5, 2.0))
    at_once = o8.apply_multipliers(0.4, 0.9, (3.0,))
    assert together == pytest.approx(at_once)


def test_the_rule_refuses_an_f_base_outside_its_domain():
    with pytest.raises(ValueError, match="F_max is"):
        o8.bounded_absorption(0.4, 1.5)
    for bad in (0.0, 0.9, 1.2):
        with pytest.raises(ValueError, match="F_base is"):
            o8.bounded_absorption(bad, 0.9)


def test_f_max_is_a_real_column_of_the_nutrient_registry():
    """The rule composes with what is already imported rather than needing a
    number nobody has."""
    nutrients = _load("nutrients_81.json")
    rows = nutrients if isinstance(nutrients, list) else next(
        v for v in nutrients.values() if isinstance(v, list))
    assert "f_max" in rows[0]
    assert all(0.0 < row["f_max"] <= 1.0 for row in rows)


# --- the gates ------------------------------------------------------------

def test_five_rows_are_gated_and_four_of_them_gate_a_number(sheet):
    gated = [c for c in sheet["conditions"] if c["gate"]]
    with_numbers = [c for c in gated if c["modifiers"]]
    assert len(gated) == 5
    assert {c["condition"] for c in with_numbers} == {
        "IBS", "Cardiovascular context", "Osteoporosis/osteopenia",
        "Stroke history"}
    # Celiac's gate qualifies a described modifier with no factor attached.
    described = set(gated_names(gated)) - set(gated_names(with_numbers))
    assert described == {"Celiac disease"}


def gated_names(rows):
    return [r["condition"] for r in rows]


def test_a_gated_factor_is_never_returned_by_omission():
    """THE SAFETY PROPERTY. `gate_satisfied` is keyword-only and defaults to
    False, so the careless call -- the one that just asks for the number --
    raises instead of applying a modifier the sheet withheld."""
    for name, pathway in [("Cardiovascular context", "Z7"),
                          ("Osteoporosis/osteopenia", "Z11"),
                          ("Stroke history", "Z13"),
                          ("IBS", "Z3")]:
        with pytest.raises(o8.GateNotSatisfied, match="gate_satisfied=True"):
            o8.eta_multiplier(name, pathway)
        # And it IS available to a caller who states the gate holds.
        assert o8.eta_multiplier(name, pathway, gate_satisfied=True) > 1.0


def test_gate_satisfied_cannot_be_passed_positionally():
    """Keyword-only on purpose: a positional boolean is exactly the kind of
    argument that gets passed by accident."""
    import inspect
    parameter = inspect.signature(o8.eta_multiplier).parameters["gate_satisfied"]
    assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
    assert parameter.default is False


def test_an_ungated_modifier_needs_no_ceremony():
    assert o8.eta_multiplier("Type 2 Diabetes", "Z1") == 1.5
    assert o8.eta_multiplier("Type 2 Diabetes", "Z6") == 2.0
    assert o8.eta_multiplier("CKD (Stage 3+)", "Z9") == 3.0
    assert o8.eta_multiplier("Hypertension (HTN)", "Z7") == 1.3


def test_every_row_keeps_its_evidence_role(sheet):
    """These are warnings against a specific misreading -- 'do not force K
    malabsorption', 'Timing, not global absorption extent', 'Clinical
    context; not an absorption multiplier'. Losing one loses the warning."""
    for condition in sheet["conditions"]:
        assert condition["evidence_role"]
    roles = {c["evidence_role"] for c in sheet["conditions"]}
    assert any("do not force K malabsorption" in r for r in roles)
    assert any("Timing, not global absorption extent" in r for r in roles)


# --- the gap --------------------------------------------------------------

def test_more_than_half_the_declared_pathway_links_have_no_factor(sheet):
    """THE FINDING. The Z-pathways column declares 20 condition-to-pathway
    links and only 9 carry a modifier.

    Celiac disease declares Z5, Z11 and Z12 and quantifies none of them;
    GERD declares Z3 and quantifies none. Only Type 2 Diabetes covers
    everything it declares.
    """
    declared = sum(len(c["z_pathways_declared"]) for c in sheet["conditions"])
    quantified = sum(len(c["modifiers"]) for c in sheet["conditions"])
    missing = sum(len(c["z_pathways_without_a_modifier"])
                  for c in sheet["conditions"])

    assert (declared, quantified, missing) == (20, 9, 11)
    assert missing > quantified

    complete = [c["condition"] for c in sheet["conditions"]
                if not c["z_pathways_without_a_modifier"]]
    assert complete == ["Type 2 Diabetes"]


def test_a_declared_pathway_with_no_factor_raises_rather_than_returning_one():
    """'Declared affected, effect unstated' and 'no effect' are different
    claims, and 1.0 would silently turn the first into the second."""
    with pytest.raises(o8.ModifierNotSupplied, match="no factor for it"):
        o8.eta_multiplier("Hypertension (HTN)", "Z9")
    with pytest.raises(o8.ModifierNotSupplied, match="no factor for it"):
        o8.eta_multiplier("Celiac disease", "Z11")
    with pytest.raises(o8.ModifierNotSupplied, match="no factor for it"):
        o8.eta_multiplier("GERD/Acid reflux", "Z3")


def test_a_pathway_the_condition_never_declared_raises_differently():
    with pytest.raises(o8.ModifierNotSupplied, match="does not declare"):
        o8.eta_multiplier("Type 2 Diabetes", "Z9")


def test_the_unquantified_links_are_reported_as_a_set():
    gaps = o8.declared_pathways_without_a_modifier()
    assert gaps["Celiac disease"] == ("Z5", "Z11", "Z12")
    assert gaps["GERD/Acid reflux"] == ("Z3",)
    assert "Type 2 Diabetes" not in gaps
    assert sum(len(v) for v in gaps.values()) == 11


# --- against the UI contract ---------------------------------------------

def test_the_interface_offers_a_condition_this_sheet_has_no_row_for(ui):
    """Step 5's gastrointestinal question names 'IBS, GERD, Celiac, UC,
    NAFLD'. There is no UC row -- the same shape as O7's Intermittent
    Fasting."""
    gastro = next(q for q in ui["questions"]
                  if q["step_number"] == 5 and "IBS" in q["answer_options_text"])
    assert "UC" in gastro["answer_options_text"]

    modelled = {row.condition for row in o8.conditions()}
    assert not any("UC" == name or "olitis" in name for name in modelled)

    with pytest.raises(o8.ModifierNotSupplied, match="not one of the sheet"):
        o8.condition("UC")


def test_only_one_of_step_5s_five_questions_gives_a_checkable_list(ui):
    """So the condition set is unknown and O8's ten rows cannot be checked
    for completeness in either direction.

    Two of the five name any condition at all, and one of those trails off
    with 'etc.'.
    """
    step_5 = [q for q in ui["questions"] if q["step_number"] == 5]
    assert len(step_5) == 5

    naming = [q for q in step_5 if ":" in q["answer_options_text"]]
    complete = [q for q in naming
                if "etc" not in q["answer_options_text"].lower()]
    assert len(naming) == 2
    assert len(complete) == 1
