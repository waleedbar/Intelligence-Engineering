"""The equation specifications, and the corrections already applied to them.

Source: v39sEng2.xlsx, sheet 'P1 Core Equations',
'01_IMPORT_MANIFEST' order 23.

The 19 corrections are the reason this sheet matters more than its formulas:
each records a wrong version of an equation that someone has already written
once. The archived Layer A/B/C code in archive/ was written against these,
and will have to be checked against them again before it is revived.
"""
import json
from pathlib import Path

import pytest

DATA_DIR = Path(__file__).parent.parent / "sahacore" / "data"


@pytest.fixture(scope="module")
def equations() -> list[dict]:
    return json.loads((DATA_DIR / "core_equations.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def by_id(equations) -> dict[str, dict]:
    return {e["eq_id"]: e for e in equations}


# --- extraction fidelity ---------------------------------------------------

def test_all_51_equations_across_eight_layers(equations):
    assert len(equations) == 51
    layers: dict[str, int] = {}
    for e in equations:
        layers[e["layer"]] = layers.get(e["layer"], 0) + 1
    assert layers == {"A": 8, "B": 6, "C": 7, "D": 4, "E": 9, "F": 4, "G": 5, "H": 8}


def test_the_layer_banners_are_not_read_as_equations(equations):
    """"LAYER A: NUTRIENT ABSORPTION (7 equations)" sits in the id column
    with nothing beside it. Requiring both an id and a layer skips it."""
    assert not any(e["eq_id"].upper().startswith("LAYER") for e in equations)


def test_every_equation_carries_a_formula(equations):
    for e in equations:
        assert e["formula"], e["eq_id"]


def test_eq_id_is_unique_here_unlike_the_other_equation_sheets(equations):
    """Worth asserting rather than assuming: 'PARAM · Eq Param FK' repeats
    A-001, and '★ Equation Backbone' repeats C2. This sheet does not, so
    eq_id can be the primary key."""
    ids = [e["eq_id"] for e in equations]
    assert len(set(ids)) == len(ids)


# --- the relationship with the backbone ------------------------------------

def test_the_two_equation_sheets_are_complementary_not_duplicates(equations):
    """22 ids in both, 29 only here, 35 only in the backbone. Loading one and
    calling the other redundant would lose whichever set was dropped."""
    backbone = json.loads(
        (DATA_DIR / "equation_backbone.json").read_text(encoding="utf-8"))
    here = {e["eq_id"] for e in equations}
    there = {b["eq_id"] for b in backbone}
    assert len(here & there) == 22
    assert len(here - there) == 29
    assert len(there - here) == 35
    # The detail equations are here; the named aggregates are there.
    assert {"D1", "H1", "G1", "E4"} <= here - there
    assert {"ONB", "DSC", "M1", "QATP"} <= there - here


def test_a_shared_id_is_in_the_same_layer_in_both_sheets(equations):
    """The check that is meaningful between them. Formula equality is not:
    the backbone writes A1 as one line and this sheet writes it with the
    log-gamma evaluation form as well. Same mathematics, different detail."""
    backbone = json.loads(
        (DATA_DIR / "equation_backbone.json").read_text(encoding="utf-8"))
    bb: dict[str, list[str]] = {}
    for b in backbone:
        bb.setdefault(b["eq_id"], []).append(b["layer"])
    for e in equations:
        layers = bb.get(e["eq_id"])
        if layers:
            assert any(L.startswith(e["layer"]) for L in layers), e["eq_id"]


# --- the corrections -------------------------------------------------------

def test_nineteen_equations_carry_a_recorded_correction(equations):
    assert sum(1 for e in equations if e["correction_applied"]) == 19


def test_the_corrections_that_change_an_implementation_are_intact(by_id):
    """Four that would each produce a wrong number if missed, quoted so a
    reworded cell is visible rather than silently weaker."""
    assert "double-counted binding" in by_id["B6"]["correction_applied"]
    assert "p = 1 enforced" in by_id["C2"]["correction_applied"]
    assert "competitive MM" in by_id["C6"]["correction_applied"]
    assert "UNITS FIX" in by_id["C4"]["correction_applied"]


def test_the_builder_refuses_a_vanished_correction(equations):
    """A correction disappearing is engineering history being lost, and is
    exactly as notable as one appearing."""
    from sahacore.data.build_core_equations import check

    rows = [dict(e) for e in equations]
    next(r for r in rows if r["eq_id"] == "B6")["correction_applied"] = None
    with pytest.raises(SystemExit, match="carry a correction"):
        check(rows)


def test_the_builder_refuses_a_layer_disagreement_with_the_backbone(equations):
    from sahacore.data.build_core_equations import check

    rows = [dict(e) for e in equations]
    next(r for r in rows if r["eq_id"] == "A1")["layer"] = "H"
    with pytest.raises(SystemExit, match="Equation Backbone"):
        check(rows)
