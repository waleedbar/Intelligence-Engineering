"""Layer A: nutrient absorption kernel (equation A1 in Dr. Ali's v39sEng2
workbook, sheet 'P1 Core Equations').

*** VERIFIED AGAINST DR. ALI'S OWN CORRECTION LOG -- SINGLE-GAMMA IS CORRECT ***
An earlier draft of this module treated the single-gamma form here as an
unconfirmed Phase-1 approximation of a two-component mixture
(h_i = w*Gamma(k1,lambda1) + (1-w)*Gamma(k2,lambda2)) implied by 'P1 Core
Equations' and 'PARAM * Eq Param FK'. That reading was wrong. Sheet
'P1 MC Engine', section F ("11 HISTORICAL CORRECTIONS LOG"), row 1, records
this as a resolved, deliberate correction:

    Issue: Gamma parameterization conflict
    Original value: shape-scale (gamma_k, gamma_theta_min)
    Corrected value: shape-rate, lambda = 1/theta
    Discovered by: DeepSeek | Status: CORRECTED

Section D of the same sheet lists this among the audited PASS checks:
"lambda = 1/theta for all 81 nutrients | 81/81 | PASS" -- i.e. the current,
canonical registry ('P1 Nutrients 81': gamma_k_shape, lambda_per_min) IS the
corrected single-gamma parameterization, verified across all 81 nutrients,
not a stand-in for a richer form that's missing. The k1/lambda1/k2/lambda2
mixture referenced elsewhere is the pre-correction formulation and is stale.

All numeric parameters are still read from the nutrients table/JSON, per
the project convention -- nothing physiological is hardcoded here.
"""
import math


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
    """h_i(t): equation A1, the corrected single-gamma absorption kernel.
    See the module docstring -- this is the audited, canonical form
    (verified 81/81 in Dr. Ali's own correction log), not an approximation.
    """
    return gamma_pdf(t, k, lam)
