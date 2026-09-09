"""Tests for sahacore/engine/damage.py (Layer C, equations C1-C4).

Source: v39sEng2.xlsx, sheet 'P1 Core Equations', rows C1-C4; cross-checked
against '★ Equation Backbone' and 'EQ · Canonical Build Rows' (C-004/C-005/
C-007) for C2-C4.
"""
import json
import math
from pathlib import Path

import pytest

from sahacore.engine.damage import (
    D_MAX_AU,
    cluster_exposure,
    combined_concentration,
    deficiency_deviation,
    exact_deficiency_damage_update,
    exact_excess_damage_update,
    excess_deviation,
    softplus_deviation,
    total_damage,
)

DATA_DIR = Path(__file__).parent.parent / "sahacore" / "data"

# Documented defaults from 'P1 Parameters 134+': s_hi,i / s_lo,i default 0.25
# (matches every nutrient's s_hi_log/s_lo_log in nutrients_81.json), tau_soft
# default 1.0. eps has no fixed default in the source (data-dependent), so
# tests use a representative small value.
TAU = 1.0
EPS = 1e-6


def test_softplus_deviation_at_zero_is_tau_ln2():
    for tau in (0.25, 0.5, 1.0):
        assert softplus_deviation(0.0, tau) == pytest.approx(tau * math.log(2), rel=1e-12)


def test_softplus_deviation_does_not_overflow_for_extreme_z():
    """The naive log1p(exp(x)) form raises OverflowError once x > ~709
    (math.exp's limit); the stable identity used here must stay finite and
    match the softplus asymptote (sp_tau(z) ~= z for z >> tau) even for
    values far past that threshold."""
    huge = 1e6
    value = softplus_deviation(huge, tau=1.0)
    assert math.isfinite(value)
    assert value == pytest.approx(huge, rel=1e-9)


def test_softplus_deviation_matches_naive_form_within_safe_range():
    """Confirms the stable rewrite is exactly equivalent to the textbook
    sp_tau(z) = tau*log1p(exp(z/tau)) wherever the naive form doesn't
    overflow, i.e. this is a stability fix, not a behavior change."""
    for z in (-50, -5, -0.1, 0, 0.1, 5, 50, 150):
        for tau in (0.25, 1.0):
            naive = tau * math.log1p(math.exp(z / tau))
            assert softplus_deviation(z, tau) == pytest.approx(naive, rel=1e-9)


def test_softplus_deviation_is_monotonically_increasing():
    tau = 1.0
    zs = [-5, -1, -0.1, 0, 0.1, 1, 5]
    values = [softplus_deviation(z, tau) for z in zs]
    assert values == sorted(values)


@pytest.mark.parametrize("cbar,theta", [(50, 100), (99.9, 100), (1, 100)])
def test_excess_deviation_is_exactly_zero_at_or_below_threshold(cbar, theta):
    """When Cbar <= theta_hi, z = (ln(Cbar+eps)-ln(theta_hi+eps))/s <= 0, and
    since softplus is monotonic, sp_tau(z) <= sp_tau(0), so max(0, ...) = 0
    exactly -- not approximately."""
    assert excess_deviation(cbar, theta, s_hi=0.25, tau=TAU, eps=EPS) == 0.0


@pytest.mark.parametrize("cbar,theta", [(150, 100), (100.1, 100), (1000, 100)])
def test_excess_deviation_is_positive_above_threshold(cbar, theta):
    assert excess_deviation(cbar, theta, s_hi=0.25, tau=TAU, eps=EPS) > 0.0


@pytest.mark.parametrize("cbar,theta", [(150, 100), (100.1, 100)])
def test_deficiency_deviation_is_exactly_zero_at_or_above_threshold(cbar, theta):
    assert deficiency_deviation(cbar, theta, s_lo=0.25, tau=TAU, eps=EPS) == 0.0


@pytest.mark.parametrize("cbar,theta", [(50, 100), (1, 100)])
def test_deficiency_deviation_is_positive_below_threshold(cbar, theta):
    assert deficiency_deviation(cbar, theta, s_lo=0.25, tau=TAU, eps=EPS) > 0.0


def test_excess_and_deficiency_deviation_share_the_same_shape_by_symmetry():
    """r_lo,i(Cbar=b, theta_lo=a) is defined as the same function as
    r_hi,i(Cbar=a, theta_hi=b) with arguments swapped -- verify that holds."""
    a, b, s = 120.0, 80.0, 0.25
    assert deficiency_deviation(b, a, s_lo=s, tau=TAU, eps=EPS) == pytest.approx(
        excess_deviation(a, b, s_hi=s, tau=TAU, eps=EPS)
    )


@pytest.mark.parametrize("w_fast", [0.0, 0.3, 0.5, 1.0])
def test_combined_concentration_is_the_w_fast_weighted_blend(w_fast):
    c_fast, c_slow = 10.0, 4.0
    expected = w_fast * c_fast + (1 - w_fast) * c_slow
    assert combined_concentration(c_fast, c_slow, w_fast) == pytest.approx(expected)


def test_combined_concentration_at_extremes():
    assert combined_concentration(c_fast=10.0, c_slow=4.0, w_fast=1.0) == pytest.approx(10.0)
    assert combined_concentration(c_fast=10.0, c_slow=4.0, w_fast=0.0) == pytest.approx(4.0)


def test_cluster_exposure_is_the_weighted_sum():
    deviations = {"a": 1.0, "b": 2.0, "c": 3.0}
    weights = {"a": 0.5, "b": 0.3, "c": 0.2}
    assert cluster_exposure(deviations, weights) == pytest.approx(0.5 * 1 + 0.3 * 2 + 0.2 * 3)


def test_cluster_exposure_with_real_cluster_weights_and_uniform_deviation():
    """Uses the real nutrient_cluster_weights.json for cluster C12: since
    those weights sum to exactly 1.0 (verified in
    test_layer_c_d_registries.py), giving every nutrient the same deviation
    X must yield exactly X back."""
    weights_rows = json.loads((DATA_DIR / "nutrient_cluster_weights.json").read_text(encoding="utf-8"))
    c12 = {r["nutrient_id"]: r["weight"] for r in weights_rows if r["cluster_id"] == "C12"}
    uniform_deviations = {nid: 2.5 for nid in c12}
    assert cluster_exposure(uniform_deviations, c12) == pytest.approx(2.5, rel=1e-6)


# --- C2/C3: exact zero-order-hold damage update ---------------------------

def test_zoh_gain_matches_live_verification_lab_golden_values():
    """Source: v39sEng2.xlsx, sheet 'Live Verification Lab', LAB 2 -- 'C5 ·
    zero-order-hold gain vs Euler'. Dr. Ali's own workbook pre-computes
    g=(1-exp(-k*dt))/k for k=0.05/day at three dt values; these are those
    exact numbers (row 91-95), not values we derived ourselves -- the
    strongest verification available, matching A1's own Live Verification
    Lab check."""
    k = 0.05
    t_half = math.log(2) / k
    golden = {
        0.25: 0.24844399012237117,
        1.0: 0.9754115099857197,
        5.0: 4.423984338571902,
    }
    for dt_day, expected_g in golden.items():
        # Isolate g via the decay-only branch: exact_excess_damage_update
        # with e_k <= theta_hi_k gives rho*z_prev (no g); instead invert
        # from a unit forcing (eta=1, deviation=1) so the update reduces
        # to rho*0 + g*1 = g exactly.
        result = exact_excess_damage_update(
            e_k=1.0, z_hi_prev=0.0, theta_hi_k=0.0, eta_hi_k=1.0,
            t_half_hi_k=t_half, p_hi=1.0, dt_day=dt_day,
        )
        assert result == pytest.approx(expected_g, rel=1e-9)

def test_excess_update_is_pure_decay_when_exposure_at_or_below_threshold():
    """max(E_k - theta_hi_k, 0) = 0 -> u_hi=0 -> Z_hi(t+dt) = rho*Z_hi(t) exactly."""
    z_prev = 10.0
    t_half, dt_day = 30.0, 1.0
    rho = math.exp(-math.log(2) / t_half * dt_day)
    result = exact_excess_damage_update(
        e_k=5.0, z_hi_prev=z_prev, theta_hi_k=5.0, eta_hi_k=0.05,
        t_half_hi_k=t_half, p_hi=1.0, dt_day=dt_day,
    )
    assert result == pytest.approx(rho * z_prev)


def test_deficiency_update_is_pure_decay_when_exposure_at_or_above_threshold():
    z_prev = 8.0
    t_half, dt_day = 14.0, 1.0
    rho = math.exp(-math.log(2) / t_half * dt_day)
    result = exact_deficiency_damage_update(
        e_k=5.0, z_lo_prev=z_prev, theta_lo_k=5.0, eta_lo_k=0.05,
        t_half_lo_k=t_half, p_lo=1.0, dt_day=dt_day,
    )
    assert result == pytest.approx(rho * z_prev)


def test_excess_update_matches_closed_form_zoh_coefficients():
    t_half, dt_day, eta, theta, e_k, z_prev, p = 30.0, 1.0, 0.05, 3.0, 8.0, 2.0, 1.0
    k = math.log(2) / t_half
    rho = math.exp(-k * dt_day)
    g = -math.expm1(-k * dt_day) / k
    u_hi = eta * max(e_k - theta, 0.0) ** p
    expected = rho * z_prev + g * u_hi
    result = exact_excess_damage_update(e_k, z_prev, theta, eta, t_half, p, dt_day)
    assert result == pytest.approx(expected, rel=1e-12)


def test_excess_and_deficiency_updates_are_symmetric_under_argument_swap():
    """u_lo(E,theta_lo) uses max(theta_lo-E,0), the mirror of u_hi's
    max(E-theta_hi,0) -- so swapping E<->theta reproduces the same update."""
    common = dict(z_hi_prev=4.0, eta_hi_k=0.07, t_half_hi_k=21.0, p_hi=1.0, dt_day=1.0)
    excess = exact_excess_damage_update(e_k=10.0, theta_hi_k=6.0, **common)
    deficiency = exact_deficiency_damage_update(
        e_k=6.0, z_lo_prev=common["z_hi_prev"], theta_lo_k=10.0,
        eta_lo_k=common["eta_hi_k"], t_half_lo_k=common["t_half_hi_k"],
        p_lo=common["p_hi"], dt_day=common["dt_day"],
    )
    assert excess == pytest.approx(deficiency)


def test_g_coefficient_reaches_its_documented_numerically_stable_limit():
    """Source's own stated limit: as k_hi,k -> 0 (T_half -> infinity, i.e.
    damage that never decays), g_hi,k -> dt_day. Using an astronomically
    long T_half must not raise (the naive -expm1(-k*dt)/k form is a 0/0 at
    k=0) and must match that limit."""
    huge_t_half = 1e15
    dt_day = 1.0
    eta_hi_k = 1.0
    e_k, theta_hi_k = 10.0, 0.0
    result = exact_excess_damage_update(
        e_k=e_k, z_hi_prev=0.0, theta_hi_k=theta_hi_k, eta_hi_k=eta_hi_k,
        t_half_hi_k=huge_t_half, p_hi=1.0, dt_day=dt_day,
    )
    assert math.isfinite(result)
    expected_u_hi = eta_hi_k * max(e_k - theta_hi_k, 0.0)
    assert result == pytest.approx(dt_day * expected_u_hi, rel=1e-6)


def test_excess_update_accumulates_toward_a_positive_steady_state_under_constant_forcing():
    """Repeated application under E_k held above theta_hi_k must increase
    Z_hi monotonically and converge -- never overshoot past the analytic
    steady state Z* = eta*(E-theta)^p / (1 - rho) * g / dt-normalized decay,
    which for exact ZOH reduces to Z* = u_hi / k (continuous-time steady
    state of dZ/dt = -k*Z + u_hi)."""
    t_half, dt_day, eta, theta, e_k, p = 10.0, 1.0, 0.1, 2.0, 5.0, 1.0
    k = math.log(2) / t_half
    u_hi = eta * max(e_k - theta, 0.0) ** p
    steady_state = u_hi / k
    z = 0.0
    prev = z
    for _ in range(2000):
        z = exact_excess_damage_update(e_k, z, theta, eta, t_half, p, dt_day)
        assert z >= prev - 1e-12
        prev = z
    assert z == pytest.approx(steady_state, rel=1e-3)


# --- C4: total damage (clip) -----------------------------------------------

def test_total_damage_is_the_plain_sum_minus_repair_in_the_middle_range():
    result = total_damage(z_hi_k=20.0, z_lo_k=5.0, repair_rate_k=3.0, dt_day=1.0)
    assert result == pytest.approx(20.0 + 5.0 - 3.0 * 1.0)


def test_total_damage_clips_at_zero():
    result = total_damage(z_hi_k=1.0, z_lo_k=0.0, repair_rate_k=10.0, dt_day=1.0)
    assert result == 0.0


def test_total_damage_clips_at_d_max():
    result = total_damage(z_hi_k=1000.0, z_lo_k=1000.0, repair_rate_k=0.0, dt_day=1.0)
    assert result == D_MAX_AU


def test_total_damage_respects_a_custom_d_max():
    result = total_damage(z_hi_k=1000.0, z_lo_k=0.0, repair_rate_k=0.0, dt_day=1.0, d_max=50.0)
    assert result == 50.0
