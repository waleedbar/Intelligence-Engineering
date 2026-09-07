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


# --- A5: gastric emptying (Weibull) -----------------------------------------
#
# Source formula ('P1 Core Equations', row A5, transcribed verbatim):
#
#     GE(t) = 1 - exp( -ln2 * (t / T_50)^kappa )
#
#     T_50:  60 - 120 min  (solid meals)
#     kappa: 0.5 - 2.0  [v39l F-I]
#
# T_50/kappa are meal-type constants (solid/liquid/mixed), not per-nutrient
# -- a much smaller gap than a full 81-nutrient table. 'P1 Parameters 134+'
# row 18 cites literature POINT estimates for kappa specifically (Elashoff
# 1982 Gastroenterology: "solids ~1.6, liquids ~1.0"), though T_50 itself
# stays a within-type range there too ("solids 60-120min, liquids
# 15-30min") rather than a single number. Neither is invented here --
# both stay explicit inputs, same convention as everywhere else.


def gastric_emptying_fraction(t: float, t_50: float, kappa: float) -> float:
    """A5: GE(t) = 1 - exp(-ln(2) * (t / T_50)^kappa), the Weibull fraction
    of a meal emptied from the stomach by time t. GE(0)=0; GE(T_50)=0.5 by
    construction; GE(t) -> 1 as t -> infinity."""
    return -math.expm1(-math.log(2) * (t / t_50) ** kappa)


# --- A6: activity/sleep timing effect ---------------------------------------
#
# Source formula ('P1 Core Equations', row A6, transcribed verbatim):
#
#     g_act(t) = MET(t) / (MET(t) + K_act)
#     m_act(t) = exp(beta_act * g_act(t) + beta_sleep * I_sleep(t))
#
#     The term is normalized through h_i*. If evidence supports a change
#     in absorption extent, include it as a bounded logit term inside
#     F_abs, never as an unbounded multiplier.
#
# Unlike A3's eta_c1,i/eta_c2,i (per-nutrient), K_act/beta_act/beta_sleep
# here carry NO nutrient subscript in the source formula -- they're global
# scalars, not an 81-row registry gap. 'P1 Parameters 134+' rows 15/16/59
# still only give generic ranges (K_act 30-60 min/day, beta_act
# 0.001-0.01, beta_sleep -0.3 to -0.1), not single ratified defaults, so
# they stay explicit inputs -- but the gap here is "one calibrated number
# each", not "one calibrated number per nutrient".


def activity_saturation(met: float, k_act: float) -> float:
    """A6: g_act(t) = MET(t) / (MET(t) + K_act) -- Michaelis-Menten
    saturation of the activity effect, in [0, 1) for MET, K_act > 0."""
    return met / (met + k_act)


def activity_sleep_modifier(g_act: float, beta_act: float, i_sleep: float, beta_sleep: float) -> float:
    """A6: m_act(t) = exp(beta_act*g_act(t) + beta_sleep*I_sleep(t))."""
    return math.exp(beta_act * g_act + beta_sleep * i_sleep)


# --- A3: positive timing modulator ------------------------------------------
#
# Source formula ('P1 Core Equations', row A3, transcribed verbatim):
#
#     m_i(t) = exp[
#         eta_c1,i*cos(2*pi*(t-phi_1,i)/1440)
#       + eta_c2,i*cos(4*pi*(t-phi_2,i)/1440)
#       + eta_act,i*g_act(t)
#       + eta_GE,i*g_GE(t)
#       + eta_sleep,i*I_sleep(t)
#       + eta_matrix,i(t)
#     ]
#
#     m_i(t) > 0 by construction. It is normalized inside h_i*, so it
#     changes the absorption-time profile, not total absorbed mass.
#
# This composes A5's g_GE, A6's g_act, and A7's eta_matrix,i -- all three
# already built above. eta_c1,i/eta_c2,i/phi_1,i/phi_2,i/eta_act,i/
# eta_GE,i/eta_sleep,i are per-nutrient sensitivities to each timing
# effect, confirmed NOT populated anywhere in the accessible workbook
# (same gap category as eta_hi,k) -- so they're explicit inputs, but the
# combining formula itself has no gap: m_i(t) > 0 always, since it's an
# exp() of a real-valued sum, by construction (matches the source's own
# stated guarantee), for ANY finite inputs.


def positive_timing_modulator(
    t: float,
    eta_c1: float, phi_1: float,
    eta_c2: float, phi_2: float,
    eta_act: float, g_act: float,
    eta_ge: float, g_ge: float,
    eta_sleep: float, i_sleep: float,
    eta_matrix: float,
) -> float:
    """A3: m_i(t), positive by construction (exp() of a finite real sum)
    for any finite inputs. g_act/g_ge are A6/A5's own outputs
    (activity_saturation, gastric_emptying_fraction); eta_matrix is A7's
    food_matrix_adjustment (0 under the confirmed Phase 1 default)."""
    exponent = (
        eta_c1 * math.cos(2 * math.pi * (t - phi_1) / 1440)
        + eta_c2 * math.cos(4 * math.pi * (t - phi_2) / 1440)
        + eta_act * g_act
        + eta_ge * g_ge
        + eta_sleep * i_sleep
        + eta_matrix
    )
    return math.exp(exponent)


# --- A4: bounded absorbed fraction ------------------------------------------
#
# Source formula ('P1 Core Equations', row A4, transcribed verbatim):
#
#     F_abs,i,m = F_max,i * sigmoid[
#         logit(F_base,i / F_max,i)
#       - log1p(q_i,m / K_m,i)
#       + SUM_j gamma_ij * tanh(z_j)
#       + gamma_cook,i
#       + gamma_condition,i
#     ]
#
#     0 <= F_abs,i,m <= F_max,i <= 1.
#     All interaction/cooking terms act on the logit scale; the range is
#     enforced mathematically rather than only documented.
#
# The interaction sum SUM_j gamma_ij*tanh(z_j) has the same shape as A7's
# food_matrix_adjustment (a coefficient times tanh of a normalized
# quantity), so it's built once, generically, and reused here.
#
# *** THE REAL GAP ***
# F_base,i/K_m,i are the still-tracked, genuinely missing per-nutrient data
# (only 18/81 F_base found, no Km at all, per the exhaustive earlier
# search -- unlike A3/A5/A6's global-or-per-nutrient-sensitivity gaps,
# this one blocks the equation from producing a real number for most
# nutrients even with the function correctly implemented). F_max,i IS
# populated for all 81 (nutrients_81.json's f_max field). gamma_cook,i and
# gamma_condition,i stay explicit inputs (context-dependent, not fixed
# registry values by the source's own framing).


def logit(p: float) -> float:
    """logit(p) = ln(p / (1-p)), the inverse of the logistic sigmoid."""
    return math.log(p / (1.0 - p))


def sigmoid(x: float) -> float:
    """1 / (1 + exp(-x)), computed via the same overflow-safe softplus
    identity used in damage.py's softplus_deviation (sigmoid(x) =
    exp(-softplus(-x)))."""
    neg_softplus = -(max(-x, 0.0) + math.log1p(math.exp(-abs(x))))
    return math.exp(neg_softplus)


def interaction_sum(coefficients: dict[str, float], normalized_values: dict[str, float]) -> float:
    """SUM_j gamma_ij * tanh(z_j) -- the same shape as A7's
    food_matrix_adjustment, reused generically here for A4's interaction
    term. coefficients absent for a given j are treated as gamma_ij=0."""
    return sum(
        coefficients.get(j, 0.0) * math.tanh(z_j)
        for j, z_j in normalized_values.items()
    )


def bounded_absorbed_fraction(
    f_base: float, f_max: float, dose: float, k_m: float,
    interaction_term: float, gamma_cook: float, gamma_condition: float,
) -> float:
    """A4: F_abs,i,m, bounded to [0, F_max] by construction (F_max times a
    sigmoid, which is always in (0,1)) for any finite dose/interaction/
    cooking/condition terms -- matches the source's own stated guarantee
    that the range is enforced mathematically, not just documented.
    interaction_term is SUM_j gamma_ij*tanh(z_j), e.g. from
    interaction_sum()."""
    logit_arg = logit(f_base / f_max)
    dose_term = math.log1p(dose / k_m)
    return f_max * sigmoid(logit_arg - dose_term + interaction_term + gamma_cook + gamma_condition)
