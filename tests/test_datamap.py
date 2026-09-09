"""The variable dictionary and the onboarding field contract.

Source: v39sEng2.xlsx, sheet 'P1 DataMap' sections A and B,
'01_IMPORT_MANIFEST' order 25.

Two things this sheet gives that nothing else in the build did: a per-variable
statement of whether a quantity is stored or computed, and the input contract
for Build Guide step 3 -- which onboarding field sets which engine variable,
and what happens when the user does not answer.
"""
import json
from pathlib import Path

import pytest

DATA_DIR = Path(__file__).parent.parent / "sahacore" / "data"


@pytest.fixture(scope="module")
def datamap() -> dict:
    return json.loads((DATA_DIR / "datamap.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def variables(datamap) -> list[dict]:
    return datamap["variables"]


@pytest.fixture(scope="module")
def fields(datamap) -> list[dict]:
    return datamap["onboarding_fields"]


# --- extraction fidelity ---------------------------------------------------

def test_the_two_sections_extracted_hold_what_they_hold(variables, fields):
    assert len(variables) == 96
    assert len(fields) == 63


def test_the_banners_overstate_and_both_numbers_are_kept(variables, fields):
    """Section A's banner says "158+ ENGINE VARIABLES" over 96 rows; B's says
    "105 ONBOARDING FIELDS" over 63. Some rows name two variables at once
    ("k₁, λ₁"), which explains part of the gap and not all of it. Recording
    the claim and the count separately is the honest option: picking one
    would either invent rows or contradict the sheet."""
    from sahacore.data.build_datamap import (
        CLAIMED_VARIABLES, CLAIMED_ONBOARDING, ACTUAL_VARIABLES, ACTUAL_ONBOARDING)

    assert "158" in CLAIMED_VARIABLES and ACTUAL_VARIABLES == 96
    assert "105" in CLAIMED_ONBOARDING and ACTUAL_ONBOARDING == 63
    assert len(variables) == ACTUAL_VARIABLES
    assert len(fields) == ACTUAL_ONBOARDING


def test_exactly_one_variable_row_has_no_symbol(variables):
    """r8 describes "Gamma shape parameter", Layer A, equation A1, and leaves
    the symbol cell empty. It is almost certainly `k`. "Almost certainly" is
    why it is not filled in."""
    unnamed = [v for v in variables if not v["variable"]]
    assert len(unnamed) == 1
    assert unnamed[0]["source_row"] == 8
    assert unnamed[0]["full_description"] == "Gamma shape parameter"


# --- stored against computed -----------------------------------------------

def test_the_data_source_column_separates_stored_from_computed(variables):
    """The distinction this build got wrong once, now available for every
    variable: 44 computed, 24 from a parameter table or marked Parameter."""
    sources: dict[str, int] = {}
    for v in variables:
        sources[v["data_source"] or ""] = sources.get(v["data_source"] or "", 0) + 1
    assert sources["Computed"] == 44
    assert sources["Parameter"] + sources["Parameter Table"] == 24


def test_the_absorbed_fraction_is_computed_and_its_bounds_are_parameters(variables):
    """A4/A5 in one reading. F_abs is computed; F_max and F_base are the
    parameters that bound it -- which is why F_base,i being absent from the
    nutrient table is a real gap and F_abs never could be."""
    by_var = {v["variable"]: v for v in variables if v["variable"]}
    assert by_var["F_abs,i,m"]["data_source"] == "Computed"
    assert by_var["F_max,i"]["data_source"].startswith("Parameter")
    assert by_var["F_base,i"]["data_source"].startswith("Parameter")


def test_every_computed_variable_names_the_equation_that_computes_it(variables):
    """A variable marked Computed with no equation would be an assertion
    without a source."""
    for v in variables:
        if v["data_source"] == "Computed":
            assert v["equations"], f"{v['variable']} is computed by nothing"


# --- the onboarding contract for Build Guide step 3 ------------------------

def test_every_onboarding_field_states_what_happens_when_it_is_skipped(fields):
    """The column that stops Layer 0 inventing a default. 'Required',
    'Estimated from BMI', a literal value -- but never blank, because a blank
    is a default chosen silently by whoever writes the code. The builder
    refuses to write if one is missing."""
    for f in fields:
        assert f["default_if_missing"], f["field_name"]


def test_the_required_fields_are_the_ones_with_no_default(fields):
    """Four fields the engine cannot proceed without."""
    required = [f["field_name"] for f in fields if f["default_if_missing"] == "Required"]
    assert len(required) == 4
    assert "Date of birth" in required


def test_every_field_names_the_engine_variable_it_sets(fields):
    """This is the join that makes the sheet an input contract rather than a
    UI description."""
    for f in fields:
        assert f["engine_variable"], f["field_name"]


def test_weight_maps_to_the_compartment_volumes(fields):
    """The mapping logic is transcribed, not interpreted -- and it is the
    same O1.1/O1.2 relation the build already knew V_f and V_s come from,
    which is why they were never on the missing-parameter list."""
    w = next(f for f in fields if f["field_name"] == "Current weight (kg)")
    assert w["engine_variable"] == "weight_kg"
    assert "V_f" in w["mapping_logic"] and "V_s" in w["mapping_logic"]
    assert w["default_if_missing"] == "Required"


def test_the_priority_vocabulary_is_the_sheets_own(fields):
    priorities = {f["priority"] for f in fields if f["priority"]}
    assert priorities <= {"P0", "P0 Critical", "P1", "P2"}


# --- the extractor refuses bad data ----------------------------------------

def test_the_builder_refuses_an_onboarding_field_with_no_stated_default(datamap):
    from sahacore.data.build_datamap import check

    broken = json.loads(json.dumps(datamap))
    broken["onboarding_fields"][0]["default_if_missing"] = None
    with pytest.raises(SystemExit, match="no stated default"):
        check(broken)


def test_the_builder_refuses_a_second_unnamed_variable(datamap):
    from sahacore.data.build_datamap import check

    broken = json.loads(json.dumps(datamap))
    broken["variables"][5]["variable"] = None
    with pytest.raises(SystemExit, match="rows with no variable symbol"):
        check(broken)
