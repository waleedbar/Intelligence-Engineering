"""Tests for sahacore/engine/pharmacokinetics.py (Layer B, equations B1-B6).

Source: v39sEng2.xlsx, sheet 'P1 Core Equations', rows B1-B6 (Q/CL
notation -- see the module docstring for why this version was chosen over
the competing k_fs and k_fs/k_cl/k_sf formulations found elsewhere).
"""
import json
import math
from pathlib import Path

import pytest

from sahacore.engine.pharmacokinetics import (
    GFR_DEFAULT_DL_PER_MIN,
    cardiac_output,
    elimination_rate_constant,
    fast_compartment_derivative,
    fast_compartment_volume,
    hepatic_blood_flow,
    hepatic_clearance,
    hepatic_extraction_ratio,
    renal_clearance,
    slow_compartment_derivative,
    slow_compartment_volume,
    total_clearance,
    unbound_fraction,
)

DATA_DIR = Path(__file__).parent.parent / "sahacore" / "data"


@pytest.fixture(scope="module")
def nutrients() -> list[dict]:
    return json.loads((DATA_DIR / "nutrients_81.json").read_text(encoding="utf-8"))


# --- B1: elimination rate constant ------------------------------------------

def test_elimination_rate_constant_matches_closed_form():
    t_half = 10.0
    assert elimination_rate_constant(t_half) == pytest.approx(math.log(2) / t_half)


def test_elimination_rate_constant_is_positive_for_every_real_nutrient_half_life(nutrients):
    for nut in nutrients:
        k_el = elimination_rate_constant(nut["half_life_fast_d"])
        assert k_el > 0.0, nut["id"]
        if nut["half_life_slow_d"] != "—":
            k_el_slow = elimination_rate_constant(nut["half_life_slow_d"])
            assert k_el_slow > 0.0, nut["id"]


def test_elimination_rate_constant_is_inversely_proportional_to_half_life():
    fast = elimination_rate_constant(1.0)
    slow = elimination_rate_constant(10.0)
    assert fast > slow
    assert fast == pytest.approx(10 * slow)


# --- Compartment volumes (O1.1/O1.2) ----------------------------------------

def test_fast_compartment_volume_at_reference_weight_equals_v_ref():
    assert fast_compartment_volume(70.0) == pytest.approx(15.0)


def test_slow_compartment_volume_at_reference_weight_equals_v_s_ref():
    assert slow_compartment_volume(70.0) == pytest.approx(30.0)


def test_compartment_volumes_increase_with_body_weight():
    weights = [40.0, 70.0, 100.0, 150.0]
    v_f_values = [fast_compartment_volume(bw) for bw in weights]
    v_s_values = [slow_compartment_volume(bw) for bw in weights]
    assert v_f_values == sorted(v_f_values)
    assert v_s_values == sorted(v_s_values)


def test_slow_volume_exceeds_fast_volume_at_every_body_weight():
    """V_s_ref (30L) > V_ref (15L) and the slow exponent (0.85) > fast
    (0.75), so V_s > V_f at every body weight, not just the reference."""
    for bw in (30.0, 70.0, 150.0):
        assert slow_compartment_volume(bw) > fast_compartment_volume(bw)


# --- B2/B3: compartment ODEs -------------------------------------------------

def test_fast_compartment_derivative_matches_closed_form():
    a_final, v1, cl, q, c1, c2 = 50.0, 15.0, 0.5, 0.2, 2.0, 1.0
    expected = a_final / v1 - (cl + q) / v1 * c1 + q / v1 * c2
    assert fast_compartment_derivative(a_final, v1, cl, q, c1, c2) == pytest.approx(expected)


def test_slow_compartment_derivative_matches_closed_form():
    v2, q, c1, c2 = 30.0, 0.2, 2.0, 1.0
    expected = (q / v2) * c1 - (q / v2) * c2
    assert slow_compartment_derivative(v2, q, c1, c2) == pytest.approx(expected)


def test_slow_compartment_derivative_is_zero_at_equilibrium():
    """C1 == C2 -> no net transfer -> dC2/dt = 0, regardless of Q/V2."""
    assert slow_compartment_derivative(v2=30.0, q=0.3, c1=5.0, c2=5.0) == 0.0


def test_slow_compartment_derivative_flows_from_high_to_low_concentration():
    """C1 > C2 -> dC2/dt > 0 (slow pool fills); C1 < C2 -> dC2/dt < 0."""
    assert slow_compartment_derivative(v2=30.0, q=0.3, c1=10.0, c2=2.0) > 0.0
    assert slow_compartment_derivative(v2=30.0, q=0.3, c1=2.0, c2=10.0) < 0.0


def test_fast_compartment_derivative_with_no_input_and_no_transfer_is_pure_elimination():
    """A_final=0, Q=0 -> dC1/dt = -CL/V1*C1 (pure first-order elimination)."""
    a_final, v1, cl, q, c1, c2 = 0.0, 15.0, 0.5, 0.0, 4.0, 100.0
    expected = -cl / v1 * c1
    assert fast_compartment_derivative(a_final, v1, cl, q, c1, c2) == pytest.approx(expected)


# --- B4/B5/B6: clearance -----------------------------------------------------

def test_total_clearance_is_the_sum():
    assert total_clearance(cl_renal=0.3, cl_hepatic=0.5) == pytest.approx(0.8)


def test_renal_clearance_matches_closed_form():
    result = renal_clearance(f_filtered=0.9, f_reabsorbed=0.1, gfr_dl_per_min=1.2)
    assert result == pytest.approx(1.2 * 0.9 * 0.9)


def test_renal_clearance_defaults_to_the_confirmed_population_gfr():
    result = renal_clearance(f_filtered=1.0, f_reabsorbed=0.0)
    assert result == pytest.approx(GFR_DEFAULT_DL_PER_MIN)


def test_renal_clearance_is_zero_when_fully_reabsorbed():
    assert renal_clearance(f_filtered=0.8, f_reabsorbed=1.0) == 0.0


def test_cardiac_output_at_reference_weight_equals_6_5_l_per_min():
    assert cardiac_output(70.0) == pytest.approx(6.5)


def test_hepatic_blood_flow_matches_closed_form():
    co = cardiac_output(70.0)
    assert hepatic_blood_flow(co) == pytest.approx(0.260 * co)


def test_unbound_fraction_is_unchanged_at_or_below_bmi_25():
    for bmi in (18.0, 22.0, 25.0):
        assert unbound_fraction(f_u_ref=0.5, bmi=bmi) == pytest.approx(0.5)


def test_unbound_fraction_decreases_above_bmi_25():
    values = [unbound_fraction(f_u_ref=0.5, bmi=b) for b in (25.0, 30.0, 40.0, 50.0)]
    assert values == sorted(values, reverse=True)


def test_hepatic_extraction_ratio_matches_closed_form():
    f_u, cl_int, q_h = 0.5, 2.0, 6.5
    expected = (f_u * cl_int) / (q_h + f_u * cl_int)
    assert hepatic_extraction_ratio(f_u, cl_int, q_h) == pytest.approx(expected)


def test_hepatic_extraction_ratio_is_bounded_0_1():
    for f_u, cl_int, q_h in [(0.01, 0.001, 6.5), (1.0, 1000.0, 6.5), (0.5, 2.0, 0.001)]:
        result = hepatic_extraction_ratio(f_u, cl_int, q_h)
        assert 0.0 <= result < 1.0


def test_hepatic_clearance_matches_closed_form():
    assert hepatic_clearance(q_h=6.5, e_h=0.3) == pytest.approx(1.95)


def test_hepatic_clearance_cannot_exceed_hepatic_blood_flow():
    """E_H < 1 always (well-stirred model), so CL_hepatic = Q_H*E_H < Q_H --
    a basic physiological sanity bound: the liver can't clear faster than
    blood arrives."""
    q_h = cardiac_output(70.0) * 0.260
    e_h = hepatic_extraction_ratio(f_u=0.9, cl_int=1000.0, q_h=q_h)
    assert hepatic_clearance(q_h, e_h) < q_h


# --- End-to-end composition with real nutrient half-lives -------------------

def test_full_clearance_pipeline_composes_for_a_reference_adult(nutrients):
    """Composes B1/B4/B5/B6 with real nutrient half-lives (B1) and the
    reference-adult body-weight defaults (B4-B6), confirming the pieces
    plug together end to end -- not just that each is individually
    correct."""
    bw, bmi = 70.0, 24.0
    gfr = GFR_DEFAULT_DL_PER_MIN
    co = cardiac_output(bw)
    q_h = hepatic_blood_flow(co)
    for nut in nutrients[:10]:
        k_el = elimination_rate_constant(nut["half_life_fast_d"])
        assert k_el > 0.0

        cl_renal = renal_clearance(f_filtered=0.8, f_reabsorbed=0.2, gfr_dl_per_min=gfr)
        f_u = unbound_fraction(f_u_ref=0.5, bmi=bmi)
        e_h = hepatic_extraction_ratio(f_u=f_u, cl_int=1.5, q_h=q_h)
        cl_hepatic = hepatic_clearance(q_h, e_h)
        cl = total_clearance(cl_renal, cl_hepatic)
        assert cl > 0.0, nut["id"]
