"""ONB-002 — the physical-activity prior.

Authority: 'O·O2 MVPA Prior' (manifest order 72) and 'P1 Activities 50'
(order 46), via onboarding_o2.json and activities_50.json.

Step 2 of onboarding: how often and how long the user moves becomes weekly
MVPA, MET-minutes, a deficit index and a sedentary penalty.

    O2.1  MVPA_wk    = (f_mod * dur) + 2 * (f_vig * dur)
    O2.2  MVPA_day   = MVPA_wk / 7
    O2.3  e_MVPA     = 1 - min(1, MVPA_wk / 300)
    O2.6  METmin_wk  = 4.5*(f_mod*dur) + 7.5*(f_vig*dur)
    O2.7  METmin_day = METmin_wk / 7
    O2.8  eta_sed    = I(sitting_hrs > 6) * 0.15

SIX OF THE EIGHT. O2.4 (PA_benefit) and O2.5 (rho_modified) are not here,
and not because they were skipped: O2.4 needs HR_Arem, which the sheet
describes and never gives, and the two consolidated sheets define PA_benefit
by a different formula whose own constant K_PA is equally absent. O2.5 needs
O2.4's output and rho_pop, which is in neither parameter registry. Writing
either would mean inventing a dose-response curve, and PA_benefit feeds
Layer C's repair rate -- so it would not stay contained. The gap is carried
in the registry as `computable = false` with the missing symbol named.

THE ORDINAL ENCODING IS READ, NOT RETYPED. "Frequency: 3-4" means 3.5
sessions a week and "Duration: <30 min" means 20 minutes -- the sheet's
"Conservative midpoint", not the arithmetic one. Those choices decide what a
user's answer means, so they live in the registry with the sheet's own
reason attached.

WHY O2.1 AND O2.6 ARE BOTH HERE. They weight vigorous activity differently
and on purpose: O2.1 doubles vigorous minutes, the WHO convention for
"MVPA-equivalent minutes", while O2.6 weights by MET -- 4.5 for moderate and
7.5 for vigorous, a ratio of 1.67. Neither is a rounding of the other, and a
caller that needs one must not take the other.
"""
import math
from dataclasses import dataclass

# Written into the formulas by the sheet itself, not parameters.
_VIGOROUS_MVPA_WEIGHT = 2.0          # O2.1
_MODERATE_MET = 4.5                  # O2.6
_VIGOROUS_MET = 7.5                  # O2.6
_DAYS_PER_WEEK = 7.0                 # O2.2, O2.7

# O2.3's denominator, which the sheet annotates "300 = WHO upper target".
_WHO_UPPER_TARGET_MIN_WK = 300.0

# O2.8's threshold and magnitude, both stated in the formula.
_SITTING_HOURS_THRESHOLD = 6.0
_SEDENTARY_PENALTY = 0.15


@dataclass(frozen=True)
class ActivityAnswers:
    """One user's Step 2 answers, already decoded from the ordinal options
    by O2Encoding.decode()."""
    moderate_sessions_per_week: float
    vigorous_sessions_per_week: float
    minutes_per_session: float
    sitting_hours_per_day: float


def mvpa_minutes_per_week(answers: ActivityAnswers) -> float:
    """O2.1. Vigorous minutes count double -- the WHO MVPA-equivalent."""
    return (answers.moderate_sessions_per_week * answers.minutes_per_session
            + _VIGOROUS_MVPA_WEIGHT * answers.vigorous_sessions_per_week
            * answers.minutes_per_session)


def mvpa_minutes_per_day(mvpa_wk: float) -> float:
    """O2.2."""
    return mvpa_wk / _DAYS_PER_WEEK


def mvpa_deficit_index(mvpa_wk: float) -> float:
    """O2.3. 1 at no activity, 0 once the WHO upper target is met, and
    clamped there -- more than 300 min/wk does not produce a negative
    deficit."""
    return 1.0 - min(1.0, mvpa_wk / _WHO_UPPER_TARGET_MIN_WK)


def met_minutes_per_week(answers: ActivityAnswers) -> float:
    """O2.6. MET-weighted, unlike O2.1."""
    return (_MODERATE_MET * answers.moderate_sessions_per_week
            * answers.minutes_per_session
            + _VIGOROUS_MET * answers.vigorous_sessions_per_week
            * answers.minutes_per_session)


def met_minutes_per_day(metmin_wk: float) -> float:
    """O2.7."""
    return metmin_wk / _DAYS_PER_WEEK


def sedentary_penalty(sitting_hours_per_day: float) -> float:
    """O2.8. A step, not a ramp: strictly more than six hours."""
    return (_SEDENTARY_PENALTY
            if sitting_hours_per_day > _SITTING_HOURS_THRESHOLD else 0.0)


def met_minutes_from_bouts(bouts: list[tuple[str, float]],
                           catalogue: dict[str, float]) -> float:
    """MET_min_week = Sigma_bouts MET_a * minutes_a.

    The form 'O · Onboarding Canonical' gives for ONB-002, for a user whose
    activities are known individually rather than as a moderate/vigorous
    split. `catalogue` maps activity id to MET, from 'P1 Activities 50'.

    Kept separate from O2.6 rather than replacing it: O2.6 is what the
    onboarding screen's four frequency options and three duration options can
    produce, and this is what a wearable history can. An unknown activity is
    an error, not a zero -- silently dropping a bout would understate
    activity, which biases the deficit index the wrong way.
    """
    total = 0.0
    for activity_id, minutes in bouts:
        if activity_id not in catalogue:
            raise KeyError(
                f"{activity_id!r} is not in the 50-activity catalogue; "
                "MET is unknown, and a dropped bout would understate activity")
        total += catalogue[activity_id] * minutes
    return total
