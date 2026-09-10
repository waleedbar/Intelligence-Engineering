"""ONB-006 — the family-history priors.

Authority: 'O·O6 Family History', equations O6.1-O6.11, via
sahacore/data/onboarding_o6.json.

Onboarding step 6, "Bayesian prior shifts", feeding Layers C, E and O11.

    O6.1   delta_FH        = I(FH) * ln(RR)
    O6.2-7 one per condition: T2D, CVD, stroke, colon, breast, dementia
    O6.8   mu_post         = mu + Sigma_12 * Sigma_22^-1 * (x2 - mu_2)
    O6.9   l = g + e;  P(disease) = Phi((l - threshold)/sigma)
    O6.10  eta_hi_modified = eta_hi * (1 + 0.3 * I(FH_relevant))
    O6.11  sigma2_inflated = sigma2_base * 1.5 if FH positive

ALL ELEVEN ARE IMPLEMENTED, four of them as functions of arguments the sheet
does not supply -- which is the honest form for O6.8 and O6.9. Their
mathematics is standard and complete; what is missing is every input. A
module that invented a covariance block or a liability threshold would be
inventing the prior, so the caller passes them and the gap stays visible.

THE BEST-SOURCED SHEET IN THE BUILD. Every relative risk names its study --
EPIC-InterAct for T2D, an AHA meta-analysis for stroke. No other O-sheet
cites a source for any constant. The risks are read from the registry, never
written here.

WHAT THE SHEET IS CHECKED AGAINST. Each relative risk is stated four times --
inside the formula as ln(RR), again pre-computed, again in the Variables
cell, and again in the reference table -- and the extractor recomputes the
logarithm and holds all four together. Step 6's six checkboxes are then
checked against the six equations in both directions.

O6.11 IS AMBIGUOUS AND IS NOT RESOLVED HERE. "sigma2_base * 1.5 if FH
positive" does not say WHICH family history, and the six are collected
separately. Inflating the whole prior when any one of six checkboxes is
ticked is a different rule from inflating per pathway, and the sheet gives no
way to choose. `variance_inflation` therefore takes an explicit boolean and
refuses to decide. See docs/parameter-gaps.md.
"""
import math
from dataclasses import dataclass

# Written into the formulas by the sheet itself.
_ETA_SENSITIVITY_INCREASE = 0.3    # O6.10
_VARIANCE_INFLATION = 1.5          # O6.11


@dataclass(frozen=True)
class FamilyHistory:
    """Step 6's six checkboxes, keyed by the UI's own variable names."""
    FH_T2D: bool = False
    FH_CVD: bool = False
    FH_stroke: bool = False
    FH_colon: bool = False
    FH_breast: bool = False
    FH_AD: bool = False

    def any_positive(self) -> bool:
        return any((self.FH_T2D, self.FH_CVD, self.FH_stroke,
                    self.FH_colon, self.FH_breast, self.FH_AD))


def log_hazard_shift(present: bool, relative_risk: float) -> float:
    """O6.1. delta_FH = I(FH) * ln(RR).

    The general form. A relative risk of 1 is no shift, and one below 1 would
    make a family history protective -- which the extractor refuses to import.
    """
    if relative_risk <= 0:
        raise ValueError(
            f"relative risk {relative_risk} has no logarithm; O6.1 is "
            "I(FH)*ln(RR).")
    return math.log(relative_risk) if present else 0.0


def condition_shift(indicator: str, present: bool) -> float:
    """O6.2-O6.7. One condition's log-hazard shift, at the sheet's own
    precision.

    Returns the PRE-COMPUTED log the sheet writes ("* 1.000"), not
    ln(relative_risk) recomputed here. The two agree to 1e-3 and the sheet's
    is the one its downstream ranges were written against -- notably T2D,
    where the relative risk is *e* rounded to 2.72 for display, so the stated
    1.000 is exact and ln(2.72) = 1.000632 is the rounded one.
    """
    from sahacore.onboarding.parameters import load_o6_shifts
    return load_o6_shifts()[indicator] if present else 0.0


def all_shifts(history: FamilyHistory) -> dict[str, float]:
    """Every condition's shift for one user, keyed by its FH_ variable."""
    from sahacore.onboarding.parameters import load_o6_shifts
    return {indicator: condition_shift(indicator, getattr(history, indicator))
            for indicator in load_o6_shifts()}


def pearson_aitken_posterior(mu, sigma_12, sigma_22_inverse, x2, mu_2):
    """O6.8. mu_post = mu + Sigma_12 * Sigma_22^-1 * (x2 - mu_2).

    EVERY INPUT IS AN ARGUMENT BECAUSE THE SHEET SUPPLIES NONE OF THEM. There
    is no covariance between family history and the damage states anywhere in
    the workbook, and no population mean vector. Written as scalars here
    because that is all the sheet's notation commits to; a caller with the
    matrices can pass the products.
    """
    return mu + sigma_12 * sigma_22_inverse * (x2 - mu_2)


def _standard_normal_cdf(z: float) -> float:
    """Phi, via the error function -- exact to double precision, no table."""
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def liability(genetic: float, environmental: float) -> float:
    """O6.9's first half: l = g + e."""
    return genetic + environmental


def liability_probability(genetic: float, environmental: float,
                          threshold: float, sigma: float) -> float:
    """O6.9. P(disease) = Phi((l - threshold)/sigma).

    The threshold and sigma are arguments for the same reason as O6.8's
    covariances: the sheet names them and gives neither, for any condition.
    """
    if sigma <= 0:
        raise ValueError(f"sigma is {sigma}; O6.9 divides by it.")
    return _standard_normal_cdf(
        (liability(genetic, environmental) - threshold) / sigma)


def relevant_pathways(history: FamilyHistory) -> frozenset[str]:
    """The Z-pathways a user's family history touches, per O6.10.

    O6.10 says "FH_relevant per pathway" and does not give the mapping. The
    RR reference table does, in its Z-Pathway Affected column, and that is
    the only statement of it in the workbook -- so it is read from there
    rather than assembled here.
    """
    from sahacore.onboarding.parameters import load_o6_pathways
    touched: set[str] = set()
    for indicator, pathways in load_o6_pathways().items():
        if getattr(history, indicator):
            touched.update(pathways)
    return frozenset(touched)


def eta_sensitivity(eta_hi: float, fh_relevant: bool) -> float:
    """O6.10. eta_hi * (1 + 0.3 * I(FH_relevant)) -- a 30% increase, or none.

    Whether a history is relevant to a given pathway is `relevant_pathways`,
    read from the RR table.
    """
    return eta_hi * (1.0 + _ETA_SENSITIVITY_INCREASE * (1.0 if fh_relevant else 0.0))


def variance_inflation(sigma2_base: float, fh_positive: bool) -> float:
    """O6.11. sigma2_base * 1.5 when a family history is positive.

    `fh_positive` IS AN EXPLICIT ARGUMENT, and deliberately not derived from
    a FamilyHistory. The sheet says "if FH positive" without saying which of
    the six, and "any of the six ticked" is a materially different rule from
    "this pathway's own history is ticked" -- one inflates the whole prior
    for a user with a single distant relative, the other does not. Choosing
    would be inventing the prior. See docs/parameter-gaps.md.
    """
    return sigma2_base * (_VARIANCE_INFLATION if fh_positive else 1.0)
