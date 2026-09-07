"""Tests for sahacore/engine/absorption.py (Layer A, equations A1/A2/A7).

Includes a golden-value regression test transcribed directly from Dr.
Ali's own workbook ('Live Verification Lab', LAB 1), so our implementation
is checked against a number the source itself already verified -- not just
against our own derivation.
"""
import json
import math
from pathlib import Path

import pytest
from scipy.integrate import quad
from scipy.stats import gamma as scipy_gamma

from sahacore.engine.absorption import (
    absorbed_mass_rate,
    absorption_kernel,
    food_matrix_adjustment,
    gamma_pdf,
    unmodulated_normalized_kernel,
)

NUTRIENTS_FILE = Path(__file__).parent.parent / "sahacore" / "data" / "nutrients_81.json"


@pytest.fixture(scope="module")
def nutrients() -> list[dict]:
    return json.loads(NUTRIENTS_FILE.read_text(encoding="utf-8"))


def test_matches_live_verification_lab_worked_example():
    """Source: v39sEng2.xlsx, sheet 'Live Verification Lab', LAB 1, row 16
    (t=10, k1 fast shape=2.5, lambda1 fast rate=0.04 -> f_fast=0.005102652414604033).
    This is the source workbook's OWN pre-computed reference value."""
    value = gamma_pdf(10, k=2.5, lam=0.04)
    assert value == pytest.approx(0.005102652414604033, rel=1e-9)


@pytest.mark.parametrize(
    "t,expected",
    [
        (10, 0.005102652414604033),
        (50, 0.011518072856146798),
        (100, 0.004408956875539648),
        (250, 4.319952509914196e-05),
    ],
)
def test_matches_live_verification_lab_at_several_timepoints(t, expected):
    """Cross-checks our f_fast column against several rows of the same LAB 1 table."""
    assert gamma_pdf(t, k=2.5, lam=0.04) == pytest.approx(expected, rel=1e-9)


def test_zero_or_negative_time_gives_zero_density():
    assert gamma_pdf(0, k=2.5, lam=0.04) == 0.0
    assert gamma_pdf(-5, k=2.5, lam=0.04) == 0.0


def test_lambda_equals_inverse_theta_for_every_real_nutrient(nutrients):
    """Source: v39sEng2.xlsx, sheet 'P1 MC Engine', section D audit row
    'lambda = 1/theta for all 81 nutrients | 81/81 | PASS' -- this is the
    workbook's own record of the corrected single-gamma parameterization
    (section F, correction #1: shape-scale -> shape-rate, lambda = 1/theta),
    re-verified here against our own registry copy.

    Five nutrients are documented exceptions, all confirmed by direct
    re-read of the raw 'P1 Nutrients 81' sheet (not an extraction error
    here) despite the audit log's 81/81 claim:
      - nitrate_mg: lambda=0.0333 vs 1/theta=0.033333... -- a truncated-
        digits rounding artifact (theta=30), not a parameterization error.
      - fat_total_g, aa_tryptophan_mg, aa_aspartate_mg, aa_glutamate_mg:
        lambda doesn't correspond to 1/theta by any consistent ratio --
        genuine, isolated data inconsistencies in the source.
    Flagged explicitly rather than silently excluded."""
    exceptions = {"fat_total_g", "aa_tryptophan_mg", "aa_aspartate_mg", "aa_glutamate_mg", "nitrate_mg"}
    for nut in nutrients:
        if nut["id"] in exceptions:
            continue
        assert nut["lambda_per_min"] == pytest.approx(1.0 / nut["gamma_theta_min"], rel=1e-9), (
            f"{nut['id']}: lambda={nut['lambda_per_min']}, 1/theta={1.0 / nut['gamma_theta_min']}"
        )


def test_lambda_theta_mismatches_are_exactly_the_five_documented_nutrients(nutrients):
    """Locks in the exact shape of the known source-data inconsistencies
    (see test above) so a future registry update either fixes one (this
    test then fails, prompting removal of that exception) or the set stays
    intentional and documented -- it can't silently drift unnoticed."""
    mismatches = {
        nut["id"] for nut in nutrients
        if nut["lambda_per_min"] != pytest.approx(1.0 / nut["gamma_theta_min"], rel=1e-9)
    }
    assert mismatches == {"fat_total_g", "aa_tryptophan_mg", "aa_aspartate_mg", "aa_glutamate_mg", "nitrate_mg"}


def test_matches_scipy_reference_for_every_real_nutrient(nutrients):
    """Our hand-written log-space gamma PDF must agree with scipy's
    battle-tested implementation, for every one of the 81 real (k, lambda)
    pairs actually in the registry -- not just the demo values."""
    sample_times = [1, 10, 60, 240, 720]
    for nut in nutrients:
        k, lam = nut["gamma_k_shape"], nut["lambda_per_min"]
        for t in sample_times:
            ours = absorption_kernel(t, k, lam)
            reference = scipy_gamma.pdf(t, a=k, scale=1.0 / lam)
            assert ours == pytest.approx(reference, rel=1e-9, abs=1e-300), (
                f"{nut['id']} at t={t}: ours={ours}, scipy={reference}"
            )


def test_kernel_mass_over_full_domain_is_one_for_every_real_nutrient(nutrients):
    """A valid gamma PDF integrates to exactly 1 over (0, infinity); this
    confirms every nutrient's (k, lambda) pair is a well-formed distribution
    (using scipy's regularized incomplete gamma, i.e. the exact CDF -- no
    numerical quadrature truncation error, unlike the workbook's own
    trapezoid demo grid)."""
    for nut in nutrients:
        k, lam = nut["gamma_k_shape"], nut["lambda_per_min"]
        mass = scipy_gamma.cdf(math.inf, a=k, scale=1.0 / lam)
        assert mass == pytest.approx(1.0, abs=1e-9), f"{nut['id']}: mass={mass}"


# --- A2: mass-conserving multi-meal absorption -----------------------------

def test_unmodulated_normalized_kernel_matches_absorption_kernel_exactly():
    """The m_i(t)=1 special case: h_i* reduces to h_i identically."""
    k, lam = 2.5, 0.04
    for tau in (1, 10, 50, 100):
        assert unmodulated_normalized_kernel(tau, k, lam) == absorption_kernel(tau, k, lam)


def test_unmodulated_kernel_still_integrates_to_exactly_one(nutrients):
    """Confirms h_i* itself (not just h_i) satisfies the mass-conservation
    precondition INTEGRAL h_i* dtau = 1 in this reduced case, for a sample
    of real nutrients -- not just algebraically identical to h_i, but
    actually still a valid probability kernel."""
    for nut in nutrients[:10]:
        k, lam = nut["gamma_k_shape"], nut["lambda_per_min"]
        mass, _ = quad(lambda tau: unmodulated_normalized_kernel(tau, k, lam), 0, math.inf)
        assert mass == pytest.approx(1.0, abs=1e-6), nut["id"]


def test_absorbed_mass_rate_before_any_meal_is_zero():
    kernel = lambda tau: unmodulated_normalized_kernel(tau, 2.5, 0.04)
    meals = [{"q": 500.0, "t_m": 100.0, "f_abs": 0.8}]
    assert absorbed_mass_rate(t=50.0, meals=meals, h_i_star=kernel) == 0.0


def test_absorbed_mass_rate_matches_closed_form_for_a_single_meal():
    k, lam, q, f_abs, t_m = 2.5, 0.04, 500.0, 0.8, 0.0
    kernel = lambda tau: unmodulated_normalized_kernel(tau, k, lam)
    t = 30.0
    expected = q * f_abs * absorption_kernel(t - t_m, k, lam)
    assert absorbed_mass_rate(t, [{"q": q, "t_m": t_m, "f_abs": f_abs}], kernel) == pytest.approx(expected)


def test_absorbed_mass_rate_sums_contributions_across_multiple_meals():
    k, lam = 2.5, 0.04
    kernel = lambda tau: unmodulated_normalized_kernel(tau, k, lam)
    meals = [
        {"q": 300.0, "t_m": 0.0, "f_abs": 0.7},
        {"q": 400.0, "t_m": 200.0, "f_abs": 0.6},
    ]
    t = 250.0
    expected = sum(m["q"] * m["f_abs"] * absorption_kernel(t - m["t_m"], k, lam) for m in meals)
    assert absorbed_mass_rate(t, meals, kernel) == pytest.approx(expected)


def test_total_absorbed_mass_equals_dose_times_f_abs_mass_conservation():
    """The formula's own stated guarantee: INTEGRAL a_i(t) dt = SUM_m
    q_{i,m} * F_abs,i,m exactly, when h_i* truly integrates to 1 (verified
    above) -- checked here by numerically integrating a_i(t) itself over
    all t for a single meal and comparing to q*F_abs directly."""
    k, lam, q, f_abs, t_m = 2.5, 0.04, 500.0, 0.8, 10.0
    kernel = lambda tau: unmodulated_normalized_kernel(tau, k, lam)
    meals = [{"q": q, "t_m": t_m, "f_abs": f_abs}]
    total, _ = quad(lambda t: absorbed_mass_rate(t, meals, kernel), t_m, math.inf)
    assert total == pytest.approx(q * f_abs, rel=1e-6)


# --- A7: food-matrix guard --------------------------------------------------

def test_food_matrix_adjustment_is_zero_under_the_confirmed_phase_1_default():
    """psi_ij=0 for every component is the actual, confirmed production
    value (see the module's note) -- an empty coefficients dict must
    reproduce that exactly, not require every component to be listed."""
    co_food = {"fiber_g": 20.0, "fat_total_g": 15.0, "polyphenols_mg": 200.0}
    reference = {"fiber_g": 25.0, "fat_total_g": 70.0, "polyphenols_mg": 500.0}
    assert food_matrix_adjustment(co_food, {}, reference) == 0.0


def test_food_matrix_adjustment_matches_closed_form_when_activated():
    """Not currently used in production (Phase 1 keeps psi_ij=0), but the
    general SUM_j psi_ij*tanh(q_j/q_ref,j) form must be correct for
    'Future activation' per the source's own note."""
    co_food = {"a": 10.0, "b": 5.0}
    psi = {"a": 0.3, "b": -0.2}
    ref = {"a": 20.0, "b": 10.0}
    expected = 0.3 * math.tanh(10.0 / 20.0) + (-0.2) * math.tanh(5.0 / 10.0)
    assert food_matrix_adjustment(co_food, psi, ref) == pytest.approx(expected)


def test_food_matrix_adjustment_is_bounded_by_sum_of_abs_psi():
    """|tanh(x)| < 1 always, so |eta_matrix,i| < SUM_j |psi_ij| for any
    coefficients -- a basic sanity bound on the general form."""
    co_food = {"a": 1000.0, "b": 1000.0}
    psi = {"a": 0.5, "b": -0.3}
    ref = {"a": 1.0, "b": 1.0}
    result = food_matrix_adjustment(co_food, psi, ref)
    assert abs(result) < abs(psi["a"]) + abs(psi["b"])
