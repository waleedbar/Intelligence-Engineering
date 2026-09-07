"""QSSA molecular layer: the ATP branch, in Dr. Ali's v39sEng2 workbook,
sheet 'P1 QSSA ATP-GSH-NAD'.

'QSSA-ATP INTERNAL: mechanistic ATP-flux surrogate -> production output
f_ATP_supply' (transcribed verbatim):

    J_ATP = SUM_i (Vmax_i * [S_i] / (Km_i + [S_i])) * f_cofactor * f_activity

    f_cofactor = min(
        CoQ10/(CoQ10+Km_CoQ10), Mg2+/(Mg2+ + Km_Mg), Fe2+/(Fe2+ + Km_Fe)
    )   -- in [0,1]
    f_activity = MR_adj / BMR

    f_ATP_supply = clip(J_ATP_raw / J_ATP_ref(context), 0, 1)

This is production output the source explicitly says feeds C6's repair
through "bounded f_ATP_supply only" (never the raw flux): repair.py's
docstring already carries a forward note that production Vm there is
really V_max_eff = Vm*exp(-gamma_scar*S)*f_ATP*f_NAD, with f_ATP coming
from here. Not wired into repair.py yet -- this module just makes f_ATP
computable; the wiring is a separate step once f_NAD (needs an implicit
steady-state root-solve, unlike this closed-form branch) exists too.

*** WHAT'S REAL VS. A GAP ***
The 5-complex Km/Vmax table (mitochondrial electron transport chain,
Complex I-V) IS real, individually literature-cited data (Hirst 2013,
Quinlan 2012, Degli Esposti & Lenaz 1982, Orii & Miki 1982, Reynafarje &
Pedersen 1996) -- see qssa_atp_complexes_5.json. mitochondrial_flux_sum
below is fully real, no gap.

Km_CoQ10 / Km_Mg / Km_Fe (f_cofactor's own half-saturation constants) are
NOT found anywhere in the accessible workbook -- a genuine data gap, same
category as C2/C3's eta_hi,k. J_ATP_ref(context) is not a gap in that
sense at all: the source states outright "No universal reference constant
... must be population/context calibrated and versioned by age, sex,
activity and relevant measured anchors" -- it is *defined* to require
external calibration, not something this workbook was ever going to
contain. Both stay plain inputs.
"""


def mitochondrial_flux_sum(substrate_concentrations: dict[str, float], complexes: list[dict]) -> float:
    """SUM_i Vmax_i * [S_i] / (Km_i + [S_i]) across the 5 electron-transport
    complexes. substrate_concentrations: {complex_id: [S_i] in uM}.
    complexes: qssa_atp_complexes_5.json's rows (complex_id, km_um,
    vmax_relative)."""
    total = 0.0
    for complex_row in complexes:
        cid = complex_row["complex_id"]
        s_i = substrate_concentrations[cid]
        km_i = complex_row["km_um"]
        vmax_i = complex_row["vmax_relative"]
        total += vmax_i * s_i / (km_i + s_i)
    return total


def cofactor_support_factor(
    coq10: float, km_coq10: float, mg: float, km_mg: float, fe: float, km_fe: float,
) -> float:
    """f_cofactor = min(CoQ10/(CoQ10+Km_CoQ10), Mg2+/(Mg2+ + Km_Mg),
    Fe2+/(Fe2+ + Km_Fe)) -- each term in [0,1] by construction (a
    nonnegative concentration over itself plus a positive Km), so the min
    is too."""
    coq10_term = coq10 / (coq10 + km_coq10)
    mg_term = mg / (mg + km_mg)
    fe_term = fe / (fe + km_fe)
    return min(coq10_term, mg_term, fe_term)


def activity_factor(mr_adj: float, bmr: float) -> float:
    """f_activity = MR_adj / BMR."""
    return mr_adj / bmr


def j_atp_raw(flux_sum: float, f_cofactor: float, f_activity: float) -> float:
    """J_ATP = (mitochondrial flux sum) * f_cofactor * f_activity."""
    return flux_sum * f_cofactor * f_activity


def atp_supply_fraction(j_atp_raw_value: float, j_atp_ref: float) -> float:
    """f_ATP_supply = clip(J_ATP_raw / J_ATP_ref(context), 0, 1) -- the
    bounded, production-safe output. j_atp_ref is context-calibrated (age,
    sex, activity, measured anchors), not a fixed constant -- see module
    docstring."""
    return max(0.0, min(1.0, j_atp_raw_value / j_atp_ref))
