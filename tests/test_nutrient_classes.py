"""Kinetic classes: what shape of model each nutrient may be given.

Source: v39sEng2.xlsx, sheet '★ Nutrient Class Registry',
'01_IMPORT_MANIFEST' order 41.

These tests are about a constraint, not a lookup. The sheet's 'Modelling
consequence' column says what Layer A and Layer B are allowed to do with a
nutrient, and two of the six classes say the obvious model is the wrong one.
Loading it before those layers exist is the point.
"""
import json
from pathlib import Path

import pytest

DATA_DIR = Path(__file__).parent.parent / "sahacore" / "data"


@pytest.fixture(scope="module")
def data() -> dict:
    return json.loads((DATA_DIR / "nutrient_classes.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def by_class(data) -> dict[str, dict]:
    return {c["class_code"]: c for c in data["classes"]}


# --- extraction fidelity ---------------------------------------------------

def test_six_classes_a_through_f(data):
    assert [c["class_code"] for c in data["classes"]] == list("ABCDEF")


def test_all_81_nutrients_are_classified(data):
    assert len(data["nutrients"]) == 81
    assert sorted(n["num"] for n in data["nutrients"]) == list(range(1, 82))


def test_the_class_counts_sum_to_81(data):
    counts: dict[str, int] = {}
    for n in data["nutrients"]:
        counts[n["class_code"]] = counts.get(n["class_code"], 0) + 1
    assert counts == {"A": 17, "B": 7, "C": 43, "D": 4, "E": 10}
    assert sum(counts.values()) == 81


def test_class_f_holds_no_nutrients_and_that_is_correct(data, by_class):
    """F is 'Behavioural exposure', and the sheet scopes it explicitly to the
    24 LIFESTYLE states -- indices 187-210 of the state vector -- not to the
    81 nutrient pools. An empty class here is the sheet being read correctly,
    not a dropped row."""
    assert not [n for n in data["nutrients"] if n["class_code"] == "F"]
    assert "LIFESTYLE" in by_class["F"]["modelling_consequence"].upper()


def test_the_namespace_is_shared_with_the_nutrient_registry(data):
    """Both sheets must mean the same 81 nutrients. The builder raises on a
    mismatch; asserted here so it fails in CI without re-running it."""
    registry = json.loads((DATA_DIR / "nutrients_81.json").read_text(encoding="utf-8"))
    by_num = {r["num"]: r["id"] for r in registry}
    for n in data["nutrients"]:
        assert by_num[n["num"]] == n["nutrient_code"]


# --- the constraints the classes carry -------------------------------------

def test_class_b_forbids_treating_serum_as_an_intake_readout(by_class):
    """The constraint most likely to be violated by a reasonable
    implementation. Seven nutrients are class B -- calcium, magnesium,
    sodium, potassium, chloride, phosphorus and water -- and a
    two-compartment plasma model would have serum calcium track calcium
    intake, which the sheet says does not happen in a healthy person."""
    consequence = by_class["B"]["modelling_consequence"]
    assert "Intake ≠ serum" in consequence
    assert "NOT" in consequence


def test_class_d_is_not_a_plasma_concentration(by_class):
    assert "Not a plasma concentration" in by_class["D"]["modelling_consequence"]


def test_the_buffered_nutrients_are_the_ones_expected(data):
    """Named, so a reclassification is visible rather than a count change."""
    b = {n["nutrient_code"] for n in data["nutrients"] if n["class_code"] == "B"}
    assert b == {"water_l", "calcium_mg", "phosphorus_mg", "magnesium_mg",
                 "sodium_mg", "potassium_mg", "chloride_mg"}


def test_every_nutrient_records_what_may_anchor_it(data):
    """The observation anchor is a safety column: several entries say what
    must NOT be used, and a blank one would read as 'anything goes'."""
    for n in data["nutrients"]:
        assert n["observation_anchor"], n["nutrient_code"]


def test_the_anchors_that_warn_against_a_measurement_are_kept_verbatim(data):
    """Reducing these to a boolean would lose the only part that matters."""
    anchors = {n["nutrient_code"]: n["observation_anchor"] for n in data["nutrients"]}
    assert "NOT serum Ca" in anchors["calcium_mg"]
    assert "INSENSITIVE" in anchors["magnesium_mg"]
    assert "NOT a dietary readout" in anchors["cholesterol_mg"]


def test_endogenous_dominance_is_flagged_where_synthesis_outweighs_intake(data):
    """16 nutrients where the body makes more than the diet supplies -- the
    non-essential amino acids, taurine, carnitine, creatine, glutathione and
    dietary cholesterol. A dose moves these states far less than its size
    suggests."""
    endo = {n["nutrient_code"] for n in data["nutrients"] if n["endogenous_dominant"]}
    assert len(endo) == 16
    assert {"aa_alanine_mg", "aa_glycine_mg", "taurine_g", "creatine_g",
            "glutathione_g", "cholesterol_mg"} <= endo
    assert "aa_leucine_mg" not in endo          # essential; intake-driven


def test_nitrate_is_class_a_with_the_anchor_the_workbook_added(data):
    """Nutrient #81 was added last and its class assignment is what makes it
    modellable at all."""
    n = next(x for x in data["nutrients"] if x["num"] == 81)
    assert n["nutrient_code"] == "nitrate_mg"
    assert n["class_code"] == "A"
    assert "nitrate" in n["observation_anchor"].lower()


# --- the extractor refuses bad data ----------------------------------------

def test_the_builder_refuses_a_class_the_sheet_does_not_define(data):
    from sahacore.data.build_nutrient_classes import check

    broken = json.loads(json.dumps(data))
    broken["nutrients"][0]["class_code"] = "Z"
    with pytest.raises(SystemExit, match="classes the sheet does not define"):
        check(broken)


def test_the_builder_refuses_a_namespace_disagreement(data):
    """If this sheet and 'P1 Nutrients 81' disagreed about what #34 is, a
    partial join would hide it. The build stops instead."""
    from sahacore.data.build_nutrient_classes import check

    broken = json.loads(json.dumps(data))
    broken["nutrients"][33]["nutrient_code"] = "not_a_real_nutrient"
    with pytest.raises(SystemExit, match="P1 Nutrients 81"):
        check(broken)
