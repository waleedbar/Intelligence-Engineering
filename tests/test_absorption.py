"""Tests for sahacore/engine/absorption.py (Layer A, equations A1-A7).

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
    activity_saturation,
    bi_gamma_absorption_kernel,
    activity_sleep_modifier,
    bounded_absorbed_fraction,
    food_matrix_adjustment,
    gamma_pdf,
    gastric_emptying_fraction,
    interaction_sum,
    logit,
    positive_timing_modulator,
    sigmoid,
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


# --- Golden values: TwinAPI workbook, sheet '11 Worked Trace' --------------
#
# That sheet states: "one real meal through Layer A/B ... If your pipeline
# reproduces these numbers, your Still-Circulating build is correct. Every
# number is computed, not illustrative." It publishes both the inputs and
# the resulting F_abs for two nutrients, which makes it a true end-to-end
# check on A4 rather than a property we derived ourselves.

@pytest.mark.parametrize(
    "label,f_base,f_max,dose,k_m,expected_f_abs",
    [
        ("Vitamin C", 0.75, 0.90, 180, 200, 0.652),
        ("Magnesium", 0.30, 0.45, 120, 250, 0.259),
    ],
)
def test_a4_matches_twinapi_worked_trace(label, f_base, f_max, dose, k_m, expected_f_abs):
    result = bounded_absorbed_fraction(
        f_base=f_base, f_max=f_max, dose=dose, k_m=k_m,
        interaction_term=0.0, gamma_cook=0.0, gamma_condition=0.0,
    )
    assert result == pytest.approx(expected_f_abs, abs=0.001), label


def test_bi_gamma_kernel_reduces_to_single_gamma_at_w_one():
    """A1's full mixture with w=1 must be exactly the degenerate
    single-component kernel absorption_kernel() provides."""
    for t in (1, 10, 50, 200):
        mixed = bi_gamma_absorption_kernel(t, w=1.0, k1=2.0, lam1=0.04, k2=3.0, lam2=0.01)
        assert mixed == absorption_kernel(t, 2.0, 0.04)


def test_bi_gamma_kernel_integrates_to_one():
    """Both components are proper densities, so any mixing weight still
    integrates to 1 -- this is what preserves A2's mass conservation."""
    for w in (0.0, 0.4, 0.7, 1.0):
        mass, _ = quad(
            lambda t: bi_gamma_absorption_kernel(t, w, 2.0, 1 / 25, 2.5, 1 / 15),
            0, math.inf,
        )
        assert mass == pytest.approx(1.0, abs=1e-6)


def test_bi_gamma_kernel_is_a_strict_blend_of_its_components():
    w, k1, lam1, k2, lam2 = 0.7, 2.0, 1 / 25, 2.5, 1 / 15
    for t in (5, 25, 73, 200):
        expected = w * absorption_kernel(t, k1, lam1) + (1 - w) * absorption_kernel(t, k2, lam2)
        assert bi_gamma_absorption_kernel(t, w, k1, lam1, k2, lam2) == pytest.approx(expected)


def test_lambda_equals_inverse_theta_for_every_real_nutrient(nutrients):
    """Source: v39sEng2.xlsx, sheet 'P1 MC Engine', section D audit row
    'lambda = 1/theta for all 81 nutrients | 81/81 | PASS' -- correction #1
    in section F is about the PARAMETERIZATION CONVENTION only (shape-scale
    -> shape-rate, lambda = 1/theta); it says nothing about the number of
    mixture components (see absorption.py's docstring). Re-verified here
    against our own registry copy.

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


# --- A5: gastric emptying (Weibull) -----------------------------------------

def test_gastric_emptying_is_zero_at_time_zero():
    assert gastric_emptying_fraction(0.0, t_50=90.0, kappa=1.6) == 0.0


def test_gastric_emptying_is_exactly_half_at_t_50():
    """GE(T_50) = 1 - exp(-ln2*1) = 1 - 0.5 = 0.5 by construction, for
    any kappa (since (T_50/T_50)^kappa = 1 always)."""
    for kappa in (0.5, 1.0, 1.6, 2.0):
        assert gastric_emptying_fraction(90.0, t_50=90.0, kappa=kappa) == pytest.approx(0.5)


def test_gastric_emptying_approaches_one_for_large_t():
    result = gastric_emptying_fraction(10000.0, t_50=90.0, kappa=1.6)
    assert result == pytest.approx(1.0, abs=1e-6)


def test_gastric_emptying_is_monotonically_increasing():
    values = [gastric_emptying_fraction(t, t_50=90.0, kappa=1.6) for t in (0, 30, 60, 90, 150, 300)]
    assert values == sorted(values)


@pytest.mark.parametrize("kappa,label", [(1.6, "solid (Elashoff 1982)"), (1.0, "liquid (Elashoff 1982)")])
def test_gastric_emptying_with_literature_kappa_stays_bounded_0_1(kappa, label):
    """Source-cited literature point estimates ('P1 Parameters 134+' row
    18): kappa~1.6 for solids, ~1.0 for liquids."""
    for t in (0, 30, 90, 200):
        result = gastric_emptying_fraction(t, t_50=90.0, kappa=kappa)
        assert 0.0 <= result <= 1.0, label


# --- A6: activity/sleep timing effect ---------------------------------------

def test_activity_saturation_is_zero_at_zero_met():
    assert activity_saturation(met=0.0, k_act=45.0) == 0.0


def test_activity_saturation_approaches_one_at_high_met():
    assert activity_saturation(met=1e9, k_act=45.0) == pytest.approx(1.0, abs=1e-6)


def test_activity_saturation_is_half_when_met_equals_k_act():
    assert activity_saturation(met=45.0, k_act=45.0) == pytest.approx(0.5)


def test_activity_sleep_modifier_is_one_at_baseline():
    """Both effects off (g_act=0, I_sleep=0) -> exp(0) = 1: no modulation."""
    assert activity_sleep_modifier(g_act=0.0, beta_act=0.005, i_sleep=0.0, beta_sleep=-0.2) == pytest.approx(1.0)


def test_activity_sleep_modifier_matches_closed_form():
    g_act, beta_act, i_sleep, beta_sleep = 0.6, 0.005, 1.0, -0.2
    expected = math.exp(beta_act * g_act + beta_sleep * i_sleep)
    assert activity_sleep_modifier(g_act, beta_act, i_sleep, beta_sleep) == pytest.approx(expected)


# --- A3: positive timing modulator ------------------------------------------

def test_positive_timing_modulator_is_always_strictly_positive():
    """Source's own stated guarantee: m_i(t) > 0 by construction."""
    cases = [
        dict(t=0, eta_c1=0.1, phi_1=400, eta_c2=0.05, phi_2=800, eta_act=0.005,
             g_act=0.5, eta_ge=0.01, g_ge=0.8, eta_sleep=-0.2, i_sleep=1.0, eta_matrix=0.0),
        dict(t=1440, eta_c1=-0.5, phi_1=0, eta_c2=-0.3, phi_2=0, eta_act=-1.0,
             g_act=1.0, eta_ge=-1.0, g_ge=1.0, eta_sleep=-5.0, i_sleep=1.0, eta_matrix=-2.0),
    ]
    for kwargs in cases:
        assert positive_timing_modulator(**kwargs) > 0.0


def test_positive_timing_modulator_is_one_when_every_term_is_neutral():
    """All eta coefficients zero -> exponent=0 -> m_i(t)=1 (no reshaping)."""
    result = positive_timing_modulator(
        t=600.0, eta_c1=0.0, phi_1=0.0, eta_c2=0.0, phi_2=0.0,
        eta_act=0.0, g_act=0.5, eta_ge=0.0, g_ge=0.5,
        eta_sleep=0.0, i_sleep=1.0, eta_matrix=0.0,
    )
    assert result == pytest.approx(1.0)


def test_positive_timing_modulator_matches_closed_form():
    kwargs = dict(
        t=300.0, eta_c1=0.1, phi_1=420.0, eta_c2=0.04, phi_2=900.0,
        eta_act=0.006, g_act=0.4, eta_ge=0.02, g_ge=0.3,
        eta_sleep=-0.15, i_sleep=0.0, eta_matrix=0.05,
    )
    expected_exponent = (
        kwargs["eta_c1"] * math.cos(2 * math.pi * (kwargs["t"] - kwargs["phi_1"]) / 1440)
        + kwargs["eta_c2"] * math.cos(4 * math.pi * (kwargs["t"] - kwargs["phi_2"]) / 1440)
        + kwargs["eta_act"] * kwargs["g_act"]
        + kwargs["eta_ge"] * kwargs["g_ge"]
        + kwargs["eta_sleep"] * kwargs["i_sleep"]
        + kwargs["eta_matrix"]
    )
    assert positive_timing_modulator(**kwargs) == pytest.approx(math.exp(expected_exponent))


def test_positive_timing_modulator_composes_with_a5_a6_a7_outputs():
    """End-to-end composition using A5's gastric_emptying_fraction, A6's
    activity_saturation, and A7's food_matrix_adjustment (Phase 1 default)
    as the actual g_ge/g_act/eta_matrix inputs -- confirms the pieces
    plug together, not just that each is individually correct."""
    g_ge = gastric_emptying_fraction(60.0, t_50=90.0, kappa=1.6)
    g_act = activity_saturation(met=6.0, k_act=45.0)
    eta_matrix = food_matrix_adjustment({}, {}, {})
    result = positive_timing_modulator(
        t=600.0, eta_c1=0.1, phi_1=420.0, eta_c2=0.03, phi_2=900.0,
        eta_act=0.006, g_act=g_act, eta_ge=0.02, g_ge=g_ge,
        eta_sleep=-0.1, i_sleep=0.5, eta_matrix=eta_matrix,
    )
    assert result > 0.0
    assert math.isfinite(result)


# --- A4: bounded absorbed fraction ------------------------------------------

def test_logit_and_sigmoid_are_inverses():
    for p in (0.01, 0.2, 0.5, 0.8, 0.99):
        assert sigmoid(logit(p)) == pytest.approx(p, rel=1e-9)


def test_sigmoid_matches_naive_form_within_safe_range():
    for x in (-20, -1, 0, 1, 20):
        naive = 1.0 / (1.0 + math.exp(-x))
        assert sigmoid(x) == pytest.approx(naive, rel=1e-9)


def test_sigmoid_does_not_overflow_for_extreme_arguments():
    assert sigmoid(-1e6) == pytest.approx(0.0, abs=1e-12)
    assert sigmoid(1e6) == pytest.approx(1.0, abs=1e-12)


def test_interaction_sum_matches_closed_form():
    coeffs = {"a": 0.3, "b": -0.2}
    values = {"a": 0.5, "b": 2.0}
    expected = 0.3 * math.tanh(0.5) + (-0.2) * math.tanh(2.0)
    assert interaction_sum(coeffs, values) == pytest.approx(expected)


def test_interaction_sum_treats_missing_coefficients_as_zero():
    assert interaction_sum({}, {"a": 5.0, "b": -3.0}) == 0.0


def test_bounded_absorbed_fraction_is_f_base_at_zero_dose_and_neutral_terms():
    """dose=0 -> log1p(0)=0; interaction/cook/condition=0 -> logit_arg
    alone survives -> sigmoid(logit(F_base/F_max)) = F_base/F_max exactly
    -> F_abs = F_max*(F_base/F_max) = F_base."""
    f_base, f_max = 0.4, 0.9
    result = bounded_absorbed_fraction(
        f_base=f_base, f_max=f_max, dose=0.0, k_m=200.0,
        interaction_term=0.0, gamma_cook=0.0, gamma_condition=0.0,
    )
    assert result == pytest.approx(f_base, rel=1e-9)


@pytest.mark.parametrize("dose", [0.0, 1.0, 50.0, 500.0, 5000.0, 1e7])
def test_bounded_absorbed_fraction_stays_in_0_f_max_for_any_dose(dose):
    result = bounded_absorbed_fraction(
        f_base=0.3, f_max=0.85, dose=dose, k_m=200.0,
        interaction_term=0.2, gamma_cook=-0.1, gamma_condition=0.05,
    )
    assert 0.0 <= result <= 0.85


def test_bounded_absorbed_fraction_decreases_with_increasing_dose():
    """log1p(dose/Km) grows with dose and is subtracted -> F_abs is
    monotonically decreasing in dose (transporter saturation)."""
    common = dict(f_base=0.3, f_max=0.85, k_m=200.0, interaction_term=0.0, gamma_cook=0.0, gamma_condition=0.0)
    values = [bounded_absorbed_fraction(dose=d, **common) for d in (0, 50, 200, 1000, 5000)]
    assert values == sorted(values, reverse=True)


def test_bounded_absorbed_fraction_stays_bounded_for_all_81_real_nutrients_f_max(nutrients):
    """Uses every real nutrient's f_max from nutrients_81.json (the one
    A4 input that IS fully populated) with a synthetic-but-plausible
    f_base/dose/km, since F_base/Km themselves are the still-tracked gap."""
    for nut in nutrients:
        f_max = nut["f_max"]
        f_base = f_max * 0.5
        result = bounded_absorbed_fraction(
            f_base=f_base, f_max=f_max, dose=100.0, k_m=200.0,
            interaction_term=0.0, gamma_cook=0.0, gamma_condition=0.0,
        )
        assert 0.0 <= result <= f_max, nut["id"]
