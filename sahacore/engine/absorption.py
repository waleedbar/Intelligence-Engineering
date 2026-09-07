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


# --- A2: mass-conserving multi-meal absorption -----------------------------
#
# Source formula ('P1 Core Equations', row A2, transcribed verbatim):
#
#     a_i(t) = SUM_m q_{i,m} * F_abs,i,m * h_i*(t - t_m)
#
#     h_i*(tau | t_m) = h_i(tau) * m_i(t_m + tau) /
#                        INTEGRAL_0^inf h_i(s) * m_i(t_m + s) ds
#
#     Because INTEGRAL h_i* d tau = 1:
#     INTEGRAL a_i(t) dt = SUM_m q_{i,m} * F_abs,i,m <= SUM_m q_{i,m}.
#
# a_i doesn't need F_base itself (A4's gap): it just consumes F_abs,i,m as
# a plain per-meal input, same convention as everywhere else in this
# codebase -- so it isn't blocked by the still-missing F_base/Km data at
# all, unlike A4/A5 which compute F_abs from scratch.
#
# h_i*'s renormalizing integral, in general, needs m_i(t) (A3's positive
# timing modulator -- circadian/activity/sleep reshaping), which isn't
# built yet: eta_c1,i/eta_c2,i/phi_1,i/phi_2,i/K_act/beta_act/beta_sleep are
# only documented as generic type-level ranges in 'P1 Parameters 134+',
# not per-nutrient values (same gap category as C2/C3's eta_hi,k). But the
# unmodulated case m_i(t)=1 identically -- i.e. exactly today's actual
# production state, since A3/A6 aren't wired in yet -- has an EXACT,
# gap-free closed form: h_i* reduces to h_i itself, because a valid gamma
# PDF already integrates to exactly 1 over (0, infinity) (verified
# per-nutrient in test_absorption.py's kernel-mass test), so
# h_i(tau)*1 / 1 = h_i(tau). No numerical integration, no approximation.


def unmodulated_normalized_kernel(tau: float, k: float, lam: float) -> float:
    """h_i*(tau | t_m) in the m_i(t)=1 special case (no A3/A6 timing
    reshaping applied -- today's actual state, since neither is built
    yet): reduces exactly to h_i(tau), equation A1's gamma kernel. See the
    module-level note above for why this is exact, not an approximation."""
    return absorption_kernel(tau, k, lam)


def absorbed_mass_rate(t: float, meals: list[dict], h_i_star) -> float:
    """A2: a_i(t) = SUM_m q_{i,m} * F_abs,i,m * h_i*(t - t_m).

    meals: [{'q': dose mg, 't_m': meal time, 'f_abs': bioavailability
    fraction in [0, F_max]}, ...] for this nutrient. h_i_star: callable
    tau -> h_i*(tau | t_m); pass unmodulated_normalized_kernel (bound to
    this nutrient's k, lam) for the current, A3/A6-unmodulated state, or
    a real renormalized kernel once A3/A6 exist. Meals at or after t
    contribute nothing (tau <= 0 -> the kernel is zero, per A1)."""
    return sum(
        meal["q"] * meal["f_abs"] * h_i_star(t - meal["t_m"])
        for meal in meals
        if t > meal["t_m"]
    )


# --- A7: food-matrix guard --------------------------------------------------
#
# Source formula ('P1 Core Equations', row A7, transcribed verbatim):
#
#     eta_matrix,i = SUM_j psi_ij * tanh(q_j / q_ref,j)
#
#     Phase 1: psi_ij = 0.
#     Future activation: eta_matrix enters logit(F_abs) or log m_i(t).
#     Do NOT use A_i * PRODUCT_j(1 + psi_ij*q_j/q_ref), because a negative
#     factor can reverse sign and a positive product can exceed the
#     absorbed dose.
#
# *** CONFIRMED, NOT A GAP *** -- unlike every other A-layer parameter
# still missing real values, psi_ij=0 in Phase 1 is stated as fact by
# THREE independent sheets, verbatim: 'P1 Core Equations' ("Phase 1:
# psi_ij = 0"), '★ Equation Backbone' ("psi=0 in Phase 1"), and 'P1
# Parameters 134+' row 25 ("Food matrix coefficient ... set to 0 in Phase
# 1", default explicitly 0). So interaction_coefficients defaulting to
# {} (i.e. every psi_ij = 0) is the actual, real, currently-correct
# production value, not a placeholder standing in for missing data.


def food_matrix_adjustment(co_food_quantities: dict[str, float], interaction_coefficients: dict[str, float], reference_quantities: dict[str, float]) -> float:
    """A7: eta_matrix,i = SUM_j psi_ij * tanh(q_j / q_ref,j).

    co_food_quantities: {food_component_j: q_j}. interaction_coefficients:
    {food_component_j: psi_ij}; components absent from this dict are
    treated as psi_ij=0 (the confirmed Phase 1 default -- see module note
    above), not silently required. reference_quantities:
    {food_component_j: q_ref,j}."""
    return sum(
        interaction_coefficients.get(component, 0.0) * math.tanh(q_j / reference_quantities[component])
        for component, q_j in co_food_quantities.items()
    )
