"""ONB-009 — 'O·O9 Drug-Nutrient Mods'.

Two things make this sheet worth careful tests. It is the first place one
sheet's rule is confirmed by another sheet's arithmetic, and it is the first
place two registries in the same workbook are caught disagreeing about a
safety hazard.
"""
import json
import math
from pathlib import Path

import pytest

from sahacore.onboarding import condition_mods as o8
from sahacore.onboarding import drug_nutrient_mods as o9

DATA_DIR = Path(__file__).parent.parent / "sahacore" / "data"


def _load(name):
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def sheet():
    return _load("onboarding_o9.json")


@pytest.fixture(scope="module")
def veto():
    data = _load("veto_drug_nutrient_339.json")
    return data if isinstance(data, list) else next(
        v for v in data.values() if isinstance(v, list))


# --- O8's rule, verified by O9's numbers ---------------------------------

def test_every_stated_shift_is_the_log_of_its_multiplier(sheet):
    """THE CROSS-SHEET CHECK. 'O·O8 Condition Modifiers' says
    Delta_logit_abs = ln(m); this sheet, written separately, does exactly
    that five times over -- correct to six decimals every time."""
    quantified = [r for r in sheet["interactions"]
                  if r["legacy_multiplier"] is not None]
    assert len(quantified) == 5

    for row in quantified:
        computed = math.log(row["legacy_multiplier"])
        assert computed == pytest.approx(row["delta_logit_abs"], abs=5e-7), row
        # And O8's own conversion agrees with the sheet's stated number.
        assert o8.delta_logit_from_multiplier(
            row["legacy_multiplier"]) == pytest.approx(
            row["delta_logit_abs"], abs=5e-7)


def test_the_five_quantified_rows_are_the_ones_expected(sheet):
    quantified = {(r["drug"], r["nutrient"]): r["legacy_multiplier"]
                  for r in sheet["interactions"]
                  if r["legacy_multiplier"] is not None}
    assert quantified == {
        ("Metformin", "Vitamin B12"): 0.7,
        ("PPIs", "Magnesium"): 0.75,
        ("PPIs", "Calcium"): 0.8,
        ("PPIs", "Vitamin B12"): 0.85,
        ("PPIs", "Iron"): 0.8,
    }


def test_every_multiplier_reduces_absorption(sheet):
    """All five are below 1 and every shift is negative, so a positive one
    would be a sign error rather than a stronger effect."""
    for row in sheet["interactions"]:
        if row["legacy_multiplier"] is None:
            continue
        assert 0 < row["legacy_multiplier"] < 1
        assert row["delta_logit_abs"] < 0


def test_the_shifts_compose_through_o8s_production_equation():
    """A user on PPIs loses B12 absorption; on PPIs AND metformin, more --
    and still inside F_max, which is the point of doing it in log-odds."""
    f_base, f_max = 0.5, 0.9

    ppis = o9.absorption_shifts(("PPIs",), "Vitamin B12")
    both = o9.absorption_shifts(("PPIs", "Metformin"), "Vitamin B12")
    assert len(ppis) == 1 and len(both) == 2

    baseline = o8.bounded_absorption(f_base, f_max)
    on_ppis = o8.bounded_absorption(f_base, f_max, ppis)
    on_both = o8.bounded_absorption(f_base, f_max, both)

    assert on_both < on_ppis < baseline == pytest.approx(f_base)
    assert 0.0 < on_both < f_max


# --- what is NOT an absorption effect ------------------------------------

def test_fifteen_rows_carry_an_action_class_and_no_shift(sheet):
    classes = {r["rule_text"] for r in sheet["interactions"]
               if r["legacy_multiplier"] is None}
    assert classes == {"TIMING", "MONITOR", "VETO", "VETO/MONITOR",
                       "CLEARANCE", "N/A"}
    for row in sheet["interactions"]:
        if row["legacy_multiplier"] is None:
            assert row["delta_logit_abs"] is None
            assert row["delta_logit_text"] == "N/A"


def test_the_two_timing_rows_say_the_nutrient_is_untouched(sheet):
    """THE SAFETY DISTINCTION. Chelation reduces absorption of the DRUG.
    Reading it the other way would cut a calcium target because the user
    takes a thyroid tablet, and the sheet spells that out in the production
    target of both rows."""
    timing = [r for r in sheet["interactions"] if r["rule_text"] == "TIMING"]
    assert {r["drug"] for r in timing} == {"Levothyroxine", "Fluoroquinolones"}

    targets = {r["drug"]: r["production_target"] for r in timing}
    assert "do not alter nutrient F_abs" in targets["Levothyroxine"]
    assert "nutrient F_abs unchanged" in targets["Fluoroquinolones"]


def test_asking_for_a_shift_on_an_action_class_raises_with_the_sheets_words():
    """Returning 0.0 would be as wrong as returning a shift -- it is a
    different kind of effect, not a smaller one."""
    with pytest.raises(o9.NotAnAbsorptionEffect, match="do not alter nutrient"):
        o9.delta_logit_abs("Levothyroxine", "Calcium/iron if co-ingested")
    with pytest.raises(o9.NotAnAbsorptionEffect, match="F_abs unchanged"):
        o9.delta_logit_abs("Fluoroquinolones", "Ca/Mg/Fe/Zn")
    with pytest.raises(o9.NotAnAbsorptionEffect, match="not a multiplier"):
        o9.delta_logit_abs("Warfarin", "Vitamin K")


def test_absorption_shifts_skips_action_classes_rather_than_raising():
    """A user on a timing rule and a real shift still has the real shift.
    Strictness stays where a caller asks about one pair."""
    shifts = o9.absorption_shifts(
        ("Levothyroxine", "Warfarin", "Metformin"), "Vitamin B12")
    assert len(shifts) == 1
    assert shifts[0] == pytest.approx(math.log(0.7), abs=5e-7)


def test_statins_are_critical_and_not_an_absorption_effect(sheet):
    statins = next(r for r in sheet["interactions"] if r["drug"] == "Statins")
    assert statins["severity"] == "CRITICAL"
    assert "not intestinal F_abs" in statins["mechanism_class"]
    assert statins["legacy_multiplier"] is None


# --- the disagreement with the VETO registry -----------------------------

def test_o9_and_the_veto_registry_disagree_about_insulin(sheet, veto):
    """THE FINDING THAT MATTERS MOST, and it disagrees downwards.

    VETO-DN-0265 and VETO-DN-0267 rate insulin and sulfonylureas against
    carbohydrate intake CRITICAL, and action both "STABLE PATTERN — discuss
    with prescriber". Row 29 here rates the same drug class MODERATE and
    actions it MONITOR.

    Same hypoglycaemia hazard. One registry routes it to a prescriber, the
    other asks for a measurement. Reported, not resolved.
    """
    by_id = {r["rule_id"]: r for r in veto}
    for rule_id in ("VETO-DN-0265", "VETO-DN-0267"):
        assert by_id[rule_id]["severity"] == "CRITICAL"
        assert "prescriber" in by_id[rule_id]["action"].lower()
        assert by_id[rule_id]["nutrient_or_food"] == "Carbohydrate intake"

    here = next(r for r in sheet["interactions"]
                if r["drug"] == "Insulin/sulfonylureas")
    assert here["severity"] == "MODERATE"
    assert here["rule_text"] == "MONITOR"
    assert "prescriber" not in here["production_target"].lower()

    reported = o9.severity_disagreements()
    assert len(reported) == 2
    assert {d["veto_rule_id"] for d in reported} == {"VETO-DN-0265",
                                                     "VETO-DN-0267"}
    for disagreement in reported:
        assert disagreement["o9_severity"] != disagreement["veto_severity"]


def test_the_two_severity_scales_do_not_match(sheet, veto):
    """O9 has no HIGH tier, and HIGH is the VETO registry's LARGEST -- 111 of
    its 339 rows, just under a third. An O9 row cannot express what the
    biggest slice of that registry says."""
    from collections import Counter

    o9_scale = set(sheet["severity_scale"])
    tiers = Counter(r["severity"] for r in veto)

    assert o9_scale == {"CRITICAL", "MODERATE", "LOW"}
    assert set(tiers) == {"CRITICAL", "HIGH", "MODERATE", "LOW",
                          "CONTROVERSIAL"}
    assert "HIGH" not in o9_scale

    # The largest tier, and the one O9 cannot express.
    assert tiers.most_common(1)[0] == ("HIGH", 111)
    assert tiers["HIGH"] > tiers["MODERATE"] > tiers["CRITICAL"]
    assert 0.30 < tiers["HIGH"] / len(veto) < 0.34


# --- against the UI contract ---------------------------------------------

def test_eight_medications_the_interface_names_have_no_row(sheet, ):
    ui = _load("step_questions.json")
    named = {option for q in ui["questions"]
             if q["step_number"] == 7 and q["is_choice"]
             for option in q["answer_options"]}
    assert len(named) == 22

    modelled = {r["drug"] for r in sheet["interactions"]}
    unmatched = sorted(n for n in named if n not in modelled)
    # Three of these are the same drug spelled differently; five are not.
    assert set(unmatched) >= {"Antibiotics", "Antiplatelet", "Beta Blockers",
                              "Magnesium", "SNRIs", "Theophylline",
                              "Vitamin E"}


def test_warfarin_is_modelled_and_the_interface_never_names_it(sheet):
    """The gap runs the other way too, and this one carries a CRITICAL
    Vitamin K veto. Step 7's first row is a free-text search bar, so the
    named medications are examples rather than the whole list -- which is
    itself why neither direction can be closed here."""
    modelled = {r["drug"] for r in sheet["interactions"]}
    assert "Warfarin" in modelled

    ui = _load("step_questions.json")
    named = {option for q in ui["questions"]
             if q["step_number"] == 7 and q["is_choice"]
             for option in q["answer_options"]}
    assert "Warfarin" not in named

    search = next(q for q in ui["questions"]
                  if q["step_number"] == 7 and "Search" in q["answer_options_text"])
    assert "Search bar" in search["answer_options_text"]


# --- the shape of the sheet ----------------------------------------------

def test_twenty_rows_each_with_a_severity_and_a_production_target(sheet):
    interactions = sheet["interactions"]
    assert len(interactions) == 20
    for row in interactions:
        assert row["severity"] in {"CRITICAL", "MODERATE", "LOW"}
        assert row["production_target"]
        assert row["mechanism_class"]
    assert len([r for r in interactions if r["severity"] == "CRITICAL"]) == 9


def test_the_registry_reads_back_as_objects():
    rows = o9.interactions()
    assert len(rows) == 20
    metformin = o9.find("Metformin", "Vitamin B12")
    assert metformin.is_absorption_effect
    assert metformin.severity == "CRITICAL"
    assert o9.delta_logit_abs("Metformin", "Vitamin B12") == pytest.approx(
        math.log(0.7), abs=5e-7)

    assert len(o9.interactions_for("PPIs")) == 4
    assert o9.interactions_for("Beta Blockers") == ()
    assert len(o9.critical()) == 9


def test_an_unmodelled_drug_raises_rather_than_returning_nothing():
    with pytest.raises(LookupError, match="no row for"):
        o9.find("Beta Blockers", "Potassium")
