"""ONB-001 — anthropometrics.

Authority: 'O·O1 Anthropometrics' (manifest order 71), equations O1.1-O1.10,
via sahacore/data/onboarding_o1.json.

Step 1 of onboarding: height, weight, waist, neck, age and sex become the
biometric quantities Layers A, B, C and E start from.

    O1.1  V_f  = V_ref * (BW/70)^0.75
    O1.2  V_s  = V_s_ref * (BW/70)^0.85
    O1.3  BMI  = BW / height_m^2
    O1.4  WHtR = waist_cm / height_cm
    O1.5  kappa_IR = 1 / (1 + exp(-k_IR*(WHtR - 0.5)))
    O1.6  BMR_male   = 10*BW + 6.25*height_cm - 5*age + 5
          BMR_female = 10*BW + 6.25*height_cm - 5*age - 161
    O1.7  CRP_mult = 1 + 0.3 * max(BMI - 25, 0)
    O1.8  f_u  = f_u_ref * (1 - 0.1 * max(BMI - 25, 0) / 25)
    O1.9  mu_centadip = 0.45*e_waist + 0.30*e_WHtR + 0.20*e_BMI
                        + 0.05*I(neck > 40cm)
    O1.10 e_waist = min(1, max(0, (waist - lo) / (hi - lo)))

and one more the authority sheet does not carry, given identically by
'O · Onboarding Canonical' and 'EQ · Canonical Build Rows':

    BSA = sqrt(height_cm * weight_kg / 3600)          (Mosteller)

WHAT IS AND IS NOT A CONSTANT HERE. The reference weight 70 kg in O1.1/O1.2,
the coefficients of Mifflin-St Jeor, the 0.3 in O1.7, the 0.1 and 25 in O1.8,
the composite weights in O1.9 and Mosteller's 3600 are all written into the
formulas by the sheet itself and are transcribed with them -- changing one
would be changing the equation, not retuning a parameter. Everything the
sheet lists in its PARAMETERS table -- V_ref, V_s_ref, the allometric
exponents, k_IR, the WHtR cutoff, the four waist thresholds, the neck
threshold, the BMI cutoff -- is read from the registry, because those are
values with sources that can move without the equation moving.

V_f AND V_s ARE PRIORS, NOT VOLUMES. The sheet is explicit: V_ref is a
"GENERIC PRIOR ONLY, not a universal physiological plasma volume", and V_s
should use "per-nutrient V_s,i where characterised". Both functions take an
optional reference so a caller with a characterised nutrient can supply it,
and the defaults are the generic priors.
"""
import math
from dataclasses import dataclass

MALE = "male"
FEMALE = "female"
SEXES = (MALE, FEMALE)

# The allometric reference weight, written into O1.1 and O1.2 themselves.
REFERENCE_WEIGHT_KG = 70.0

# Mifflin-St Jeor, O1.6, as the sheet writes it.
_BMR_WEIGHT = 10.0
_BMR_HEIGHT = 6.25
_BMR_AGE = 5.0
_BMR_INTERCEPT = {MALE: 5.0, FEMALE: -161.0}

# O1.7 and O1.8's slopes, and O1.8's normaliser.
_CRP_SLOPE = 0.3
_FU_SLOPE = 0.1
_FU_NORMALISER = 25.0

# O1.9's composite weights, in the sheet's order.
_CENTADIP_WEIGHTS = {"waist": 0.45, "whtr": 0.30, "bmi": 0.20, "neck": 0.05}

# Mosteller's denominator.
_BSA_DENOMINATOR = 3600.0


@dataclass(frozen=True)
class O1Parameters:
    """The PARAMETERS table of 'O·O1 Anthropometrics', as read from the
    registry. Constructed by sahacore.onboarding.parameters.load_o1()."""
    v_ref_l: float
    v_s_ref_l: float
    k_ir: float
    whtr_cutoff: float
    allometric_exponent_v_f: float
    allometric_exponent_v_s: float
    waist_threshold_male_low_cm: float
    waist_threshold_male_high_cm: float
    waist_threshold_female_low_cm: float
    waist_threshold_female_high_cm: float
    neck_threshold_cm: float
    bmi_obesity_threshold: float

    def waist_thresholds(self, sex: str) -> tuple[float, float]:
        if sex == MALE:
            return (self.waist_threshold_male_low_cm,
                    self.waist_threshold_male_high_cm)
        if sex == FEMALE:
            return (self.waist_threshold_female_low_cm,
                    self.waist_threshold_female_high_cm)
        raise ValueError(f"sex must be one of {SEXES}, got {sex!r}")


def fast_compartment_volume(weight_kg: float, p: O1Parameters,
                            v_ref_l: float | None = None) -> float:
    """O1.1. A generic prior on apparent volume, not a measured one."""
    reference = p.v_ref_l if v_ref_l is None else v_ref_l
    return reference * (weight_kg / REFERENCE_WEIGHT_KG) ** p.allometric_exponent_v_f


def slow_compartment_volume(weight_kg: float, p: O1Parameters,
                            v_s_ref_l: float | None = None) -> float:
    """O1.2. Pass v_s_ref_l for a nutrient whose V_s,i is characterised."""
    reference = p.v_s_ref_l if v_s_ref_l is None else v_s_ref_l
    return reference * (weight_kg / REFERENCE_WEIGHT_KG) ** p.allometric_exponent_v_s


def body_mass_index(weight_kg: float, height_cm: float) -> float:
    """O1.3. The sheet writes height in metres; the inputs here are the
    onboarding fields, which 'P1 DataMap' collects in centimetres."""
    height_m = height_cm / 100.0
    return weight_kg / height_m ** 2


def waist_to_height_ratio(waist_cm: float, height_cm: float) -> float:
    """O1.4."""
    return waist_cm / height_cm


def body_surface_area(weight_kg: float, height_cm: float) -> float:
    """Mosteller. Declared by the consolidated ONB-001 rows, not by the
    authority sheet, and consumed by no other O1 equation."""
    return math.sqrt(height_cm * weight_kg / _BSA_DENOMINATOR)


def insulin_resistance_index(whtr: float, p: O1Parameters) -> float:
    """O1.5. Bounded (0, 1) by construction: a logistic centred on the WHtR
    cutoff, which 'Ashwell et al. 2012' puts at 0.5."""
    return 1.0 / (1.0 + math.exp(-p.k_ir * (whtr - p.whtr_cutoff)))


def basal_metabolic_rate(weight_kg: float, height_cm: float, age_years: float,
                         sex: str) -> float:
    """O1.6, Mifflin-St Jeor. The two sexes differ only in the intercept."""
    if sex not in SEXES:
        raise ValueError(f"sex must be one of {SEXES}, got {sex!r}")
    return (_BMR_WEIGHT * weight_kg
            + _BMR_HEIGHT * height_cm
            - _BMR_AGE * age_years
            + _BMR_INTERCEPT[sex])


def crp_multiplier(bmi: float, p: O1Parameters) -> float:
    """O1.7. Exactly 1.0 at or below the obesity threshold -- no amplification
    is the default, and the max() is what guarantees it."""
    return 1.0 + _CRP_SLOPE * max(bmi - p.bmi_obesity_threshold, 0.0)


def unbound_fraction(f_u_ref: float, bmi: float, p: O1Parameters) -> float:
    """O1.8. Per-nutrient: f_u_ref is the nutrient's own reference."""
    excess = max(bmi - p.bmi_obesity_threshold, 0.0)
    return f_u_ref * (1.0 - _FU_SLOPE * excess / _FU_NORMALISER)


def waist_exposure_index(waist_cm: float, sex: str, p: O1Parameters) -> float:
    """O1.10. Clamped to [0, 1] between the sex-specific thresholds."""
    low, high = p.waist_thresholds(sex)
    return min(1.0, max(0.0, (waist_cm - low) / (high - low)))


def central_adiposity_composite(e_waist: float, e_whtr: float, e_bmi: float,
                                neck_cm: float, p: O1Parameters) -> float:
    """O1.9. The three exposure indices are normalised [0, 1] and the neck
    term is an indicator, so the result is in [0, 1] whenever they are."""
    return (_CENTADIP_WEIGHTS["waist"] * e_waist
            + _CENTADIP_WEIGHTS["whtr"] * e_whtr
            + _CENTADIP_WEIGHTS["bmi"] * e_bmi
            + _CENTADIP_WEIGHTS["neck"] * float(neck_cm > p.neck_threshold_cm))
