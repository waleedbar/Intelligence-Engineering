"""ONB-005 — the substance-exposure priors.

Authority: 'O·O5 Substance Exposure', equations O5.1-O5.7, via
sahacore/data/onboarding_o5.json.

Onboarding steps 3 (sugary drinks) and 10 (tobacco, alcohol), feeding
Layers C and E.

    O5.1  lambda_smoke   = 1 + 0.02 * pack_years
    O5.2  lambda_alcohol = 1 + 0.01 * units_week
    O5.3  k_ox           = lambda_smoke * lambda_alcohol
    O5.4  GSH_depletion  = 0.8 * I(drinks_wk >= 8)
    O5.5  e_SSB          = min(1, SSB_serv_day / 1.5)
    O5.6  e_alcohol      = min(1, max(0, (drinks_wk - T)/T)), T = 7 F / 14 M
    O5.7  tobacco_idx    : Never=0 ... Daily=1.0

ALL SEVEN ARE IMPLEMENTED.

FOUR ENCODINGS, ALL READ FROM THE REGISTRY. This sheet turns an answer into
a number four times -- pack_years, units_week, tobacco_idx and O5.5's SSB
midpoints -- and every one of those mappings is the sheet's judgement about
what an answer is worth. None is written here.

TWO ALCOHOL QUANTITIES, DELIBERATELY NOT BRIDGED. O5.2 reads `units_week`,
described as "from Step 10 UI midpoints". O5.4 and O5.6 read `drinks_wk`.
The UI asks about alcohol exactly once, so they are almost certainly the same
answer -- but the sheet never says so, and bridging two names on a
resemblance is what build_eq_param_fk.ALIASES exists to stop. So the caller
supplies each explicitly and `SubstanceAnswers` keeps them apart.

That non-bridge is also what makes the finding visible rather than baked in:

  IF the two are the same answer, `drinks_wk` cannot exceed units_week's
  largest encoded value, 10, and O5.6's male branch -- min(1, max(0,
  (drinks_wk - 14)/14)) -- is zero for every answer the UI accepts. A female
  tops out at 0.43. Both are declared 0-1.

THREE MORE FINDINGS, none corrected, all in docs/parameter-gaps.md.

  O5.5's "midpoints" are not the midpoints of Step 3's bands. It declares
  0/0.5/1.75/3 against bands 0 / 1-2 / 3-4 / 5+, whose midpoints are
  0/1.5/3.5. O5.2's alcohol midpoints ARE exact, so the sheet knows how.
  A user answering "1-2 sugary drinks a day" scores e_SSB = 0.333, not 1.0.

  The five smoking categories are not what the UI collects. Step 10 asks
  smoke_status (Yes daily / Yes occasionally / No) and quit_time, and
  neither offers "Former". The five must be a join of two answers, and no
  sheet gives the rule -- so this module takes the joined category and
  cannot perform the join.

  O5.1 and O5.7 rank those five differently. pack_years ties Former(<1yr)
  with Occasional at 5; tobacco_idx separates them, 0.35 against 0.5.
"""
from dataclasses import dataclass

# Written into the formulas by the sheet itself.
_SMOKE_SLOPE = 0.02              # O5.1
_ALCOHOL_SLOPE = 0.01            # O5.2
_GSH_PENALTY = 0.8               # O5.4
_GSH_DRINKS_THRESHOLD = 8        # O5.4
_SSB_DIVISOR = 1.5               # O5.5
_ALCOHOL_THRESHOLDS = {"Female": 7, "Male": 14}    # O5.6


@dataclass(frozen=True)
class SubstanceAnswers:
    """One user's Step 3 and Step 10 answers.

    `smoke_status` is one of the sheet's five joined categories, not a raw
    UI answer -- see the module docstring. `alcohol_band` is the UI's band
    label ('4-7'); `drinks_wk` is the number O5.4 and O5.6 read, kept
    separate because the sheet never bridges the two. `ssb_band_position` is
    1-based, because O5.5's midpoints carry no labels to key them by.
    """
    smoke_status: str
    alcohol_band: str
    drinks_wk: float
    ssb_band_position: int
    sex: str


# --- the four encodings, each read rather than written --------------------

def pack_years(smoke_status: str) -> float:
    """O5.1's inner term. What a smoking answer is worth in pack-years.

    NOTE the sheet's own Variables cell says "pack_years estimated from
    status + age", and the encoding it gives depends on status ALONE -- age
    appears nowhere in it. Read as written.
    """
    from sahacore.onboarding.parameters import load_o5_encoding
    return load_o5_encoding("pack_years")[smoke_status]


def tobacco_index(smoke_status: str) -> float:
    """O5.7. The same answer as pack_years, on a different scale and with a
    different ranking -- it separates Former(<1yr) from Occasional where
    pack_years ties them."""
    from sahacore.onboarding.parameters import load_o5_encoding
    return load_o5_encoding("tobacco_idx")[smoke_status]


def units_week(alcohol_band: str) -> float:
    """O5.2's inner term: the UI band's midpoint. These are exact midpoints
    of Step 10's bands, which is what makes O5.5's SSB values a discrepancy
    rather than a convention."""
    from sahacore.onboarding.parameters import load_o5_encoding
    return load_o5_encoding("units_week")[alcohol_band]


def ssb_servings(band_position: int) -> float:
    """O5.5's inner term, addressed by position because it has no labels.

    The sheet calls these midpoints and they are not the midpoints of Step
    3's bands. Read as written; see docs/parameter-gaps.md.
    """
    from sahacore.onboarding.parameters import load_o5_ssb_midpoints
    midpoints = load_o5_ssb_midpoints()
    if not 1 <= band_position <= len(midpoints):
        raise ValueError(
            f"SSB band position {band_position} is outside 1..{len(midpoints)}.")
    return midpoints[band_position - 1]


# --- the equations --------------------------------------------------------

def tobacco_exposure_index(smoke_status: str) -> float:
    """O5.1. lambda_smoke, feeding Layer C's Z2 oxidative DNA damage."""
    return 1.0 + _SMOKE_SLOPE * pack_years(smoke_status)


def alcohol_exposure_index(weekly_units: float) -> float:
    """O5.2. lambda_alcohol, feeding Layer C's Z8 hepatic fibrosis."""
    return 1.0 + _ALCOHOL_SLOPE * weekly_units


def oxidative_rate_constant(smoke_status: str, weekly_units: float) -> float:
    """O5.3. k_ox = lambda_smoke * lambda_alcohol.

    Multiplicative, so its ceiling is the product of the two ceilings --
    1.4 * 1.1 = 1.54 -- and the sheet declares "1.0-1.5+".
    """
    return (tobacco_exposure_index(smoke_status)
            * alcohol_exposure_index(weekly_units))


def gsh_depletion_factor(drinks_wk: float) -> float:
    """O5.4. A step, not a ramp: 0.8 at eight drinks a week or more, else 0.
    Feeds Layer C's GSH QSSA modifier."""
    return _GSH_PENALTY if drinks_wk >= _GSH_DRINKS_THRESHOLD else 0.0


def ssb_exposure_index(ssb_serv_day: float) -> float:
    """O5.5. e_SSB = min(1, SSB_serv_day / 1.5), feeding O11's Z1 glycation.

    Saturates at 1.5 servings a day, so the encoding's top two values both
    reach 1.0 and only the second band's value distinguishes anything.
    """
    return min(1.0, ssb_serv_day / _SSB_DIVISOR)


def alcohol_sex_index(drinks_wk: float, sex: str) -> float:
    """O5.6. Sex-specific, feeding O11's Z8 hepatic fibrosis.

    The threshold doubles for males, so the male branch needs 28 drinks a
    week to reach 1.0 and more than 14 to leave zero. If drinks_wk is the
    same answer as units_week -- which the UI implies and the sheet never
    states -- neither is attainable. Implemented as written.
    """
    if sex not in _ALCOHOL_THRESHOLDS:
        raise KeyError(
            f"sex is {sex!r}; O5.6 gives thresholds only for "
            f"{sorted(_ALCOHOL_THRESHOLDS)}.")
    threshold = _ALCOHOL_THRESHOLDS[sex]
    return min(1.0, max(0.0, (drinks_wk - threshold) / threshold))
