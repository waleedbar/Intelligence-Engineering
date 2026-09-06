"""Layer A: nutrient absorption kernel (equation A1 in Dr. Ali's v39sEng2
workbook, sheet 'P1 Core Equations').

*** KNOWN APPROXIMATION -- NEEDS DR. ALI'S CONFIRMATION ***
The canonical A1 formula is a two-component gamma mixture:

    h_i(tau) = w_i * Gamma(tau; k1_i, lambda1_i) + (1 - w_i) * Gamma(tau; k2_i, lambda2_i)

That needs FOUR per-nutrient numbers (k1, lambda1, k2, lambda2) plus a mixing
weight w_i. The canonical, populated nutrient registry ('P1 Nutrients 81',
verified column-by-column: 21 columns, no hidden k1/k2/lambda1/lambda2
fields) only carries ONE gamma shape/rate pair per nutrient (gamma_k_shape,
lambda_per_min). The only places k1/k2/lambda1/lambda2 appear anywhere in
the eight source workbooks are a generic illustrative demo ('Live
Verification Lab') and a parameter-type registry giving population RANGES,
not per-nutrient values ('P1 Parameters 134+'). Searched all 205 sheets and
all 8 workbooks -- the per-nutrient dual-component table does not exist yet.

Until that data exists, this module implements the SINGLE-component
degenerate case (equivalent to w_i = 1, i.e. no slow absorption component)
using the one (k, lambda) pair the registry actually has. This is an
engineering approximation, not a verified part of Dr. Ali's spec -- it must
be revisited once the missing k2/lambda2/w_i values are provided or
confirmed unnecessary. All numeric parameters are read from the nutrients
table/JSON, per the project convention -- nothing physiological is
hardcoded here.
"""
import math

PHASE_1_ABSORPTION_KERNEL_IS_SINGLE_GAMMA_APPROXIMATION = True


def gamma_log_pdf(t: float, k: float, lam: float) -> float:
    """Natural log of the gamma(k, rate=lam) PDF at t, computed in log-space
    to avoid overflow/underflow for extreme parameters (per A1's stated
    log-space formulation: log Gamma = k*ln(lambda) + (k-1)*ln(t) - lambda*t - lgamma(k)).

    Returns -inf for t <= 0 (the kernel is zero before/at meal ingestion).
    """
    if t <= 0:
        return float("-inf")
    return k * math.log(lam) + (k - 1) * math.log(t) - lam * t - math.lgamma(k)


def gamma_pdf(t: float, k: float, lam: float) -> float:
    """Gamma(k, rate=lam) probability density at t. Zero for t <= 0."""
    if t <= 0:
        return 0.0
    return math.exp(gamma_log_pdf(t, k, lam))


def absorption_kernel(t: float, k: float, lam: float) -> float:
    """h_i(t): the Phase-1 single-gamma approximation of equation A1.
    See the module docstring -- this omits the slow-pathway component
    (k2, lambda2, w_i) that the canonical formula specifies but that the
    nutrient registry does not yet provide values for.
    """
    return gamma_pdf(t, k, lam)
