"""Layer C: damage accumulation, equation C1 (Dimensionless Cluster Exposure)
in Dr. Ali's v39sEng2 workbook, sheet 'P1 Core Equations'.

Source formula (transcribed verbatim):

    Cbar_i = w_i*C1_i + (1-w_i)*C2_i
    sp_tau(z) = tau*log1p(exp(z/tau))

    r_hi,i = max(0, sp_tau((ln(Cbar_i+eps)-ln(theta_hi,i+eps))/s_hi,i) - sp_tau(0))
    r_lo,i = max(0, sp_tau((ln(theta_lo,i+eps)-ln(Cbar_i+eps))/s_lo,i) - sp_tau(0))

    E_k(t) = SUM_i v_ik * (r_hi,i + r_lo,i)
    v_ik >= 0; SUM_i v_ik = 1

*** SCOPE OF THIS MODULE ***
Cbar_i needs C1_i/C2_i -- the fast/slow plasma and tissue concentrations
that Layer B's compartment ODE (B2/B3) computes over time. Layer B is not
built yet (it needs the still-missing per-nutrient V1/V2/CL/Q values --
see the A2/B4 gap tracked separately). So this module implements every
part of C1 that does NOT require Layer B output as a working, fully
tested function, and takes Cbar_i as a plain input parameter -- ready to
wire to Layer B's real output once that exists, rather than faking it.

r_hi and r_lo share one underlying shape (a max(0, ...) softplus deviation
in log-ratio space); implemented once as _bounded_log_deviation and
specialised for each side, since r_lo,i(Cbar, theta_lo) is the same
function as r_hi,i(theta_lo, Cbar).

eps and tau are read from the caller, not hardcoded here: the source
gives eps_C a data-dependent rule (max(machine_eps, 1e-12*reference), i.e.
it depends on the unit scale in play) rather than a fixed constant, and
tau_soft's "default 1.0" is a tunable engineering constant, not a
physiological one -- both stay explicit inputs per the project convention
of keeping numeric parameters out of code.
"""
import math


def softplus_deviation(z: float, tau: float) -> float:
    """sp_tau(z) = tau * log1p(exp(z / tau)), computed via the numerically
    stable identity log1p(exp(x)) = max(x,0) + log1p(exp(-abs(x))) so this
    never overflows for large |z/tau| (the naive log1p(exp(x)) form raises
    OverflowError in Python once x exceeds ~709, e.g. from an extreme or
    malformed concentration ratio) -- mathematically identical to the naive
    form for every finite x, just stable at the tails."""
    x = z / tau
    return tau * (max(x, 0.0) + math.log1p(math.exp(-abs(x))))


def combined_concentration(c_fast: float, c_slow: float, w_fast: float) -> float:
    """Cbar_i = w_i*C1_i + (1-w_i)*C2_i -- the fast/slow blend for nutrient i.
    c_fast/c_slow are Layer B's C1_i/C2_i; w_fast is the nutrient's w_fast
    field from the registry (nutrients_81.json)."""
    return w_fast * c_fast + (1 - w_fast) * c_slow


def _bounded_log_deviation(a: float, b: float, scale: float, tau: float, eps: float) -> float:
    """Shared shape behind both r_hi and r_lo:
    max(0, sp_tau((ln(a+eps) - ln(b+eps)) / scale) - sp_tau(0))."""
    z = (math.log(a + eps) - math.log(b + eps)) / scale
    return max(0.0, softplus_deviation(z, tau) - softplus_deviation(0.0, tau))


def excess_deviation(cbar: float, theta_hi: float, s_hi: float, tau: float, eps: float) -> float:
    """r_hi,i: baseline-corrected deviation above the high threshold."""
    return _bounded_log_deviation(cbar, theta_hi, s_hi, tau, eps)


def deficiency_deviation(cbar: float, theta_lo: float, s_lo: float, tau: float, eps: float) -> float:
    """r_lo,i: baseline-corrected deviation below the low threshold."""
    return _bounded_log_deviation(theta_lo, cbar, s_lo, tau, eps)


def cluster_exposure(nutrient_deviations: dict[str, float], cluster_weights: dict[str, float]) -> float:
    """E_k = SUM_i v_ik * (r_hi,i + r_lo,i).

    nutrient_deviations: {nutrient_id: r_hi,i + r_lo,i} for nutrients active
    in cluster k. cluster_weights: {nutrient_id: v_ik} for the same cluster,
    e.g. read from nutrient_cluster_weights.json filtered to one cluster_id
    (those weights already sum to 1 across all 81 nutrients per cluster --
    verified in tests/test_layer_c_d_registries.py).
    """
    return sum(
        cluster_weights.get(nutrient_id, 0.0) * deviation
        for nutrient_id, deviation in nutrient_deviations.items()
    )


# --- C2/C3/C4: cluster-level damage accumulation --------------------------
#
# Verified against THREE independently-worded, mutually consistent sheets in
# the same v39sEng2 workbook: 'P1 Core Equations' (rows C2/C3/C4), the more
# terse '★ Equation Backbone' (row C2/C3), and 'EQ · Canonical Build Rows'
# (rows C-004/C-005/C-007, each marked BUILD_LOCKED). All three agree these
# operate on E_k -- the SINGLE dimensionless exposure this cluster's C1
# already aggregated across its nutrients -- not per-nutrient. This also
# matches the state vector's own shape (sql/003_state_vector.sql, '★ State
# Vector v33 (219)'): xi_hi/xi_lo hold exactly 12+12 damage states, one pair
# per cluster, not one per (nutrient, cluster) pair.
#
# Source formulas (C-004/C-005, transcribed verbatim from 'EQ · Canonical
# Build Rows', identical in substance to 'P1 Core Equations' C2/C3):
#
#     k_side,k   = ln(2) / T_half_side,k
#     rho_side,k = exp(-k_side,k * dt_day)
#     g_side,k   = -expm1(-k_side,k * dt_day) / k_side,k
#     u_hi,k  = eta_hi,k * max(E_k - theta_hi,k, 0)^p_hi
#     u_lo,k  = eta_lo,k * max(theta_lo,k - E_k, 0)^p_lo
#     Z_side,k(t+dt) = rho_side,k * Z_side,k(t) + g_side,k * u_side,k
#
# *** REAL, CONFIRMED DATA GAP ***
# eta_hi,k / theta_hi,k / T_half_hi,k (and their lo-side counterparts) are
# genuinely NOT populated as concrete per-cluster numbers anywhere in the
# accessible workbook: 'P1 Parameters 134+' rows 52-55 list them only as
# generic type-level ranges ("0.001-0.1", "varies per cluster"), the same
# pattern already confirmed for the F_base/Km/V1/V2/CL/Q gap tracked
# separately. So these stay plain inputs here, same convention as Cbar_i in
# C1 and Vm in repair.py -- not hardcoded, not faked, not guessed.
#
# p_hi = p_lo = 1.0 IS confirmed (unlike the above): 'P1 Scoring Alerts'
# Section C states it as a GLOBAL CONVENTION ("p_hi = p_lo = 1.0, linear for
# safety"), correcting an earlier p=2 that caused false alarms from data
# entry errors. Still passed explicitly rather than defaulted in code, per
# the project convention of not hardcoding even confirmed constants.

_ZOH_RATE_FLOOR = 1e-9  # k_side,k below this is treated as exactly 0 for g's L'Hopital limit


def _exact_zoh_coefficients(t_half: float, dt_day: float) -> tuple[float, float]:
    """rho_side,k and g_side,k for one exact zero-order-hold damage step.

    g = -expm1(-k*dt)/k is a 0/0 form as k -> 0 (T_half -> infinity, no
    decay): the source's own stated numerically stable limit is g = dt_day
    in that regime, which is exactly what the closed-form limit evaluates
    to. rho = exp(-k*dt) needs no such branch -- exp(0) = 1 is exact."""
    k = math.log(2) / t_half
    rho = math.exp(-k * dt_day)
    g = dt_day if abs(k) < _ZOH_RATE_FLOOR else -math.expm1(-k * dt_day) / k
    return rho, g


def exact_excess_damage_update(
    e_k: float, z_hi_prev: float, theta_hi_k: float, eta_hi_k: float,
    t_half_hi_k: float, p_hi: float, dt_day: float,
) -> float:
    """C2 (C-004): Z_hi,k(t+dt), the exact zero-order-hold update for one
    time step of piecewise-constant excess forcing above theta_hi,k."""
    rho, g = _exact_zoh_coefficients(t_half_hi_k, dt_day)
    u_hi = eta_hi_k * max(e_k - theta_hi_k, 0.0) ** p_hi
    return rho * z_hi_prev + g * u_hi


def exact_deficiency_damage_update(
    e_k: float, z_lo_prev: float, theta_lo_k: float, eta_lo_k: float,
    t_half_lo_k: float, p_lo: float, dt_day: float,
) -> float:
    """C3 (C-005): Z_lo,k(t+dt), the exact zero-order-hold update for one
    time step of piecewise-constant deficiency forcing below theta_lo,k."""
    rho, g = _exact_zoh_coefficients(t_half_lo_k, dt_day)
    u_lo = eta_lo_k * max(theta_lo_k - e_k, 0.0) ** p_lo
    return rho * z_lo_prev + g * u_lo


# D_max = 100 AU is a confirmed universal governance constant ('P1 Scoring
# Alerts' Section C row 123 and the 'GLOBAL CONVENTIONS' block, row 130:
# "All damage states capped at 100 AU"), not a per-cluster tunable -- kept
# as an explicit default rather than hardcoded inline, same treatment as
# tau_soft's documented default 1.0 in C1.
D_MAX_AU = 100.0


def total_damage(z_hi_k: float, z_lo_k: float, repair_rate_k: float, dt_day: float, d_max: float = D_MAX_AU) -> float:
    """C4 (C-007): Z_total,k = clip(Z_hi,k + Z_lo,k - repair_integral, 0, D_max).

    Source: 'EQ · Canonical Build Rows' row C-007 (BUILD_LOCKED):
    "Z_total,k=clip(Z_hi,k+Z_lo,k-repair_integral,0,Dmax)". repair_integral
    is repair_k (repair.py's competitive_repair_rate, AU/time) integrated
    over one step, i.e. repair_rate_k * dt_day -- the natural Euler
    integration of a rate already given in AU/time (repair.py's own units).

    *** NOTE ON SOURCE DISAGREEMENT, RESOLVED IN FAVOR OF THE LOCKED ROW ***
    'P1 Core Equations' row C4 additionally describes a sedentary softplus
    forcing term and a multiplicative MVPA activity modulation folded into
    this same step. 'EQ · Canonical Build Rows' -- the sheet whose own rows
    are individually marked BUILD_LOCKED, i.e. the frozen build spec -- has
    no such terms for C-007, just this clip. Built to the locked, simpler
    form; the activity/sedentary terms are not implemented here pending
    confirmation of which sheet is current (same category of open question
    as the A1 gamma-mixture text turned out to be, but unlike that case
    there is no correction-log entry here proving either side supersedes
    the other -- so this is flagged, not silently guessed)."""
    return max(0.0, min(d_max, z_hi_k + z_lo_k - repair_rate_k * dt_day))
