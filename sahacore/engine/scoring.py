"""Layer D: scoring and alerting, equations D1 (Disruption Score) and D2
(Traffic Light) in Dr. Ali's v39sEng2 workbook, sheet 'P1 Core Equations'.

Source formulas (transcribed verbatim):

    D1: D_k = 100 / (1 + exp(-(a_k * ln(1 + Z_k) + b_k)))

    D2: Score_k = 100 - D_k   (D_k is internal only; Score_k is what's shown)
        Color_k, in SCORE space (higher is better):
          GOOD GREEN  #5FC79A  >= 80  (Optimal)
          DEEP TEAL   #325356  60-79  (Build)
          AMBER       #E0A05A  40-59  (Focus)
          WARM CORAL  #E8735A  < 40   (Reach Out -- supportive coral, NEVER red)

Z_k (total damage for cluster k) is C4's output; Layer C isn't fully built
yet (C2-C4 need cluster-level persistence parameters not yet confirmed --
tracked separately), so z_k is a plain input here, same pattern as
combined_concentration's Cbar_i in sahacore/engine/damage.py. a_k and b_k
come from cluster_scoring_params_12.json, which IS fully populated and
verified for all 12 clusters (unlike the Layer A/B gap) -- see
tests/test_layer_c_d_registries.py.

The source explicitly flags the D-Q1 governance rule this module must
respect: the low band is coral, never red, and its label is "Reach Out",
never a clinical term -- both were historical defects (v35.9) it corrects.
"""
import math

# GOOD GREEN / DEEP TEAL / AMBER / WARM CORAL, exact hex codes and score
# cutoffs from D2. Never rename WARM CORAL to red or its label away from
# "Reach Out" -- that's the specific defect D2 documents as corrected.
BANDS = (
    ("Optimal", "#5FC79A", 80.0),
    ("Build", "#325356", 60.0),
    ("Focus", "#E0A05A", 40.0),
    ("Reach Out", "#E8735A", float("-inf")),
)


def disruption_score(z_k: float, a_k: float, b_k: float) -> float:
    """D1: D_k = 100 / (1 + exp(-(a_k * ln(1+Z_k) + b_k))). Bounded to
    (0, 100) for any finite z_k >= 0 by construction (sigmoid)."""
    return 100.0 / (1.0 + math.exp(-(a_k * math.log1p(z_k) + b_k)))


def wellness_score(d_k: float) -> float:
    """D2: Score_k = 100 - D_k. D_k stays internal; Score_k is displayed."""
    return 100.0 - d_k


def band_for_score(score: float) -> tuple[str, str]:
    """D2's traffic light: returns (label, hex_color) for a Score_k in
    SCORE space (already 100 - D_k). Bands are score >= 80 / 60 / 40,
    lowest band inclusive of everything below 40."""
    for label, color, cutoff in BANDS:
        if score >= cutoff:
            return label, color
    raise AssertionError("unreachable: BANDS' last cutoff is -inf")
