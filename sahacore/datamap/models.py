"""The P1 DataMap as typed models, and an honest count of what it holds.

Source: v39sEng2.xlsx, sheet 'P1 DataMap', sections A and B, via
sahacore/data/datamap.json. The Postgres side is
engine_internal.datamap_variable and .datamap_onboarding_field, created by
sql/019_datamap.sql; this is the same contract in Python.

    from sahacore.datamap import DataMap
    contract = DataMap.load()

WHY MODELS AND NOT JUST THE JSON. The DataMap is the input/output contract:
every engine variable with the layer and equations that own it, and every
onboarding field with the engine variable it sets. It is the thing an API
request or an onboarding payload will eventually be checked against, and a
dict is checked against nothing. `extra="forbid"` and `frozen=True` mean a
column added to the sheet without being added here fails loudly, and nothing
downstream can mutate a row it was handed.

WHAT THESE MODELS DO NOT DO. They do not repair the sheet. Two rows are
malformed at source and both are typed as optional rather than guessed at --
see MALFORMED_AT_SOURCE. One priority value is non-canonical and is kept
verbatim rather than normalised. A model that silently fixed these would make
the defects unfindable, which is the opposite of what a contract is for.
"""
from __future__ import annotations

import json
import re
from enum import Enum
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

DATA_FILE = Path(__file__).parent.parent / "data" / "datamap.json"

# --- the closed sets, measured from the sheet rather than assumed ---------
#
# Only two columns are closed. `layer` is exactly A-H across all 96 variable
# rows, and every atom of the onboarding `target_layer` combinations is one
# of the same eight. Everything else that looks enumerable is not:
# data_source has 18 distinct values over 96 rows, update_frequency 17,
# input_type 24, units 32. Those are free text in the source and are typed as
# free text here -- an enum over them would be this build deciding which
# spellings are canonical, which is the sheet author's decision.


class Layer(str, Enum):
    """The engine's eight layers. A absorption through H the bandit."""
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"
    F = "F"
    G = "G"
    H = "H"


class Priority(str, Enum):
    """The onboarding field's build priority, P0 first.

    Three canonical values, and one row that reads "P0 Critical" instead --
    see OnboardingField.priority_tier.
    """
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"


# Rows the workbook itself leaves incomplete. Typed optional here and pinned
# by tests/test_datamap_models.py, so the count cannot drift and neither can
# the decision to leave them alone.
MALFORMED_AT_SOURCE = {
    # The variable NAME cell is empty. Everything else is present: layer A,
    # equation A1, "Gamma shape parameter", dimensionless, range 1-5,
    # "Per-nutrient lookup (81 nutrients)". The 81-nutrient registry carries
    # `gamma_k_shape`, so the intended symbol is not a mystery -- but the
    # cell is blank, and writing a name into a contract row because the
    # surrounding cells imply one is inventing the contract.
    8: "variable name is blank in the sheet",
    # The step NUMBER cell is empty on the Baseline screen's biological-sex
    # field. The rows around it are step 1.
    108: "step number is blank in the sheet",
}

# The three counts that disagree, all measured rather than quoted.
CONTRACT_ROW_COUNT = 229       # the signed contract, M1
SHEET_TITLE_ROW_COUNT = 227    # the sheet's own title: "227 input-output routings"

# Section -> (banner claim, rows actually present, whether this build reads it).
#
# Counted from the workbook by taking any row with a non-empty cell in the
# section's column span -- not by counting the first column, which undercounts
# by one in section A (source row 8 has no variable name) and misses the
# continuation rows in D and E.
#
# THE BANNERS AND THE ROWS AGREE ONCE OUT OF FOUR. Section C claims 24 and
# holds 24. Section A claims "158+" and holds 96; B claims 105 and holds 63;
# D claims 127 and holds 13, because D is a GROUPED summary -- its last row
# reads "L06-L20", one row standing for fifteen actions -- rather than a row
# per action. The real 127 are in engine_internal.action_space, loaded from
# 'Action_Space' itself.
SECTIONS = {
    "A engine variables": ("158+", 96, True),
    "B onboarding fields": ("105", 63, True),
    "C data source categories": ("24", 24, False),
    "D registered actions": ("127", 13, False),
    "E layer interconnections": (None, 15, False),
}

_EQUATION_SEPARATOR = re.compile(r"[,;/]")


class EngineVariable(BaseModel):
    """Section A. One engine variable, and where its value comes from."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_row: int
    # Optional only because of source row 8. Every other row names one.
    variable: str | None = None
    layer: Layer
    equations: str
    full_description: str
    physiological_meaning: str
    units: str
    typical_range: str
    # THE COLUMN THAT EARNS THE IMPORT. It separates 'Parameter' and
    # 'Parameter Table' from 'Computed', 'Input', 'Diet Logging' and
    # 'Onboarding'. This build once reported CL as a missing parameter when
    # it is computed; this column is where that distinction is written down.
    data_source: str
    specific_source: str
    update_frequency: str

    @property
    def equation_ids(self) -> tuple[str, ...]:
        """'A1,A2' -> ('A1', 'A2'). Splitting, not interpreting."""
        return tuple(
            part.strip() for part in _EQUATION_SEPARATOR.split(self.equations)
            if part.strip())

    @property
    def is_computed(self) -> bool:
        """True when the engine derives it rather than reading it.

        Deliberately narrow: it answers only for the exact value 'Computed'.
        'Computed + Lab' and 'Computed' are different rows in the sheet and
        collapsing them here would undo the distinction the column exists to
        make.
        """
        return self.data_source == "Computed"


class OnboardingField(BaseModel):
    """Section B. One onboarding screen field and the engine variable it
    sets, with the layers and equations that consume it."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_row: int
    # Optional only because of source row 108.
    step: int | None = None
    screen: str
    field_name: str
    input_type: str
    engine_variable: str
    target_layer: str
    equations: str
    mapping_logic: str
    default_if_missing: str
    # Kept as written. One row reads "P0 Critical"; see priority_tier.
    priority: str

    @property
    def target_layers(self) -> frozenset[Layer]:
        """'B,C,E,F' -> {B, C, E, F}. Every atom in the sheet is A-H, so this
        splits and maps without needing a fallback."""
        return frozenset(
            Layer(part.strip())
            for part in _EQUATION_SEPARATOR.split(self.target_layer)
            if part.strip())

    @property
    def equation_ids(self) -> tuple[str, ...]:
        return tuple(
            part.strip() for part in _EQUATION_SEPARATOR.split(self.equations)
            if part.strip())

    @property
    def priority_tier(self) -> Priority | None:
        """The canonical priority, or None when the cell is not one.

        Returns None for source row 164, which reads "P0 Critical". NOT
        mapped to P0: the sheet has a three-value scale and this is a fourth
        string on it, so either it is P0 written emphatically or it is a
        tier above P0, and only the sheet's author knows which. Returning
        None keeps the question visible; returning P0 would answer it.
        """
        try:
            return Priority(self.priority)
        except ValueError:
            return None


class DataMap(BaseModel):
    """Sections A and B together -- the part of the DataMap this build
    reads. Sections C, D and E are not extracted; see SECTIONS."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    variables: list[EngineVariable]
    onboarding_fields: list[OnboardingField] = Field(
        default_factory=list, alias="onboarding_fields")

    @classmethod
    def load(cls) -> DataMap:
        """Validate the committed datamap.json through these models.

        Cached: the file does not change at runtime, and every caller wants
        the same immutable contract.
        """
        return _load()

    # --- what the contract asks for, against what is here -----------------

    @property
    def row_count(self) -> int:
        return len(self.variables) + len(self.onboarding_fields)

    def variables_for_layer(self, layer: Layer) -> tuple[EngineVariable, ...]:
        return tuple(v for v in self.variables if v.layer is layer)

    def fields_for_step(self, step: int) -> tuple[OnboardingField, ...]:
        return tuple(f for f in self.onboarding_fields if f.step == step)

    def field_for_engine_variable(self, name: str) -> OnboardingField | None:
        for field in self.onboarding_fields:
            if field.engine_variable == name:
                return field
        return None


@lru_cache(maxsize=1)
def _load() -> DataMap:
    return DataMap.model_validate(
        json.loads(DATA_FILE.read_text(encoding="utf-8")))


def shortfall() -> dict[str, int | str]:
    """The gap between the contract's 229 rows and what exists, itemised.

    Written as a function rather than a paragraph so the numbers are
    queryable and a test can fail when one of them moves. See
    docs/parameter-gaps.md for the prose version.
    """
    extracted = sum(rows for _, rows, taken in SECTIONS.values() if taken)
    present = sum(rows for _, rows, _ in SECTIONS.values())
    return {
        "contract_rows": CONTRACT_ROW_COUNT,
        "sheet_title_rows": SHEET_TITLE_ROW_COUNT,
        "rows_present_in_all_five_sections": present,
        "rows_extracted_sections_a_and_b": extracted,
        "contract_minus_sheet_title": CONTRACT_ROW_COUNT - SHEET_TITLE_ROW_COUNT,
        "sheet_title_minus_rows_present": SHEET_TITLE_ROW_COUNT - present,
        "rows_present_minus_extracted": present - extracted,
        "why_not_extracted": (
            "C is integration metadata with no consumer; D restates "
            "engine_internal.action_space, loaded from 'Action_Space' itself; "
            "E restates the inputs and outputs of '★ Equation Backbone'. "
            "Importing either would create two records that can disagree."
        ),
    }
