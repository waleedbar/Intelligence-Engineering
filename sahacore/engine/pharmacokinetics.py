"""Layer B: pharmacokinetics, equations B1-B6, in Dr. Ali's v39sEng2
workbook, sheet 'P1 Core Equations'.

*** RESOLVED VERSION CONFLICT ***
Three sheets describe the fast/slow compartment transfer differently:
'P1 Core Equations' (Q/CL notation, dC1/dt = A/V1 - (CL+Q)/V1*C1 + ...),
'P1 MC Engine' section F ("11 HISTORICAL CORRECTIONS LOG": a simpler
k_fs-only update, C_s += k_fs*(Cf-Cs)*dt*(Vf/Vs)), and 'P1 Parameters
134+' (a fuller k_fs/k_cl/k_sf/k_cl_s four-rate-constant model, citing
only Gibaldi & Perrier 1982 with no correction markers).

Per the user's direction to follow the latest version: 'P1 Core
Equations' explicitly frames itself as "SahaCore v32.10.2 corrected
canonical (merged engine)" with its own recent, named fixes on this exact
row (I19: "P0-3: Q/V notation", "P0-4: CL in dL/min"). The MC Engine
entry is filed under a section titled "11 HISTORICAL corrections log" --
i.e. it documents an earlier development stage, not a still-competing
production formula. 'P1 Parameters 134+' cites only a 1982 textbook
reference with no version/correction tag at all. So B1-B6 below are built
to 'P1 Core Equations', Q/CL notation.

The same reasoning applies to the fast/slow volume allometric exponents:
'O·O1 Anthropometrics' (V_f=V_ref*(BW/70)^0.75, V_s=V_s_ref*(BW/70)^0.85)
carries an explicit "[v39l F-AX]" tag -- a v39-era revision -- while 'P1
Parameters 134+' gives exponent 1.0 for both with no such tag. The v39l
exponents are used here.

Source formulas (transcribed verbatim from 'P1 Core Equations'):

    B1: k_el_i = ln(2) / T_half_i
    B2: dC1/dt = A_final(t)/V1 - (CL+Q)/V1*C1 + Q/V1*C2
    B3: dC2/dt = (Q/V2)*C1 - (Q/V2)*C2
    B4: CL = CL_renal + CL_hepatic          (all values in dL/min)
    B5: CL_renal = GFR*f_filtered*(1-f_reabsorbed)
        GFR default = 120 mL/min = 1.2 dL/min, adjusted by eGFR if available
    B6: CL_hepatic = Q_H*E_H
        E_H = (f_u*CL_int) / (Q_H + f_u*CL_int)   (well-stirred model;
        f_u already embedded -- do NOT multiply by f_u again, the v32.3
        double-counting fix)
        Q_H = 0.260*CO; CO = 6.5*(BW/70)^0.75 L/min (ICRP Publication 89, 2003)

*** REAL, CONFIRMED DATA GAPS ***
Q (intercompartmental clearance) and CL_int (intrinsic hepatic clearance)
are per-nutrient PK parameters with no computable formula found anywhere
in the accessible workbook -- genuine gaps, same category as C2/C3's
eta_hi,k. f_filtered/f_reabsorbed (renal handling) and f_u_ref (baseline
unbound fraction) are likewise per-nutrient and not populated for the
full 81-nutrient set (a handful of beverage-specific f_filtered values
exist in 'MERGE·Bev Engine Params', not a general registry). All stay
plain inputs, not hardcoded, not invented.

*** WHAT IS REAL AND USABLE NOW ***
T_half,i (nutrients_81.json's half_life_fast_d/half_life_slow_d, all 81
nutrients) for B1. V_ref=15L/exponent=0.75 (V_f) and V_s_ref=30L/
exponent=0.85 (V_s), both from body weight alone, cited (West et al.
1997; Anderson & Holford 2008) and v39l-tagged. GFR_ref=120 mL/min
(Levey 2009 Ann Intern Med, CKD-EPI standard). CO=6.5*(BW/70)^0.75 L/min
and Q_H=0.260*CO (ICRP Publication 89, 2003). f_u's BMI adjustment
mechanism (O1.8).
"""
import math

# GFR_DEFAULT_DL_PER_MIN: 120 mL/min = 1.2 dL/min, the confirmed
# population default (B5; GFR_ref, Levey 2009 Ann Intern Med, CKD-EPI
# standard) -- kept as a default value, not hardcoded inline, same
# treatment as D_MAX_AU in damage.py.
GFR_DEFAULT_DL_PER_MIN = 1.2


def elimination_rate_constant(t_half_days: float) -> float:
    """B1: k_el = ln(2) / T_half. T_half from nutrients_81.json's
    half_life_fast_d or half_life_slow_d (real for all 81 nutrients)."""
    return math.log(2) / t_half_days


def fast_compartment_volume(body_weight_kg: float, v_ref_l: float = 15.0, exponent: float = 0.75) -> float:
    """O1.1 (feeds B2's V1): V_f = V_ref * (BW/70)^0.75. V_ref=15L and
    exponent=0.75 are the confirmed v39l defaults (West et al. 1997) --
    still explicit parameters, not hardcoded, per project convention."""
    return v_ref_l * (body_weight_kg / 70.0) ** exponent


def slow_compartment_volume(body_weight_kg: float, v_s_ref_l: float = 30.0, exponent: float = 0.85) -> float:
    """O1.2 (feeds B3's V2): V_s = V_s_ref * (BW/70)^0.85. V_s_ref=30L
    and exponent=0.85 are the confirmed v39l defaults (Anderson & Holford
    2008)."""
    return v_s_ref_l * (body_weight_kg / 70.0) ** exponent


def fast_compartment_derivative(a_final: float, v1: float, cl: float, q: float, c1: float, c2: float) -> float:
    """B2: dC1/dt = A_final(t)/V1 - (CL+Q)/V1*C1 + Q/V1*C2. Q
    (intercompartmental clearance) is a genuine, still-missing per-nutrient
    gap (see module docstring) -- plain input, not invented."""
    return a_final / v1 - (cl + q) / v1 * c1 + q / v1 * c2


def slow_compartment_derivative(v2: float, q: float, c1: float, c2: float) -> float:
    """B3: dC2/dt = (Q/V2)*C1 - (Q/V2)*C2."""
    return (q / v2) * c1 - (q / v2) * c2


def total_clearance(cl_renal: float, cl_hepatic: float) -> float:
    """B4: CL = CL_renal + CL_hepatic (dL/min)."""
    return cl_renal + cl_hepatic


def renal_clearance(f_filtered: float, f_reabsorbed: float, gfr_dl_per_min: float = GFR_DEFAULT_DL_PER_MIN) -> float:
    """B5: CL_renal = GFR * f_filtered * (1 - f_reabsorbed). gfr_dl_per_min
    defaults to the confirmed population value (1.2 dL/min = 120 mL/min),
    overridable with a real eGFR when lab data is available, per the
    source's own note. f_filtered/f_reabsorbed stay per-nutrient gaps."""
    return gfr_dl_per_min * f_filtered * (1.0 - f_reabsorbed)


def cardiac_output(body_weight_kg: float, co_ref_l_per_min: float = 6.5, exponent: float = 0.75) -> float:
    """B6 (feeds Q_H): CO = 6.5 * (BW/70)^0.75 L/min (ICRP Publication
    89, 2003) -- the same 0.75 allometric exponent as V_f, different
    reference constant."""
    return co_ref_l_per_min * (body_weight_kg / 70.0) ** exponent


def hepatic_blood_flow(cardiac_output_l_per_min: float, q_h_fraction: float = 0.260) -> float:
    """B6: Q_H = 0.260 * CO (L/min)."""
    return q_h_fraction * cardiac_output_l_per_min


def unbound_fraction(f_u_ref: float, bmi: float) -> float:
    """O1.8 (feeds B6's E_H): f_u = f_u_ref * (1 - 0.1*max(BMI-25,0)/25).
    f_u_ref (the per-nutrient baseline) stays a plain input -- not
    populated for the full 81-nutrient set."""
    return f_u_ref * (1.0 - 0.1 * max(bmi - 25.0, 0.0) / 25.0)


def hepatic_extraction_ratio(f_u: float, cl_int: float, q_h: float) -> float:
    """B6: E_H = (f_u*CL_int) / (Q_H + f_u*CL_int) -- the well-stirred
    model. f_u is ALREADY embedded here; the source explicitly warns
    against multiplying by f_u a second time elsewhere (the v32.3 fix,
    correcting a prior double-counting bug). CL_int stays a genuine,
    still-missing per-nutrient gap."""
    return (f_u * cl_int) / (q_h + f_u * cl_int)


def hepatic_clearance(q_h: float, e_h: float) -> float:
    """B6: CL_hepatic = Q_H * E_H (same units as Q_H)."""
    return q_h * e_h
