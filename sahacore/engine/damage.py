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
