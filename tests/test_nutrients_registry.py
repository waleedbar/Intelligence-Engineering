"""Pure-data tests for sahacore/data/nutrients_81.json.

These lock in invariants that were verified by hand against the raw
'P1 Nutrients 81' sheet, so a future edit to the JSON (or a bad re-export)
fails loudly instead of silently corrupting the Layer 0 registry.
No database is needed to run these.
"""
import json
from pathlib import Path

import pytest

DATA_FILE = Path(__file__).parent.parent / "sahacore" / "data" / "nutrients_81.json"

KNOWN_CATEGORIES = {
    "Amino Acid", "Bioactive", "Electrolyte", "Endogenous+Diet", "Fat",
    "Fatty Acid", "Hydration", "Lipid", "Macro", "Mineral", "Other",
    "Vitamin", "Vitamin-like",
}
KNOWN_UNITS = {"IU", "L", "g", "kcal", "mg", "µg", "µg DFE", "µg RAE"}
KNOWN_STATE_SEMANTICS = {"BODY_POOL_PROXY", "EXPOSURE_EQUIVALENT"}


@pytest.fixture(scope="module")
def registry() -> list[dict]:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def test_has_exactly_81_entries(registry):
    assert len(registry) == 81


def test_ids_are_unique(registry):
    ids = [r["id"] for r in registry]
    assert len(ids) == len(set(ids))


def test_num_is_contiguous_1_to_81(registry):
    assert sorted(r["num"] for r in registry) == list(range(1, 82))


def test_categories_are_known(registry):
    unknown = {r["category"] for r in registry} - KNOWN_CATEGORIES
    assert not unknown, f"unexpected categories: {unknown}"


def test_units_are_known(registry):
    unknown = {r["unit"] for r in registry} - KNOWN_UNITS
    assert not unknown, f"unexpected units: {unknown}"


def test_state_semantics_are_known(registry):
    unknown = {r["state_semantics"] for r in registry} - KNOWN_STATE_SEMANTICS
    assert not unknown, f"unexpected state_semantics: {unknown}"


def test_kappa_fast_and_slow_partition_sums_to_one(registry):
    for r in registry:
        total = r["kappa_fast"] + r["kappa_slow"]
        assert abs(total - 1.0) < 1e-9, f"{r['id']}: kappa_fast+kappa_slow={total}"


def test_half_life_slow_d_defined_iff_slow_pool_exists(registry):
    """half_life_slow_d is the registry's '—' placeholder exactly when
    kappa_slow == 0 (no slow pool) -- confirmed for water_l, alcohol_g,
    sodium_mg, potassium_mg, chloride_mg."""
    for r in registry:
        is_placeholder = r["half_life_slow_d"] == "—"
        assert is_placeholder == (r["kappa_slow"] == 0), (
            f"{r['id']}: kappa_slow={r['kappa_slow']} but "
            f"half_life_slow_d={r['half_life_slow_d']!r}"
        )


def test_core_kinetic_params_are_positive_where_numeric(registry):
    positive_fields = [
        "gamma_k_shape", "gamma_theta_min", "lambda_per_min",
        "half_life_fast_d", "v_f_dl", "f_max",
    ]
    for r in registry:
        for field in positive_fields:
            assert r[field] > 0, f"{r['id']}.{field} = {r[field]}"


def test_half_life_slow_d_positive_when_present(registry):
    for r in registry:
        value = r["half_life_slow_d"]
        if value != "—":
            assert value > 0, f"{r['id']}.half_life_slow_d = {value}"
