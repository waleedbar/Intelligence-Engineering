"""Layer M: durable memory / scarring, equations M1 (as its production
exact-update form M1x) and M2, in Dr. Ali's v39sEng2 workbook, sheet
'M-EQ LayerM Equations'.

Source formulas (transcribed verbatim):

    M1  (Scarring accumulation):
        dS_k/dt = alpha_scar,k * over_k(t) * (1 - S_k) - beta_autophagy,k * S_k
        over_k = max(0, (Z_total,k - theta_elastic,k) / theta_elastic,k)

    M1x (Exact single-state update -- status: PRODUCTION):
        a = alpha_scar,k * over_k
        q = a + beta_k
        S_inf = a / q
        S_next = S_inf + (S - S_inf) * exp(-q * dt)

    M2  (Repair degradation, feeds C6's V_max_eff):
        V_max,k^eff = V_max,k^base * exp(-gamma_scar,k * S_k)

M1's own source note explains why M1x needs no clip: S* = a/(a+b) lies in
[0,1) for any a>=0, b>0 by construction (a strictly earlier form, S* =
(a/b)*over, could exceed 1 -- this is the documented v35.4+ fix). S_next is
a weighted blend of S_inf and the previous S, so it inherits that same
bound as long as S starts in [0,1] and beta_k > 0.

*** SCOPE OF THIS MODULE ***
theta_elastic,k and gamma_scar,k ARE ratified per-cluster numbers (sheet
'M-PARAM Registry', rows 47-60 and 30-43 respectively -- see
layer_m_scarring_params_12.json), unlike the still-missing alpha_scar,k /
beta_autophagy,k (only documented as generic ranges, e.g. "0.001-0.01",
not per-cluster values -- same category of gap as C2/C3's eta_hi,k /
theta_hi,k, tracked separately). So alpha_scar_k and beta_k stay plain
inputs here, same convention as everywhere else in this codebase.
"""
import math


def overshoot(z_total_k: float, theta_elastic_k: float) -> float:
    """over_k = max(0, (Z_total,k - theta_elastic,k) / theta_elastic,k):
    the fraction by which this cluster's total damage exceeds its ratified
    scarring threshold, zero below the threshold."""
    return max(0.0, (z_total_k - theta_elastic_k) / theta_elastic_k)


# Degenerate-q tolerance, taken from the reference implementation's own
# default (sheet '06_DATA_SERVER_EQUATIONS', M1-04/M1-05: `if q <= tol`,
# `tol: float = 1e-12`). Guards not just q == 0 exactly but any q so small
# that a/q and exp(-q*dt) would lose all precision.
_Q_TOLERANCE = 1e-12


def exact_scarring_update(s_prev: float, alpha_scar_k: float, beta_k: float, over_k: float, dt_day: float) -> float:
    """M1x: S_next for one exact time step of piecewise-constant over_k.

    Mirrors the canonical reference implementation published in sheet
    '06_DATA_SERVER_EQUATIONS' (rows M1-02..M1-05, status BUILD_LOCKED),
    including both of its numerical choices:
      - the degenerate branch triggers on q <= tol, not q == 0 exactly;
        with no forcing and no clearance dS/dt = 0 identically, so S is
        unchanged.
      - the step is written with expm1 as
        S + (S_inf - S)*(-expm1(-q*dt)) rather than the algebraically
        identical S_inf + (S - S_inf)*exp(-q*dt); the reference notes
        expm1 "improves precision when q*dt is very small"."""
    a = alpha_scar_k * over_k
    q = a + beta_k
    if q <= _Q_TOLERANCE:
        return s_prev
    s_inf = a / q
    gain = -math.expm1(-q * dt_day)
    return s_prev + (s_inf - s_prev) * gain


def time_constant_days(beta_k: float) -> float:
    """M1-06 (QA/MONITOR): tau = 1/beta, the e-fold time constant -- time
    to 36.8% remaining. The source is explicit that tau is NOT a
    half-life ('M-PARAM Registry' v37.2 kinetic definitions)."""
    return 1.0 / beta_k


def half_life_days(beta_k: float) -> float:
    """M1-07 (QA/MONITOR): t_half = ln(2)/beta, time to 50% remaining."""
    return math.log(2.0) / beta_k


def healthy_recovery(s0: float, beta_k: float, t_days: float) -> tuple[float, float]:
    """M1-09/M1-10 (QA/MONITOR): the zero-overshoot limit of M1. With
    over_k = 0 the accumulation term vanishes and scarring decays purely
    exponentially, S(t) = S0*exp(-beta*t). Returns (S(t), memory
    remaining as a percentage of S0)."""
    s_t = s0 * math.exp(-beta_k * t_days)
    return s_t, 100.0 * s_t / s0


# --- Scarring bistability guard -------------------------------------------
#
# Source: sheet '★ Scarring Bistability Guard' ("per-cluster monotonicity
# bound"). The scarring loop is positive feedback -- damage raises S, S cuts
# repair via V_max_eff = V_max*exp(-gamma*S), less repair means more damage.
# Above a threshold the total-removal curve F(Z) folds and a cluster gains
# TWO stable equilibria (healthy and scarred) for the SAME intake. The sheet
# is explicit about why that is dangerous: "the engine will converge to the
# scarred state and report a stable low score without complaint" -- unlike
# the catastrophic-load guard, nothing fires.
#
#     S*(Z) = r*over / (1 + r*over),   r = alpha_scar / beta_autophagy
#     F(Z)  = k*Z + V_max*exp(-gamma*S*(Z)) * Z/(K_m + Z)
#
# The destabilising term scales with the group gamma*r, so the shipped
# per-cluster caps are bounds on gamma*r (bound_gamma_r in
# layer_m_scarring_params_12.json). The sheet says to "assert these at
# build time" -- tests/test_scarring.py does exactly that for all 12.


def scarring_ratio(alpha_scar_k: float, beta_autophagy_k: float) -> float:
    """r = alpha_scar / beta_autophagy -- the accumulation-to-clearance
    ratio that, multiplied by gamma_scar, drives the bistability fold."""
    return alpha_scar_k / beta_autophagy_k


def scarring_equilibrium(alpha_scar_k: float, beta_autophagy_k: float, over_k: float) -> float:
    """S*(Z) = r*over/(1 + r*over), the scarring level a sustained
    overshoot settles at. Always in [0,1) for r, over >= 0 -- the same
    bound M1x's step inherits."""
    r_over = scarring_ratio(alpha_scar_k, beta_autophagy_k) * over_k
    return r_over / (1.0 + r_over)


def is_bistability_safe(gamma_scar_k: float, alpha_scar_k: float, beta_autophagy_k: float, bound_gamma_r_k: float) -> bool:
    """The guard itself: gamma_scar * r must stay at or under this
    cluster's shipped bound. The bounds are computed conservatively at
    kappa = K_m/theta = 0.5 rather than 1.0, so a cluster whose repair
    saturates earlier than theta only tightens them further."""
    return gamma_scar_k * scarring_ratio(alpha_scar_k, beta_autophagy_k) <= bound_gamma_r_k


# --- Pinned per-cluster repair constants ----------------------------------
#
# Same sheet, section 2 ("V_max AND K_m ARE NOW PINNED -- they were
# 'tissue-specific, unspecified'"). Both follow from quantities already in
# the registries, with no new measurement:
#   - At low damage MM repair linearises to (V_max/K_m)*Z, a first-order
#     rate. That rate IS the recovery timescale, so V_max/K_m = 1/tau_heal.
#   - K_m = theta_elastic is a declared modelling choice: repair
#     half-saturates exactly where scarring begins, which is what makes
#     theta_elastic the scarring threshold at all.


def pinned_repair_km(theta_elastic_k: float) -> float:
    """K_m,k = theta_elastic,k."""
    return theta_elastic_k


def pinned_repair_vmax(theta_elastic_k: float, tau_heal_days_k: float) -> float:
    """V_max,k = theta_elastic,k / tau_heal,k, from V_max/K_m = 1/tau_heal
    together with K_m = theta_elastic."""
    return theta_elastic_k / tau_heal_days_k


def effective_repair_capacity(v_max_base: float, gamma_scar_k: float, s_k: float) -> float:
    """M2: V_max,k^eff = V_max,k^base * exp(-gamma_scar,k * S_k) -- the
    multiplicative repair-capacity penalty from accumulated scarring
    (S_k=0 -> no penalty; higher S_k -> repair.py's competitive_repair_rate
    should be driven with this reduced V_max instead of the base value)."""
    return v_max_base * math.exp(-gamma_scar_k * s_k)
