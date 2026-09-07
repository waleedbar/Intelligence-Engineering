"""Tests for sahacore/engine/qssa.py (QSSA molecular layer, ATP branch).

Source: v39sEng2.xlsx, sheet 'P1 QSSA ATP-GSH-NAD', 'QSSA-ATP INTERNAL'.
"""
import json
from pathlib import Path

import pytest

from sahacore.engine.qssa import (
    activity_factor,
    atp_supply_fraction,
    cofactor_support_factor,
    j_atp_raw,
    mitochondrial_flux_sum,
)

DATA_DIR = Path(__file__).parent.parent / "sahacore" / "data"


@pytest.fixture(scope="module")
def complexes() -> list[dict]:
    return json.loads((DATA_DIR / "qssa_atp_complexes_5.json").read_text(encoding="utf-8"))


# --- mitochondrial_flux_sum ------------------------------------------------

def test_flux_sum_matches_closed_form_for_a_single_complex():
    complexes = [{"complex_id": "I", "km_um": 150.0, "vmax_relative": 1.0}]
    s = {"I": 300.0}
    expected = 1.0 * 300.0 / (150.0 + 300.0)
    assert mitochondrial_flux_sum(s, complexes) == pytest.approx(expected)


def test_flux_sum_is_the_sum_across_all_5_real_complexes(complexes):
    s = {c["complex_id"]: 100.0 for c in complexes}
    expected = sum(c["vmax_relative"] * 100.0 / (c["km_um"] + 100.0) for c in complexes)
    assert mitochondrial_flux_sum(s, complexes) == pytest.approx(expected)


def test_flux_sum_is_zero_when_all_substrates_are_zero(complexes):
    s = {c["complex_id"]: 0.0 for c in complexes}
    assert mitochondrial_flux_sum(s, complexes) == 0.0


def test_flux_sum_saturates_toward_sum_of_vmax_at_very_high_substrate(complexes):
    s = {c["complex_id"]: 1e9 for c in complexes}
    result = mitochondrial_flux_sum(s, complexes)
    total_vmax = sum(c["vmax_relative"] for c in complexes)
    assert result == pytest.approx(total_vmax, rel=1e-6)


# --- cofactor_support_factor -----------------------------------------------

def test_cofactor_factor_is_the_minimum_of_the_three_saturation_terms():
    coq10, km_coq10 = 1.0, 1.0   # term = 0.5
    mg, km_mg = 9.0, 1.0         # term = 0.9
    fe, km_fe = 0.25, 1.0        # term = 0.2 (the binding constraint)
    result = cofactor_support_factor(coq10, km_coq10, mg, km_mg, fe, km_fe)
    assert result == pytest.approx(0.2)


def test_cofactor_factor_is_bounded_0_1():
    result = cofactor_support_factor(coq10=1000.0, km_coq10=1.0, mg=1000.0, km_mg=1.0, fe=1000.0, km_fe=1.0)
    assert 0.0 <= result <= 1.0


def test_cofactor_factor_is_zero_when_any_cofactor_is_absent():
    result = cofactor_support_factor(coq10=0.0, km_coq10=1.0, mg=5.0, km_mg=1.0, fe=5.0, km_fe=1.0)
    assert result == 0.0


# --- activity_factor / j_atp_raw / atp_supply_fraction ---------------------

def test_activity_factor_is_the_plain_ratio():
    assert activity_factor(mr_adj=2000.0, bmr=1600.0) == pytest.approx(1.25)


def test_j_atp_raw_is_the_product_of_its_three_factors():
    assert j_atp_raw(flux_sum=5.0, f_cofactor=0.8, f_activity=1.1) == pytest.approx(5.0 * 0.8 * 1.1)


@pytest.mark.parametrize("raw,ref,expected", [(5.0, 10.0, 0.5), (20.0, 10.0, 1.0), (0.0, 10.0, 0.0)])
def test_atp_supply_fraction_matches_expected_clipped_ratio(raw, ref, expected):
    assert atp_supply_fraction(raw, ref) == pytest.approx(expected)


def test_atp_supply_fraction_is_always_bounded_0_1():
    for raw, ref in [(-5.0, 10.0), (0.0, 10.0), (10.0, 10.0), (1000.0, 10.0)]:
        result = atp_supply_fraction(raw, ref)
        assert 0.0 <= result <= 1.0


def test_full_atp_pipeline_with_real_complex_data_produces_a_bounded_fraction(complexes):
    """End-to-end composition using the real 5-complex registry -- not a
    golden-value check (no worked example was found in the source for
    this branch, unlike A1's Live Verification Lab), but confirms the
    pieces compose to a valid [0,1] fraction for a plausible physiological
    input set."""
    substrate_concentrations = {c["complex_id"]: 200.0 for c in complexes}
    flux = mitochondrial_flux_sum(substrate_concentrations, complexes)
    f_cofactor = cofactor_support_factor(coq10=1.0, km_coq10=0.5, mg=1.0, km_mg=0.5, fe=1.0, km_fe=0.5)
    f_activity = activity_factor(mr_adj=1800.0, bmr=1600.0)
    raw = j_atp_raw(flux, f_cofactor, f_activity)
    fraction = atp_supply_fraction(raw, j_atp_ref=raw)  # ref=raw is a trivial sanity anchor
    assert fraction == pytest.approx(1.0)
    assert 0.0 <= atp_supply_fraction(raw, j_atp_ref=raw * 2.0) <= 1.0
