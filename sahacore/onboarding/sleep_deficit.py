"""ONB-003 — the sleep prior.

Authority: 'O·O3 Sleep Deficit' (manifest order 73), equations O3.1-O3.8,
via sahacore/data/onboarding_o3.json.

Step 9 of onboarding: hours slept, a quality rating and a consistency answer
become the modifiers Layers C and E start from.

    O3.1  SDS = (7 - sleep_hrs)/7 * quality_factor,
          quality_factor = 1 - (quality_rating - 1)/4
    O3.2  k_inflam_mod = 1 + 0.081 * deficit_hrs
    O3.3  k_IR_sleep   = 1 - 0.045 * deficit_hrs
    O3.4  FSR_mod      = 1 - 0.18 * I(deficit > 1)
    O3.5  sleep_def    = 0 on [7, 9]; min(1,(7-h)/2) below; min(1,(h-9)/2) above
    O3.6  e_sched      = (consistency_score - 1)/3
    O3.7  mu_sleep     = 0.5*sleep_def + 0.3*e_sleepqual + 0.2*e_sched
    O3.8  sleep_minutes = 60 * sleep_hrs

ALL EIGHT ARE IMPLEMENTED. sahacore.data.onboarding_symbols reports no symbol
this sheet uses and the workbook fails to define -- the first O-sheet of the
three for which that is true. O3.7 even defines e_sleepqual inline,
"(5-quality)/4", where O1.9 leaves e_WHtR and e_BMI undefined.

NO PARAMETERS TABLE ON THIS SHEET, so unlike ONB-001 there is nothing here to
read from a registry: every constant lives inside a formula. That is a
property of the source, not a relaxation of the rule. What IS read from the
registry is O3.6's ordinal scale, because a user's answer of "Fairly
consistent" meaning 3 is a decision the sheet made and the module must not
re-make.

TWO DEFINITIONS OF SLEEP SHORTFALL, AND THEY DISAGREE. O3.1's SDS and O3.5's
sleep_def both measure it:

    SDS       is one-sided and SIGNED. At nine hours it is (7-9)/7 = -0.29
              times the quality factor -- negative -- while its declared
              range is 0-1.
    sleep_def is two-sided and clamped: zero across seven to nine hours,
              rising on both sides, never negative.

Both are implemented under their own names and neither is corrected. A
caller that wants "how far from healthy sleep" wants sleep_def; SDS is what
O3.1 defines and what its engine target -- O3.2, O3.3, O3.4 and O11 -- names.
The disagreement is reported in docs/parameter-gaps.md.
"""
from dataclasses import dataclass

# Written into the formulas by the sheet itself.
_TARGET_SLEEP_HOURS = 7.0        # O3.1, O3.2, O3.5's lower edge
_HEALTHY_UPPER_HOURS = 9.0       # O3.5's upper edge
_SLEEP_DEF_SPAN_HOURS = 2.0      # O3.5's divisor on both sides
_QUALITY_LEVELS = 5              # O3.1 and O3.7: ratings run 1..5
_INFLAMMATION_SLOPE = 0.081      # O3.2
_INSULIN_SLOPE = 0.045           # O3.3
_FSR_PENALTY = 0.18              # O3.4
_FSR_DEFICIT_THRESHOLD = 1.0     # O3.4, in hours
_MINUTES_PER_HOUR = 60.0         # O3.8

# O3.7's composite weights, in the sheet's order.
_SLEEP_PRIOR_WEIGHTS = {"deficit": 0.5, "quality": 0.3, "schedule": 0.2}


@dataclass(frozen=True)
class SleepAnswers:
    """One user's Step 9 answers. `consistency_score` is already decoded from
    the ordinal option by O3.6's scale -- see parameters.load_o3_consistency."""
    sleep_hours: float
    quality_rating: float
    consistency_score: float


def deficit_hours(sleep_hours: float) -> float:
    """O3.2's inner term: max(0, 7 - sleep_hrs). One-sided -- sleeping more
    than the target produces no deficit, it produces zero."""
    return max(0.0, _TARGET_SLEEP_HOURS - sleep_hours)


def quality_factor(quality_rating: float) -> float:
    """O3.1's inner term: 1 - (quality_rating - 1)/4. One at the worst
    rating, zero at the best -- so it scales the deficit UP for poor sleep."""
    return 1.0 - (quality_rating - 1.0) / (_QUALITY_LEVELS - 1)


def sleep_deficit_score(answers: SleepAnswers) -> float:
    """O3.1. SDS = (7 - sleep_hrs)/7 * quality_factor.

    NOT clamped, and the sheet's own range of 0-1 does not hold above seven
    hours: at nine hours with the worst quality rating this returns -0.29.
    Left as written; sleep_deficit_index is the two-sided, clamped one.
    """
    return ((_TARGET_SLEEP_HOURS - answers.sleep_hours) / _TARGET_SLEEP_HOURS
            * quality_factor(answers.quality_rating))


def inflammation_modifier(sleep_hours: float) -> float:
    """O3.2. Feeds Layer C's Z3 inflammation rate."""
    return 1.0 + _INFLAMMATION_SLOPE * deficit_hours(sleep_hours)


def insulin_resistance_modifier(sleep_hours: float) -> float:
    """O3.3. Feeds Layer C's Z6. Falls with deficit, so short sleep lowers
    it -- the sheet's declared range is 0.7-1.0."""
    return 1.0 - _INSULIN_SLOPE * deficit_hours(sleep_hours)


def fractional_synthesis_modifier(sleep_hours: float) -> float:
    """O3.4. A step, not a ramp: 0.82 once the deficit passes one hour,
    1.0 below it. Feeds Layer C's Z10 sarcopenia."""
    return (1.0 - _FSR_PENALTY
            if deficit_hours(sleep_hours) > _FSR_DEFICIT_THRESHOLD else 1.0)


def sleep_deficit_index(sleep_hours: float) -> float:
    """O3.5. Two-sided and clamped to [0, 1]: zero across the healthy seven-
    to-nine-hour window, rising on both sides, saturating two hours out."""
    if _TARGET_SLEEP_HOURS <= sleep_hours <= _HEALTHY_UPPER_HOURS:
        return 0.0
    if sleep_hours < _TARGET_SLEEP_HOURS:
        shortfall = _TARGET_SLEEP_HOURS - sleep_hours
    else:
        shortfall = sleep_hours - _HEALTHY_UPPER_HOURS
    return min(1.0, shortfall / _SLEEP_DEF_SPAN_HOURS)


def schedule_consistency_index(consistency_score: float) -> float:
    """O3.6. (score - 1)/3, so the four options map onto [0, 1]."""
    return (consistency_score - 1.0) / 3.0


def sleep_quality_index(quality_rating: float) -> float:
    """e_sleepqual, defined inline by O3.7's own Variables cell as
    (5-quality)/4. Zero at the best rating, one at the worst."""
    return (_QUALITY_LEVELS - quality_rating) / (_QUALITY_LEVELS - 1)


def composite_sleep_prior(answers: SleepAnswers) -> float:
    """O3.7. In [0, 1] whenever its three inputs are, since the weights sum
    to one. Feeds Layer E as a state prior."""
    return (_SLEEP_PRIOR_WEIGHTS["deficit"] * sleep_deficit_index(answers.sleep_hours)
            + _SLEEP_PRIOR_WEIGHTS["quality"] * sleep_quality_index(answers.quality_rating)
            + _SLEEP_PRIOR_WEIGHTS["schedule"] * schedule_consistency_index(
                answers.consistency_score))


def sleep_minutes(sleep_hours: float) -> float:
    """O3.8. The control-vector entry Layer E reads as u_t[sleep_hrs]."""
    return _MINUTES_PER_HOUR * sleep_hours
