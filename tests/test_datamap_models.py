"""The P1 DataMap as typed models, and the counts that do not agree.

Contract M1 asks for the DataMap "implemented as Pydantic models and Postgres
DDL". These tests check the models against the committed extract and against
the database, and pin the three row counts that disagree so none of them can
drift silently.

Nothing here needs a database except the two that say so.
"""
import json
import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from sahacore.datamap import (
    CONTRACT_ROW_COUNT,
    DataMap,
    EngineVariable,
    Layer,
    MALFORMED_AT_SOURCE,
    OnboardingField,
    Priority,
    SECTIONS,
    SHEET_TITLE_ROW_COUNT,
    shortfall,
)

DATA_FILE = Path(__file__).parent.parent / "sahacore" / "data" / "datamap.json"


@pytest.fixture(scope="module")
def contract() -> DataMap:
    return DataMap.load()


# === the models validate the real extract =================================

def test_every_committed_row_validates(contract):
    """THE TEST THAT MAKES THE MODELS REAL. A model that has never been run
    against the data it describes is a diagram."""
    raw = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    assert len(contract.variables) == len(raw["variables"]) == 96
    assert len(contract.onboarding_fields) == len(raw["onboarding_fields"]) == 63
    assert contract.row_count == 159


def test_a_column_added_to_the_sheet_would_fail_rather_than_vanish(contract):
    """extra="forbid". The failure mode this build has hit three times is a
    sheet growing a column and an extractor silently dropping it; a model
    that ignored unknown keys would repeat it one layer higher."""
    row = dict(contract.variables[0])
    row["newly_added_column"] = "something"
    with pytest.raises(ValidationError):
        EngineVariable.model_validate(row)


def test_the_rows_are_immutable(contract):
    """frozen=True. A contract row handed to a caller is a fact, not a
    scratch buffer."""
    with pytest.raises(ValidationError):
        contract.variables[0].layer = Layer.H


def test_every_variable_belongs_to_one_of_the_eight_layers(contract):
    assert {v.layer for v in contract.variables} == set(Layer)


def test_every_onboarding_field_targets_only_real_layers(contract):
    """`target_layer` is free text like "B,C,E,F" in the sheet. Every atom
    across all 63 rows is A-H, which is what lets target_layers parse
    without a fallback."""
    for field in contract.onboarding_fields:
        assert field.target_layers
        assert field.target_layers <= set(Layer), field.field_name


# === the two rows the workbook leaves incomplete ==========================

def test_exactly_two_rows_are_malformed_at_source(contract):
    """Pinned by source row so a third cannot appear unnoticed, and so that
    repairing either upstream turns this red rather than passing quietly."""
    nameless = [v.source_row for v in contract.variables if v.variable is None]
    stepless = [f.source_row for f in contract.onboarding_fields if f.step is None]

    assert nameless == [8]
    assert stepless == [108]
    assert set(nameless) | set(stepless) == set(MALFORMED_AT_SOURCE)


def test_the_nameless_variable_kept_everything_else(contract):
    """Source row 8 is missing only its name. It is NOT reconstructed from
    the surrounding cells, even though they point plainly at the 81-nutrient
    registry's gamma_k_shape -- writing a name into a contract row because
    its neighbours imply one is inventing the contract."""
    row = next(v for v in contract.variables if v.source_row == 8)

    assert row.variable is None
    assert row.layer is Layer.A
    assert row.equation_ids == ("A1",)
    assert row.full_description == "Gamma shape parameter"
    assert row.units == "dimensionless"
    assert "81 nutrients" in row.specific_source


# === the priority scale has a fourth value ================================

def test_one_priority_is_not_on_the_declared_scale(contract):
    """Source row 164 reads "P0 Critical" where the scale is P0/P1/P2.

    priority_tier returns None rather than P0. Either it is P0 written
    emphatically or a tier above P0, and only the sheet's author knows
    which -- returning P0 would answer a question this build cannot answer.
    """
    odd = [f for f in contract.onboarding_fields if f.priority_tier is None]
    assert [f.source_row for f in odd] == [164]
    assert odd[0].priority == "P0 Critical"
    assert odd[0].screen == "Lab Results"

    # And the raw value is preserved, not normalised on the way in.
    assert odd[0].priority not in {p.value for p in Priority}

    for field in contract.onboarding_fields:
        if field.source_row != 164:
            assert field.priority_tier is not None, field.source_row


# === the counts that do not agree =========================================

def test_the_three_row_counts_disagree_and_all_three_are_recorded():
    """M1 names 229. The sheet's own title names 227. 211 rows are present
    across all five sections, and this build reads the 159 in A and B.

    Recorded as numbers rather than prose so a change to any of them fails
    here. See docs/parameter-gaps.md for what each gap is.
    """
    gap = shortfall()

    assert gap["contract_rows"] == CONTRACT_ROW_COUNT == 229
    assert gap["sheet_title_rows"] == SHEET_TITLE_ROW_COUNT == 227
    assert gap["rows_present_in_all_five_sections"] == 211
    assert gap["rows_extracted_sections_a_and_b"] == 159

    assert gap["contract_minus_sheet_title"] == 2
    assert gap["sheet_title_minus_rows_present"] == 16
    assert gap["rows_present_minus_extracted"] == 52


def test_the_section_table_adds_up(contract):
    extracted = sum(rows for _, rows, taken in SECTIONS.values() if taken)
    assert extracted == contract.row_count == 159
    assert sum(rows for _, rows, _ in SECTIONS.values()) == 211


def test_only_one_section_banner_matches_its_own_row_count():
    """Section C claims 24 and holds 24. A claims "158+" over 96, B claims
    105 over 63, and D claims 127 over 13 -- D because it is a grouped
    summary whose last row reads "L06-L20", one row for fifteen actions."""
    matching = [
        name for name, (banner, rows, _) in SECTIONS.items()
        if banner is not None and banner.isdigit() and int(banner) == rows
    ]
    assert matching == ["C data source categories"]


# === the lookups the contract exists to answer ============================

def test_a_field_resolves_to_the_engine_variable_it_sets(contract):
    field = contract.field_for_engine_variable("diet_type")
    assert field is not None
    assert field.screen == "Diet"
    assert field.step == 3
    # The finding recorded earlier: the pattern adjusts weights and
    # bioavailability rather than supplying a mean.
    assert "F_bio" in field.mapping_logic


def test_the_twelve_onboarding_steps_are_all_present(contract):
    steps = {f.step for f in contract.onboarding_fields if f.step is not None}
    assert steps == set(range(1, 13))


def test_layer_lookup_partitions_the_variables(contract):
    counted = sum(len(contract.variables_for_layer(layer)) for layer in Layer)
    assert counted == len(contract.variables)


# === the Python side agrees with the Postgres side ========================

needs_database = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"),
    reason="DATABASE_URL is not set; this compares against the loaded tables")


@needs_database
def test_the_models_and_the_ddl_hold_the_same_rows(ledger_db, contract):
    """M1 asks for Pydantic models AND Postgres DDL. Two representations of
    one contract are worth having only if they cannot drift."""
    with ledger_db.cursor() as cur:
        cur.execute("SELECT count(*) AS n FROM engine_internal.datamap_variable")
        variables = cur.fetchone()["n"]
        cur.execute(
            "SELECT count(*) AS n FROM engine_internal.datamap_onboarding_field")
        fields = cur.fetchone()["n"]

    assert variables == len(contract.variables)
    assert fields == len(contract.onboarding_fields)


@needs_database
def test_every_modelled_variable_is_in_the_table_under_the_same_row(
        ledger_db, contract):
    """Matched on source_row, which is the one identifier both sides carry
    and the only one row 8 has."""
    with ledger_db.cursor() as cur:
        cur.execute("SELECT source_row FROM engine_internal.datamap_variable")
        stored = {r["source_row"] for r in cur.fetchall()}

    assert {v.source_row for v in contract.variables} == stored
