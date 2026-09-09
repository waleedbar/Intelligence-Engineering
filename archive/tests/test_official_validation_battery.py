"""The workbook's own validation gates, run against this build.

Source: v39sEng2.xlsx, sheet '★ Validation Test Battery' -- "Named
mathematical, software and model-admission tests ... A BLOCKING failure
stops the corresponding module."

Only the gates whose target layers are actually built are implemented
here; each test is named for its official ID so a failure maps straight
back to the sheet. Gates for unbuilt layers (C4/C6 filter and QSSA
conditioning, S1/S2/S5) are deliberately absent rather than stubbed.
"""
import json
import math
import random
from pathlib import Path

import pytest
from scipy.integrate import quad

from sahacore.engine.absorption import (
    absorption_kernel,
    bi_gamma_absorption_kernel,
    bounded_absorbed_fraction,
)
from sahacore.engine.damage import exact_excess_damage_update
from sahacore.engine.repair import competitive_repair_rates
from sahacore.engine.scarring import (
    exact_scarring_update,
    half_life_days,
    overshoot,
    time_constant_days,
)

DATA_DIR = Path(__file__).parent.parent / "sahacore" / "data"


@pytest.fixture(scope="module")
def nutrients() -> list[dict]:
    return json.loads((DATA_DIR / "nutrients_81.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def pathways() -> list[dict]:
    return json.loads((DATA_DIR / "tvmcd_pathways_15.json").read_text(encoding="utf-8"))


# --- LEVEL 1: COMPONENT ----------------------------------------------------

def test_gate_c1_gamma_kernel_integrates_to_one_for_all_81_nutrients(nutrients):
    """C1 (BLOCKING) -- "Integrate the normalised kernel over 0->inf
    numerically. Pass: |INTEGRAL h - 1| < 1e-6 for all 81 nutrients."

    Run as specified: numeric quadrature, every nutrient, the sheet's own
    tolerance -- not a closed-form CDF shortcut."""
    for nut in nutrients:
        k, lam = nut["gamma_k_shape"], nut["lambda_per_min"]
        mass, _ = quad(lambda t: absorption_kernel(t, k, lam), 0, math.inf)
        assert abs(mass - 1.0) < 1e-6, f"{nut['id']}: mass={mass}"


def test_gate_c1_holds_for_the_bi_gamma_mixture_too(nutrients):
    """C1 applies to A1's canonical mixture form, not just its degenerate
    case: a mixture of two proper densities is still a proper density, so
    the same tolerance must hold for any mixing weight."""
    for nut in nutrients[:15]:
        k, lam = nut["gamma_k_shape"], nut["lambda_per_min"]
        for w in (0.3, 0.7):
            mass, _ = quad(
                lambda t: bi_gamma_absorption_kernel(t, w, k, lam, k * 1.25, lam * 1.6),
                0, math.inf,
            )
            assert abs(mass - 1.0) < 1e-6, f"{nut['id']} w={w}: mass={mass}"


def test_gate_c2_bounded_absorption_monte_carlo(nutrients):
    """C2 (BLOCKING) -- "Monte-Carlo doses from 0 to 5x K_m. Pass: F_abs <=
    F_max in 100% of draws."

    Drawn over every nutrient's registry F_max, with F_base and K_m swept
    across their registry-documented ranges (F_base 0.01-1.0, K_m
    10-5000 mg per 'P1 Parameters 134+'), since those two are still-missing
    per-nutrient values.

    *** THIS GATE IS CURRENTLY WEAKER THAN IT LOOKS ***
    F_max is 1.0 for all 81 rows of the nutrient registry, because the sheet
    we hold ships that column at the placeholder 'P1 Parameters 134+' row 120
    documents: "Nutrient-specific literature; default 1.0 until calibrated".
    F_abs is bounded by 1 by construction, so the ceiling check passes
    trivially today. The test is written to bind properly the moment
    calibrated F_max values arrive -- the companion test below fails if that
    ever silently stops being true. See docs/parameter-gaps.md."""
    rng = random.Random(20260908)
    for nut in nutrients:
        f_max = nut["f_max"]
        for _ in range(40):
            k_m = rng.uniform(10.0, 5000.0)
            f_base = rng.uniform(0.01, 1.0) * f_max
            dose = rng.uniform(0.0, 5.0 * k_m)
            f_abs = bounded_absorbed_fraction(
                f_base=f_base, f_max=f_max, dose=dose, k_m=k_m,
                interaction_term=rng.uniform(-1.0, 1.0),
                gamma_cook=rng.uniform(-0.5, 0.5),
                gamma_condition=rng.uniform(-0.5, 0.5),
            )
            assert 0.0 <= f_abs <= f_max, f"{nut['id']}: F_abs={f_abs} > F_max={f_max}"


def test_gate_c2_is_still_running_against_placeholder_ceilings(nutrients):
    """A standing check on the gate above, not on the engine.

    While every F_max is the uncalibrated 1.0 default, C2's ceiling is
    vacuous. This test states that fact so it cannot be forgotten, and turns
    into the notification that it has changed: once calibrated per-nutrient
    ceilings are loaded, this fails, and the reviewer removes it and this
    note from C2's docstring -- at which point C2 becomes a real bound.

    Source of the placeholder: 'P1 Parameters 134+' row 120, F_max,i,
    calibration method "Nutrient-specific literature; default 1.0 until
    calibrated". Read directly from the workbook, all 81 rows are 1.
    """
    ceilings = {n["f_max"] for n in nutrients}
    assert ceilings == {1.0}, (
        "F_max is no longer uniformly the uncalibrated 1.0 placeholder -- "
        "calibrated ceilings appear to have arrived. Delete this test and the "
        "*** warning *** paragraph in test_gate_c2_bounded_absorption_monte_carlo, "
        "and update docs/parameter-gaps.md."
    )


@pytest.mark.parametrize("t_half_days", [1.0, 7.0, 30.0, 180.0, 365.0])
@pytest.mark.parametrize("dt_day", [0.25, 1.0, 5.0])
def test_gate_c5_zero_order_hold_gain_matches_the_analytic_solution(t_half_days, dt_day):
    """C5 (BLOCKING) -- "Compare each discrete update against the analytic
    solution of its own ODE. Pass: relative error < 1e-9; convention
    matches g = (1-e^(-k*dt))/k."

    C2/C3 solve dZ/dt = -k*Z + u for piecewise-constant u, whose exact
    solution from Z0 over dt is Z0*e^(-k*dt) + (u/k)*(1-e^(-k*dt)). The
    discrete update must reproduce that to 1e-9 relative."""
    k = math.log(2) / t_half_days
    eta, e_k, theta = 0.05, 8.0, 3.0
    u = eta * max(e_k - theta, 0.0)
    z0 = 12.0

    analytic = z0 * math.exp(-k * dt_day) + (u / k) * (1.0 - math.exp(-k * dt_day))
    discrete = exact_excess_damage_update(
        e_k=e_k, z_hi_prev=z0, theta_hi_k=theta, eta_hi_k=eta,
        t_half_hi_k=t_half_days, p_hi=1.0, dt_day=dt_day,
    )
    assert discrete == pytest.approx(analytic, rel=1e-9)

    # and the gain convention itself
    g = -math.expm1(-k * dt_day) / k
    assert g == pytest.approx((1.0 - math.exp(-k * dt_day)) / k, rel=1e-9)


# --- LEVEL 2: SUBSYSTEM ----------------------------------------------------

def test_gate_s3_competitive_repair_saturates_below_sum_of_vmax(pathways):
    """S3 (BLOCKING) -- "Drive all pathways to high damage simultaneously.
    Pass: total repair < SUM V_max."

    Competitive inhibition means each pathway's repair is throttled by
    every other pathway's load, so the aggregate must stay strictly under
    the sum of the individual ceilings however hard the system is driven."""
    vm = {p["pathway_id"]: p["vm"] for p in pathways}
    km = {p["pathway_id"]: p["km"] for p in pathways}
    sum_vmax = sum(vm.values())

    for load in (10.0, 100.0, 1e4, 1e6):
        z = {p["pathway_id"]: load for p in pathways}
        total_repair = sum(competitive_repair_rates(z, vm, km).values())
        assert total_repair < sum_vmax, f"load={load}: {total_repair} !< {sum_vmax}"


def test_gate_s4_scarring_memory_decay_identities():
    """S4 (MONITORED) -- "Apply sustained damage for 30 days, then remove
    it and track S_k. Pass: exact identity t_half = ln(2)/beta and
    tau = 1/beta holds."

    Drives M1x with sustained overshoot for 30 days, then releases it and
    checks the decay phase reproduces both identities from the simulated
    trajectory itself, not merely from the closed-form helpers."""
    alpha, beta, over, dt = 0.004, 0.01, 1.5, 1.0

    s = 0.0
    for _ in range(30):
        s = exact_scarring_update(s, alpha, beta, over, dt)
    s_at_release = s
    assert s_at_release > 0.0

    # release: no overshoot -> pure exponential decay at rate beta
    trajectory = [s]
    for _ in range(2000):
        s = exact_scarring_update(s, alpha, beta, 0.0, dt)
        trajectory.append(s)

    def first_day_at_or_below(fraction: float) -> int:
        target = s_at_release * fraction
        return next(i for i, v in enumerate(trajectory) if v <= target)

    # t_half = ln(2)/beta, tau = 1/beta -- both recovered from the run,
    # to within the 1-day resolution of the simulated step
    assert first_day_at_or_below(0.5) == pytest.approx(half_life_days(beta), abs=1.0)
    assert first_day_at_or_below(1 / math.e) == pytest.approx(time_constant_days(beta), abs=1.0)


def test_gate_s4_overshoot_removal_stops_accumulation():
    """S4's precondition: with the forcing removed, overshoot is exactly
    zero and scarring can only decay, never grow."""
    assert overshoot(z_total_k=40.0, theta_elastic_k=50.0) == 0.0
    s = 0.6
    for _ in range(100):
        nxt = exact_scarring_update(s, alpha_scar_k=0.004, beta_k=0.01, over_k=0.0, dt_day=1.0)
        assert nxt < s
        s = nxt
