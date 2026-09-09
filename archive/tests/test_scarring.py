"""Tests for sahacore/engine/scarring.py (Layer M, equations M1x and M2).

Source: v39sEng2.xlsx, sheet 'M-EQ LayerM Equations', rows M1/M1x/M2.
"""
import json
import math
from pathlib import Path

import pytest

from sahacore.engine.scarring import (
    effective_repair_capacity,
    exact_scarring_update,
    half_life_days,
    healthy_recovery,
    is_bistability_safe,
    overshoot,
    pinned_repair_km,
    pinned_repair_vmax,
    scarring_equilibrium,
    scarring_ratio,
    time_constant_days,
)

DATA_DIR = Path(__file__).parent.parent / "sahacore" / "data"


@pytest.fixture(scope="module")
def scarring_params() -> list[dict]:
    return json.loads((DATA_DIR / "layer_m_scarring_params_12.json").read_text(encoding="utf-8"))


# --- Golden-value regression: Live Verification Lab, LAB 4 ----------------

def test_full_scarring_pipeline_matches_live_verification_lab_lab4():
    """Source: v39sEng2.xlsx, sheet 'Live Verification Lab', LAB 4 --
    'LM-P01/P03 · the Layer-M scar update, live: bounded, step-size exact,
    half-life ln2/beta'. Every number here (inputs AND expected outputs)
    is transcribed directly from Dr. Ali's own pre-computed worked
    example (rows 124-140), not derived by us -- the strongest available
    verification, same standard as A1's Live Verification Lab check."""
    s_t, z_t, theta_elastic = 0.65, 62.0, 50.0
    alpha_scar, beta_autophagy, gamma_scar, dt_day, vmax_base = 0.004, 0.001, 0.69, 1.0, 1.0

    o = overshoot(z_t, theta_elastic)
    assert o == pytest.approx(0.24)  # B132

    s_next = exact_scarring_update(s_t, alpha_scar, beta_autophagy, o, dt_day)
    assert s_next == pytest.approx(0.6496863075190548, rel=1e-12)  # B135
    assert 0.0 <= s_next <= 1.0  # B136: "LM-P01 bounds verdict ... PASS"

    vmax_eff = effective_repair_capacity(vmax_base, gamma_scar, s_next)
    assert vmax_eff == pytest.approx(0.6387235468928708, rel=1e-12)  # B140


# --- overshoot ---------------------------------------------------------

@pytest.mark.parametrize("z_total,theta", [(30, 68), (68, 68), (0, 45)])
def test_overshoot_is_exactly_zero_at_or_below_threshold(z_total, theta):
    assert overshoot(z_total, theta) == 0.0


def test_overshoot_matches_closed_form_above_threshold():
    z_total, theta = 90.0, 60.0
    assert overshoot(z_total, theta) == pytest.approx((90.0 - 60.0) / 60.0)


def test_overshoot_scales_with_theta_elastic(scarring_params):
    """Same absolute excess damage overshoots more for a lower-threshold
    cluster (e.g. C7, theta=44) than a higher-threshold one (e.g. C4, theta=70)."""
    by_id = {r["cluster_id"]: r["theta_elastic_au"] for r in scarring_params}
    z_total = 80.0
    over_c7 = overshoot(z_total, by_id["C7"])
    over_c4 = overshoot(z_total, by_id["C4"])
    assert over_c7 > over_c4


# --- exact_scarring_update (M1x) ----------------------------------------

def test_scarring_update_is_pure_decay_when_overshoot_is_zero():
    s_prev, beta_k, dt = 0.4, 0.001, 1.0
    result = exact_scarring_update(s_prev, alpha_scar_k=0.005, beta_k=beta_k, over_k=0.0, dt_day=dt)
    assert result == pytest.approx(s_prev * math.exp(-beta_k * dt))


# --- Bistability guard: the sheet says "assert these at build time" -------

def test_guard_passes_just_inside_every_cluster_bound(scarring_params):
    """Source: '★ Scarring Bistability Guard' section 3, "PER-CLUSTER
    BOUNDS (assert these at build time)".

    Driving at exactly the published MAX alpha/beta lands ON the boundary
    to within the sheet's own rounding -- e.g. C1 is gamma*r = 0.6*2.42 =
    1.452 against a published bound of 1.45, both 2-decimal figures of the
    same quantity. So the guard is exercised just inside (99% of the cap),
    which is unambiguous, and its rejection side is covered by the test
    below."""
    for row in scarring_params:
        beta = 0.001
        alpha = row["max_alpha_beta_ratio"] * 0.99 * beta
        assert is_bistability_safe(row["gamma_scar"], alpha, beta, row["bound_gamma_r"]), row["cluster_id"]


def test_published_bound_and_max_ratio_agree_to_the_sheets_rounding(scarring_params):
    """bound_gamma_r is gamma_scar * MAX(alpha/beta); both are published to
    two decimals, so they agree to within that rounding and no further."""
    for row in scarring_params:
        product = row["gamma_scar"] * row["max_alpha_beta_ratio"]
        assert row["bound_gamma_r"] == pytest.approx(product, abs=0.01), row["cluster_id"]


def test_exceeding_a_cluster_max_ratio_trips_the_guard(scarring_params):
    """The guard must actually reject: 10% past the shipped cap fails."""
    for row in scarring_params:
        beta = 0.001
        alpha = row["max_alpha_beta_ratio"] * 1.10 * beta
        assert not is_bistability_safe(row["gamma_scar"], alpha, beta, row["bound_gamma_r"]), row["cluster_id"]


def test_v_ratio_matches_the_sheets_own_closed_form(scarring_params):
    """The sheet derives V_k = 1.443 * tau_dam,k / tau_heal,k and ships the
    result per cluster; recomputing it catches a transcription slip in
    either tau column."""
    for row in scarring_params:
        expected = 1.443 * row["tau_dam_days"] / row["tau_heal_days"]
        assert row["v_ratio"] == pytest.approx(expected, abs=0.01), row["cluster_id"]


def test_pinned_repair_constants_follow_the_declared_identities(scarring_params):
    """K_m = theta_elastic (declared choice) and V_max = theta_elastic /
    tau_heal (from V_max/K_m = 1/tau_heal). Their ratio must therefore be
    exactly 1/tau_heal for every cluster."""
    for row in scarring_params:
        theta, tau_heal = row["theta_elastic_au"], row["tau_heal_days"]
        km = pinned_repair_km(theta)
        vmax = pinned_repair_vmax(theta, tau_heal)
        assert km == theta
        assert vmax / km == pytest.approx(1.0 / tau_heal)


def test_scarring_equilibrium_is_bounded_and_monotonic():
    """S*(Z) = r*over/(1+r*over) is in [0,1) for any nonnegative forcing
    and rises with overshoot -- the property the bistability analysis
    rests on."""
    alpha, beta = 0.004, 0.001
    values = [scarring_equilibrium(alpha, beta, over) for over in (0.0, 0.1, 0.5, 1.0, 10.0)]
    assert values[0] == 0.0
    assert all(0.0 <= v < 1.0 for v in values)
    assert values == sorted(values)


def test_scarring_ratio_is_alpha_over_beta():
    assert scarring_ratio(0.004, 0.001) == pytest.approx(4.0)


def test_official_layer_m_acceptance_battery_lm_r01_to_lm_r12():
    """Source: '06_DATA_SERVER_EQUATIONS' rows 57-69 -- the workbook's own
    12-point acceptance battery for Layer M (LM-R01..LM-R12), each with a
    published expected value and a stated tolerance (1e-15 for most).
    These are the values the reference implementation is required to
    produce; running our own functions against every one of them is the
    strongest conformance check available for this layer."""
    s, z, theta = 0.65, 62.0, 50.0
    alpha, beta, gamma, dt, vmax_base = 0.004, 0.001, 0.69, 1.0, 1.0

    o = overshoot(z, theta)
    assert o == pytest.approx(0.24, abs=1e-15)                     # LM-R01

    a = alpha * o
    assert a == pytest.approx(0.00096, abs=1e-15)                  # LM-R02

    q = a + beta
    assert q == pytest.approx(0.00196, abs=1e-15)                  # LM-R03
    assert a / q == pytest.approx(0.489795918367347, abs=1e-15)    # LM-R04

    s_next = exact_scarring_update(s, alpha, beta, o, dt)
    assert s_next == pytest.approx(0.649686307519055, abs=1e-15)   # LM-R05

    assert time_constant_days(beta) == pytest.approx(1000, abs=1e-12)          # LM-R06
    assert half_life_days(beta) == pytest.approx(693.147180559945, abs=1e-12)  # LM-R07

    repair_ratio = effective_repair_capacity(1.0, gamma, s_next)
    assert repair_ratio == pytest.approx(0.638723546892871, abs=1e-15)          # LM-R08
    vmax_eff = effective_repair_capacity(vmax_base, gamma, s_next)
    assert vmax_eff == pytest.approx(0.638723546892871, abs=1e-15)              # LM-R09

    assert 0.0 <= s_next <= 1.0                                                 # LM-R10

    s_365, memory_pct = healthy_recovery(s, beta, 365.0)
    assert s_365 == pytest.approx(0.451227823070686, abs=1e-15)                 # LM-R11
    assert memory_pct == pytest.approx(69.4196650877979, abs=1e-12)             # LM-R12


def test_scarring_update_uses_the_reference_tolerance_not_exact_zero():
    """The canonical reference implementation ('06_DATA_SERVER_EQUATIONS',
    M1-04/M1-05, BUILD_LOCKED) branches on `q <= tol` with tol=1e-12, not
    on q == 0 -- a q below that is numerically indistinguishable from no
    dynamics at all, and a/q would be meaningless."""
    result = exact_scarring_update(s_prev=0.42, alpha_scar_k=0.0, beta_k=1e-15, over_k=0.0, dt_day=1.0)
    assert result == 0.42


def test_scarring_update_is_unchanged_with_zero_forcing_and_zero_clearance():
    """q = a + beta_k = 0 degenerate branch: dS/dt = 0 identically, so S
    must stay exactly what it was, not raise ZeroDivisionError."""
    result = exact_scarring_update(s_prev=0.3, alpha_scar_k=0.0, beta_k=0.0, over_k=5.0, dt_day=1.0)
    assert result == 0.3


def test_scarring_update_matches_closed_form_coefficients():
    s_prev, alpha, beta, over, dt = 0.2, 0.005, 0.001, 1.5, 1.0
    a = alpha * over
    q = a + beta
    s_inf = a / q
    expected = s_inf + (s_prev - s_inf) * math.exp(-q * dt)
    result = exact_scarring_update(s_prev, alpha, beta, over, dt)
    assert result == pytest.approx(expected, rel=1e-12)


@pytest.mark.parametrize("s_prev", [0.0, 0.3, 0.999])
def test_scarring_update_stays_in_zero_one_even_at_the_documented_worst_case_ratio(s_prev, scarring_params):
    """Source's own claim: S* = a/(a+b) in [0,1) for ANY nonnegative a and
    positive b -- tested here at each cluster's own registry-derived
    worst-case alpha/beta ratio (max_alpha_beta_ratio), the specific
    scenario the source cites as the one that broke the earlier (pre-v35.4)
    form."""
    beta_k = 0.001
    for row in scarring_params:
        alpha_scar_k = row["max_alpha_beta_ratio"] * beta_k
        result = exact_scarring_update(s_prev, alpha_scar_k, beta_k, over_k=1.0, dt_day=1.0)
        assert 0.0 <= result < 1.0, row["cluster_id"]


def test_scarring_update_converges_to_the_analytic_equilibrium_under_sustained_overshoot():
    alpha, beta, over, dt = 0.005, 0.001, 2.0, 1.0
    a = alpha * over
    q = a + beta
    s_star = a / q
    s = 0.0
    prev = s
    for _ in range(5000):
        s = exact_scarring_update(s, alpha, beta, over, dt)
        assert s >= prev - 1e-12
        prev = s
    assert s == pytest.approx(s_star, rel=1e-3)


# --- effective_repair_capacity (M2) --------------------------------------

def test_repair_capacity_is_unpenalized_at_zero_scarring():
    assert effective_repair_capacity(v_max_base=0.1, gamma_scar_k=0.6, s_k=0.0) == pytest.approx(0.1)


def test_repair_capacity_decreases_monotonically_with_scarring():
    values = [effective_repair_capacity(0.1, 0.6, s) for s in (0.0, 0.2, 0.5, 0.8, 1.0)]
    assert values == sorted(values, reverse=True)
    assert values[-1] < values[0]


def test_repair_capacity_halves_at_s_equals_one_for_gamma_scar_ln2():
    """Source's own worked note: 'gamma~0.69 halves at S_k=1' -- gamma_scar
    = ln(2) makes exp(-gamma*1) = 0.5 exactly."""
    result = effective_repair_capacity(v_max_base=1.0, gamma_scar_k=math.log(2), s_k=1.0)
    assert result == pytest.approx(0.5)


def test_m_c6_overlay_matches_the_surgical_integration_contract(scarring_params):
    """Source: sheet 'M-C6 Integration' -- "Layer M's ONLY change to a
    locked equation: multiply the C6 repair ceiling by the scarring
    overlay. Nothing else in Layer C changes."

        before: repair_k = V_max      * Z_k / (Km*(1+SUM) + Z_k)
        after:  repair_k = [V_max*e^(-gamma*S_k)] * Z_k / (Km*(1+SUM) + Z_k)

    So scarring.py's effective_repair_capacity is exactly what should be
    handed to repair.py's competitive_repair_rate as its Vm -- verified
    here end to end, including the sheet's own stated safety properties."""
    from sahacore.engine.repair import competitive_repair_rate

    z = {"Z1": 4.0, "Z2": 2.0, "Z3": 6.0}
    km = {"Z1": 0.5, "Z2": 0.3, "Z3": 0.4}
    vm_base = {"Z1": 0.1, "Z2": 0.05, "Z3": 0.02}
    gamma, s_k = 0.6, 0.5

    scarred_vm = {p: effective_repair_capacity(vm_base[p], gamma, s_k) for p in vm_base}
    before = competitive_repair_rate("Z1", z, vm_base, km)
    after = competitive_repair_rate("Z1", z, scarred_vm, km)

    # "can only REDUCE repair, never invert sign or break positivity"
    assert 0.0 < after < before

    # the overlay scales the ceiling only: the ratio is exactly exp(-gamma*S)
    assert after / before == pytest.approx(math.exp(-gamma * s_k))

    # "Flag-off equivalence: gamma=0 OR S_k=0 -> overlay = 1 -> the
    #  original C6 engine is recovered exactly."
    for off_gamma, off_s in ((0.0, 0.5), (0.6, 0.0)):
        off_vm = {p: effective_repair_capacity(vm_base[p], off_gamma, off_s) for p in vm_base}
        assert competitive_repair_rate("Z1", z, off_vm, km) == pytest.approx(before)


def test_repair_capacity_never_negative_or_exceeds_base(scarring_params):
    for row in scarring_params:
        for s_k in (0.0, 0.5, 1.0):
            result = effective_repair_capacity(1.0, row["gamma_scar"], s_k)
            assert 0.0 < result <= 1.0, row["cluster_id"]
