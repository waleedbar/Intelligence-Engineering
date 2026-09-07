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


def exact_scarring_update(s_prev: float, alpha_scar_k: float, beta_k: float, over_k: float, dt_day: float) -> float:
    """M1x: S_next for one exact time step of piecewise-constant over_k.

    q = a + beta_k is zero only when both alpha_scar_k*over_k and beta_k
    are zero (no forcing, no clearance) -- dS/dt = 0 identically in that
    case, so S is unchanged; that degenerate branch is handled explicitly
    rather than dividing by zero."""
    a = alpha_scar_k * over_k
    q = a + beta_k
    if q == 0.0:
        return s_prev
    s_inf = a / q
    return s_inf + (s_prev - s_inf) * math.exp(-q * dt_day)


def effective_repair_capacity(v_max_base: float, gamma_scar_k: float, s_k: float) -> float:
    """M2: V_max,k^eff = V_max,k^base * exp(-gamma_scar,k * S_k) -- the
    multiplicative repair-capacity penalty from accumulated scarring
    (S_k=0 -> no penalty; higher S_k -> repair.py's competitive_repair_rate
    should be driven with this reduced V_max instead of the base value)."""
    return v_max_base * math.exp(-gamma_scar_k * s_k)
