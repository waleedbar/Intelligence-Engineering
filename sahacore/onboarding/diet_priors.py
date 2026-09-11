"""ONB-007 — the diet-pattern priors, and the 648 means that are missing.

Authority: 'O·O7 Diet Pattern Priors', equations O7.1-O7.4, via
sahacore/data/onboarding_o7.json.

Onboarding step 3, "81-nutrient Normal priors", feeding Layers A, B and E.

    O7.1  C_f(0)_i ~ N(mu_pattern_i, sigma2_pattern_i)
    O7.2  sigma2_post = 1 / (1/sigma2_prior + k/sigma2_obs)
    O7.3  days 1-7 the prior dominates; day 14+ the food logs do
    O7.4  DQI = (fruit_serv + veg_serv) / 10

THIS MODULE CANNOT DO WHAT THE SHEET IS FOR, and says so rather than
improvising. O7.1's engine target is "Layer E: x_hat(0)[1..81]" -- the
starting value of every nutrient the engine tracks, 81 of its 219 states. It
needs a MEAN per nutrient per pattern: 8 x 81 = 648 numbers. The workbook
supplies none of them.

What it supplies instead is prose, one line per pattern: "High omega-3, olive
oil, fiber", "B12, Iron (heme), Zinc, Omega-3". Useful to a dietitian,
uncomputable by anything.

THE VARIANCE HALF IS NOT MISSING, AND AN EARLIER VERSION OF THIS MODULE SAID
IT WAS. It claimed 8 x 81 x 2 = 1,296 absent numbers. The variance is
supplied -- by 'O·O12-O14 State Init', O13.2, which is a different module:

    "PK state variances | sigma^2 = (0.3-0.5)^2 per typed nutrient/exposure
     prior unless a stronger source exists | [1..162] | 81 fast + 81 slow"

One rule for all 162 PK states, not one number per pattern per nutrient --
the width of a prior is a state-initialisation concern and the workbook
assigns it to O13, never to O7. It still leaves a choice inside 0.3-0.5, and
it arrives here only when ONB-012-014 are imported.

HOW THE MISS HAPPENED, because the lesson generalises: the search that
concluded "none of them" looked for the SYMBOLS `mu_pattern` and
`sigma2_pattern`, which do appear only on this sheet and its duplicate at
'P1 Onboarding' row 328. O13.2 supplies the same QUANTITY under a different
name, in another module, so a symbol search could not see it. Searching for a
name answers "is this name used elsewhere", not "is this number known".

The mean survives that correction: it was searched for as a quantity too --
all 205 sheets scanned for the eight pattern names, and the only two carrying
anything are this sheet and its duplicate, both qualitative; the 81-nutrient
registry has kinetics and no baseline-intake column; '★ Target Registry' has
6 DRI targets of 81, which are what a person should get rather than what a
pattern supplies.

So `nutrient_prior` REFUSES rather than returning a made-up number. Returning
zero, or a population average, would put an invented initial condition into
81 states and nothing downstream would ever know. See docs/parameter-gaps.md.

WHAT IS BUILT: O7.2's precision-weighted update, O7.3's crossover as the
sheet states it, O7.4's index, and the eight-pattern catalogue -- which is
worth having on its own, because comparing it against the interface is what
turned up the finding below.

THE INTERFACE OFFERS A PATTERN THE SHEET HAS NEVER HEARD OF. Step 3 lists
six options; this sheet describes eight; 'P1 DataMap' row 125 says "Radio (8
options)". The sheet's own UI Label column marks DASH and Carnivore "Not in
current UI" -- it knows about those. Nothing anywhere mentions that the
interface also offers **Intermittent Fasting**, which has no row here, no
nutrient shift and no prior. A user selecting it gets no O7 prior.

BUT IT IS NOT UNMODELLED, AND THIS MODULE USED TO SAY IT WAS. The engine
tracks intermittent fasting in several places, none of them O7:

    state 207    fasting_state, "hours since last meal"
    state 208    fasting_pattern, "fasting pattern regularity"
    action 125   "Intermittent fasting 14-16h window"
    action 126   "Time-restricted eating (8-10h window)"

-- two of the canonical 219 states and two of the 127 bandit arms, plus
'04 Data & Registries' naming the "intermittent-fasting window" as one of the
lifestyle block's 12 pairs. So the real finding is narrower and sharper than
"the engine does not model it": intermittent fasting is a question of WHEN a
person eats, the other seven options are questions of WHAT they eat, and
Step 3 asks for both with one radio button. The fix is a UI question, not a
missing model -- and O7 giving it no prior is correct behaviour, because a
fasting window is not a nutrient composition.

O7.4'S SERVING BANDS, AND WHY THE ENCODING IS A CHOICE RATHER THAN AN
OVERSIGHT. Step 3 asks for fruit and vegetable servings as '0 / 1-2 / 3-4 /
5+'. The workbook encodes that EXACT band set twice, differently:

    O2 (sessions/wk)    1-2 -> 1.5    3-4 -> 3.5    5+ -> 5.5   "Midpoint"
    O5.5 (SSB servings) 1-2 -> 0.5    3-4 -> 1.75   5+ -> 3

and gives no encoding at all for fruit or vegetables. Two incompatible
answers already exist for the same question, so picking one here would be
choosing between the sheet's own authors. `diet_quality_index` takes
servings, not a band.
"""
from dataclasses import dataclass

# O7.4's divisor, written into the formula by the sheet.
_DQI_DIVISOR = 10.0

# O7.3's two stated edges, in days of food logging.
_PRIOR_DOMINATES_THROUGH_DAY = 7
_LOGS_DOMINATE_FROM_DAY = 14


class PriorNotSupplied(LookupError):
    """Raised because the workbook does not contain the number asked for.

    A distinct type so a caller cannot mistake it for a typo in a nutrient
    id, and so that the day this is fixed the fix is greppable.
    """


@dataclass(frozen=True)
class DietPattern:
    """One of the sheet's eight patterns, as described rather than measured."""
    pattern: str
    key_nutrient_shifts: str
    typical_deficiencies: str
    ui_label: str
    ui_status: str


def patterns() -> tuple[DietPattern, ...]:
    """The eight dietary patterns, in the sheet's order."""
    from sahacore.onboarding.parameters import load_o7_patterns
    return tuple(DietPattern(**row) for row in load_o7_patterns())


def pattern_for_ui_option(option: str) -> DietPattern:
    """The pattern whose declared UI label is exactly this option.

    EXACT, deliberately. 'Mediterranean Diet' plainly means the interface's
    'Mediterranean' and 'Low-carb/Ketogenic' its 'Low-carb/Keto' -- and
    matching on "plainly means" is the move this repo refuses, the same one
    refused for f_u_ref and for standing_hrs. Those two are bridges for the
    sheet's author to declare.
    """
    for pattern in patterns():
        if pattern.ui_label == option:
            return pattern
    raise PriorNotSupplied(
        f"no dietary pattern declares the UI label {option!r}. The interface "
        "offers six options and the sheet describes eight, and they do not "
        "line up -- see docs/parameter-gaps.md.")


def nutrient_prior(pattern: str, nutrient_id: str) -> tuple[float, float]:
    """O7.1. The (mean, variance) this nutrient starts at under this pattern.

    ALWAYS RAISES, on the mean. The sheet states the distribution and gives no
    mu_pattern for any of the 81 nutrients under any of the 8 patterns.

    It raises even though the variance IS obtainable -- O13.2's
    sigma^2 = (0.3-0.5)^2 -- because a distribution with a known width and an
    unknown centre is not a usable prior, and returning half of one would let
    a caller believe it had a prior. The variance is not returned separately
    here either: it belongs to O13, and this module would be the wrong place
    to learn it from.

    This is not a stub awaiting code -- the code is one line. It is a
    deliberate refusal to invent 648 numbers that would become the initial
    condition of 81 of the engine's 219 states, with nothing downstream able
    to tell they were guessed.
    """
    raise PriorNotSupplied(
        f"O7.1 gives no mu_pattern for nutrient {nutrient_id!r} under pattern "
        f"{pattern!r}, and neither does any other sheet in the workbook: "
        "8 patterns x 81 nutrients = 648 means, none of them written down. "
        "(The variance is not the gap -- 'O·O12-O14 State Init' O13.2 gives "
        "sigma^2 = (0.3-0.5)^2 for states [1..162].) See "
        "docs/parameter-gaps.md.")


def posterior_variance(sigma2_prior: float, sigma2_obs: float,
                       observation_days: int) -> float:
    """O7.2. sigma2_post = 1 / (1/sigma2_prior + k/sigma2_obs).

    Precision-weighted, and correct as written: precisions add, and each day
    of food logging contributes one more unit of observation precision. It
    needs no missing constants -- only the two variances the caller has, and
    the day count.

    Note that sigma2_prior is exactly what O7.1 fails to supply. So this
    function is buildable and, until the priors arrive, not callable with a
    real prior.
    """
    if sigma2_prior <= 0 or sigma2_obs <= 0:
        raise ValueError(
            f"variances must be positive; got prior={sigma2_prior}, "
            f"observed={sigma2_obs}.")
    if observation_days < 0:
        raise ValueError(f"observation_days is {observation_days}.")
    return 1.0 / (1.0 / sigma2_prior + observation_days / sigma2_obs)


def prior_weight(sigma2_prior: float, sigma2_obs: float,
                 observation_days: int) -> float:
    """How much of the posterior precision still comes from the prior, 0-1.

    Not an equation on the sheet -- it is O7.2 rearranged, and it is what
    makes O7.3's claim checkable rather than decorative. At k = 0 it is 1;
    it falls monotonically as days accumulate.
    """
    prior_precision = 1.0 / sigma2_prior
    total = prior_precision + observation_days / sigma2_obs
    return prior_precision / total


def dominant_source(observation_days: int) -> str:
    """O7.3, as the sheet states it: 'prior', 'logs', or 'transition'.

    The sheet gives day 7 and day 14 as edges and says nothing about the days
    between, so they are named rather than assigned to one side. Which source
    actually dominates depends on the ratio of the two variances, and O7.1
    supplies neither -- so this reports the sheet's SCHEDULE, not a
    computation. `prior_weight` is the computation.
    """
    if observation_days < 0:
        raise ValueError(f"observation_days is {observation_days}.")
    if observation_days <= _PRIOR_DOMINATES_THROUGH_DAY:
        return "prior"
    if observation_days >= _LOGS_DOMINATE_FROM_DAY:
        return "logs"
    return "transition"


def diet_quality_index(fruit_servings: float, veg_servings: float) -> float:
    """O7.4. DQI = (fruit_serv + veg_serv) / 10, feeding O11's Z5.

    THE SERVING COUNTS ARE NUMBERS AND THE INTERFACE COLLECTS BANDS. Step 3
    asks for fruit and vegetable servings as '0 / 1-2 / 3-4 / 5+', and no
    sheet in the workbook says what those bands are worth -- O5.2 gives
    midpoints for alcohol and O5.5 gives (wrong) ones for sugary drinks, and
    nothing gives any for fruit or vegetables.

    So this takes servings, not a band, and the caller supplies the
    conversion the sheet declines to. Not clamped: the declared range is 0-1
    and whether it holds depends entirely on that missing encoding.
    """
    return (fruit_servings + veg_servings) / _DQI_DIVISOR
