"""The parameter registry, and the gap list it computes.

Source: v39sEng2.xlsx, sheet 'P1 Parameters 134+'. Build step 2 of
'★ Build Guide Python' requires "current parameter/FK registries" to load
before the equations can "resolve parameter FKs deterministically", with the
acceptance test "no missing FK".

The registry's value to this build is not that it holds numbers -- mostly it
does not -- but that it makes the question "which parameters do we actually
have values for?" answerable by query. These tests pin that answer so it
cannot drift silently: if a future registry load resolves a parameter, or a
sheet re-extraction loses one, the count changes and CI says so.
"""
import json
import re
from pathlib import Path

import pytest

DATA_DIR = Path(__file__).parent.parent / "sahacore" / "data"


@pytest.fixture(scope="module")
def params() -> list[dict]:
    return json.loads((DATA_DIR / "parameter_registry_192.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def nutrients() -> list[dict]:
    return json.loads((DATA_DIR / "nutrients_81.json").read_text(encoding="utf-8"))


# --- extraction fidelity ---------------------------------------------------

def test_the_registry_has_192_parameters_numbered_without_gaps(params):
    """The sheet is six blocks sharing one header -- a base registry plus five
    EXTENSION blocks. Reading only the first block, or only the rows whose
    number happens to be stored as a number rather than as text, silently
    loses most of it. Both mistakes are caught here."""
    numbers = [p["param_no"] for p in params]
    assert len(params) == 192
    assert numbers == list(range(1, 193))


def test_every_parameter_has_an_identity(params):
    for p in params:
        assert p["symbol"], f"#{p['param_no']} has no symbol"
        assert p["full_name"], f"#{p['param_no']} has no name"


def test_the_only_duplicated_symbol_is_the_one_the_sheet_supersedes(params):
    """A duplicated symbol would normally make an equation's FK ambiguous.
    The sheet has exactly one, and it is deliberate: kappa_v appears at #168
    and again at #186, the first marked SUPERSEDED and the second carrying
    the production value. Pinned rather than tolerated, so a NEW duplicate
    still fails."""
    symbols = [p["symbol"] for p in params]
    dupes = {s for s in symbols if symbols.count(s) > 1}
    assert dupes == {"kappa_v"}, f"unexpected duplicate symbols: {dupes - {'kappa_v'}}"

    versions = [p for p in params if p["symbol"] == "kappa_v"]
    assert [p["param_no"] for p in versions] == [168, 186]
    assert "SUPERSEDED" in (versions[0]["default_or_range"] or "")
    assert "FIXED_PRODUCTION" in (versions[1]["default_or_range"] or "")


def test_every_layer_named_is_one_the_engine_has(params):
    """Layers A-H plus M (memory) and W (warning). A stray layer letter means
    the extraction picked up a row from somewhere else."""
    known = {"A", "B", "C", "D", "E", "F", "G", "H", "M", "W", None}
    seen = {p["layer"] for p in params}
    assert seen <= known, f"unexpected layers: {seen - known}"


def test_weights_use_the_sheets_own_four_levels(params):
    assert {p["weight"] for p in params} <= {"Critical", "High", "Medium", "Low", None}


# --- the parameters this build already resolves ----------------------------

def test_resolved_by_claims_point_at_registries_that_really_carry_the_value(params, nutrients):
    """`resolved_by` is a claim about this build, not a transcription from the
    sheet, so it is verified rather than trusted: every parameter mapped to a
    `nutrients.<column>` must name a column that exists on all 81 rows."""
    sample = nutrients[0]
    for p in params:
        target = p["resolved_by"]
        if not target or not target.startswith("nutrients."):
            continue
        for column in re.findall(r"nutrients\.(\w+)|/ (\w+)", target):
            name = column[0] or column[1]
            assert name in sample, f"#{p['param_no']} {p['symbol']}: nutrients has no column {name!r}"
            assert all(n.get(name) is not None for n in nutrients), (
                f"#{p['param_no']} {p['symbol']}: nutrients.{name} is not populated on all 81"
            )


def test_the_absorption_kernels_fast_component_is_resolved(params):
    """A1's fast gamma is k1_i / lam1_i, and 'P1 Nutrients 81' supplies both
    as γ_k and λ. This is the parameter FK the C1 validation gate exercises."""
    by_symbol = {p["symbol"]: p for p in params}
    assert by_symbol["k1_i"]["resolved_by"] == "nutrients.gamma_k_shape"
    assert by_symbol["lam1_i"]["resolved_by"] == "nutrients.lambda_per_min"


def test_hepatic_blood_flow_is_resolved_by_formula_not_by_a_table(params):
    """Q_liver is one physiological quantity with a published allometric
    formula -- "CO = 6.5*(BW/70)^0.75 L/min (ICRP Pub 89 2003); Q_H =
    0.260*CO" -- already implemented, so it is not a gap despite having no
    per-nutrient table."""
    q = next(p for p in params if p["symbol"] == "Q_liver")
    assert q["resolved_by"] is not None
    assert "ICRP" in q["resolved_by"]


# --- the gap list ----------------------------------------------------------

def _gaps(params, weight=None):
    return [
        p for p in params
        if p["value_kind"] in ("RANGE", "PER_ENTITY_UNSPECIFIED", "ABSENT")
        and p["resolved_by"] is None
        and (weight is None or p["weight"] == weight)
    ]


def test_the_critical_gap_list_is_exactly_these_ten(params):
    """The engine's open holes at Critical weight: an admissible interval and
    no number, with no entity registry that supplies one.

    Pinned by symbol rather than by count so that a change says WHICH
    parameter moved. Shrinking this list is the measure of progress on the
    data spine; growing it means a registry stopped resolving something.
    See docs/parameter-gaps.md.
    """
    assert {p["symbol"] for p in _gaps(params, "Critical")} == {
        "k2_i",          # A1 slow gamma shape  -- the mixture's second component
        "lam2_i",        # A1 slow gamma rate
        "T50",           # A5 gastric half-emptying time
        "kappa",         # A5 gastric Weibull shape
        "F_base,i",      # A4 baseline bioavailability
        "K_m,i",         # A4 Michaelis constant
        "f_unbound,i",   # B5-B7 unbound fraction
        "lam_rep",       # C repair rate
        "R_min",         # H minimum safe reward
        "epsilon_base",  # H conservative baseline tolerance
    }


def test_the_bi_gamma_kernels_second_component_is_among_the_gaps(params):
    """A1 is a mixture of two gammas. 'P1 Nutrients 81' carries one triple
    (γ_k, γ_θ, λ), so the slow component's shape and rate have a range and no
    per-nutrient value -- which is why bi_gamma_absorption_kernel takes them
    as plain arguments and the registry seed does not supply them."""
    by_symbol = {p["symbol"]: p for p in params}
    for symbol in ("k2_i", "lam2_i"):
        assert by_symbol[symbol]["equations"] and "A1" in by_symbol[symbol]["equations"]
        assert by_symbol[symbol]["value_kind"] == "RANGE"
        assert by_symbol[symbol]["resolved_by"] is None


def test_every_critical_gap_still_carries_its_admissible_range(params):
    """A gap with no range at all would be worse than one with a range: the
    range is what lets the validation battery sweep the parameter and what a
    literature fit would have to land inside."""
    for p in _gaps(params, "Critical"):
        assert p["default_or_range"], f"#{p['param_no']} {p['symbol']} has no range to work within"
        assert p["units"], f"#{p['param_no']} {p['symbol']} has no units"


def test_gaps_at_lower_weights_are_recorded_but_not_asserted_individually(params):
    """The Critical list is pinned by symbol; the rest is pinned by count, so
    a regression in the extraction or a newly resolved parameter is still
    visible without enumerating 63 rows."""
    assert len(_gaps(params, "High")) == 22
    assert len(_gaps(params)) == 55


def test_the_chs_display_weights_are_a_recorded_gap_not_an_oversight(params):
    """w_k^fix -- the twelve fixed cluster weights behind the composite score
    -- is parameter #67, omega_base,k. The registry gives it a range and the
    instruction "set proportional to clinical importance of each cluster";
    no workbook carries the twelve values. It is a product decision rather
    than a measurement, which is why it is tracked here by number."""
    omega = next(p for p in params if p["param_no"] == 67)
    assert omega["symbol"] == "omega_base,k"
    assert omega["layer"] == "D"
    assert omega["value_kind"] == "RANGE"
    assert omega["resolved_by"] is None
    assert "clinical importance" in omega["calibration_method"]


def test_deliberately_unresolved_symbols_are_documented_with_a_reason(params):
    """Four symbols could be mapped to a column we hold, and are not. The
    reasons live beside the map so the omissions read as decisions."""
    from sahacore.data.build_parameter_registry import DELIBERATELY_UNRESOLVED

    known = {p["symbol"] for p in params}
    for symbol, reason in DELIBERATELY_UNRESOLVED.items():
        assert symbol in known, f"{symbol!r} is not a symbol in the registry"
        assert len(reason) > 30, f"{symbol!r} has no real reason recorded"
        entry = next(p for p in params if p["symbol"] == symbol)
        assert entry["resolved_by"] is None
