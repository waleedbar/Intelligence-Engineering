"""ONB-004 — the stress prior.

Authority: 'O·O4 Stress Index', equations O4.1-O4.9, via
sahacore/data/onboarding_o4.json.

Step 8 of onboarding: ten PSS-10 answers and a count of stress-management
practices become the modifiers Layers C and E start from.

    O4.1  PSS10          = SUM(r_i') for i=1..10,
                           r_i' = 4 - r_i for i in {4,5,7,8}, else r_i
    O4.2  stress_idx_raw = PSS10 / 40
    O4.3  stress_idx_adj = max(0, stress_idx_raw - p_stressprot),
                           p_stressprot = 0.05 per practice (cap 0.20)
    O4.4  Theta_AL       = PSS10 / 40
    O4.5  gamma_cort     = 1 + 0.4  * Theta_AL
    O4.6  gamma_infl     = 1 + 0.3  * Theta_AL
    O4.7  gamma_gluc     = 1 + 0.3  * Theta_AL
    O4.8  gamma_cvd      = 1 + 0.3  * Theta_AL
    O4.9  lambda_rep_mod = 1 - 0.15 * Theta_AL

ALL NINE ARE IMPLEMENTED, and every symbol resolves.

PSS-10, NOT PSS-4 -- the sheet's own header calls that a correction, so which
items are reverse-scored is read from the registry rather than written here.
It is tabulated twice on the sheet, in a Reverse? column and inside O4.1's
formula, and the extractor refuses to import a sheet where the two disagree.

NO PARAMETERS TABLE, as on O3: every constant is written inside a formula, so
it is transcribed with the formula. What is TABULATED -- the reverse-scored
item set, the three interpretation bands -- is read.

THE FINDING: p_stressprot REACHES NOTHING. O4.3's Engine Target names O4.4,
O4.5, O4.6 and O4.7, and none of the four reads stress_idx_adj. O4.4
recomputes Theta_AL from PSS10 directly, and every modifier below it reads
Theta_AL. So a user who reports four stress-management practices gets exactly
the same cortisol, inflammation, glucose, CVD and repair modifiers as one who
reports none.

`stress_index_adjusted` is therefore implemented and called by nothing in
this module, which is what the sheet specifies. It is not wired into
`allostatic_load` on this build's initiative: doing so would move five
downstream modifiers on an unstated authority. Reported in
docs/parameter-gaps.md.

AND O4.2 IS O4.4. stress_index_raw and allostatic_load are the same function
of PSS10 under two names. They are kept separate because the sheet keeps them
separate and their engine targets differ -- O4.2 feeds O4.3, O4.4 feeds Layer
C's damage sensitivity -- but a caller should know they cannot disagree.
"""
from dataclasses import dataclass

# Written into the formulas by the sheet itself.
_ITEM_MAX = 4                    # O4.1: each item is scored 0-4
_ITEM_COUNT = 10                 # O4.1: ten items
_PSS10_MAX = _ITEM_MAX * _ITEM_COUNT   # 40, O4.2 and O4.4's denominator
_PROTECTION_PER_PRACTICE = 0.05  # O4.3
_PROTECTION_CAP = 0.20           # O4.3
_CORTISOL_SLOPE = 0.4            # O4.5
_INFLAMMATION_SLOPE = 0.3        # O4.6
_GLUCOSE_SLOPE = 0.3             # O4.7
_CVD_SLOPE = 0.3                 # O4.8
_REPAIR_SLOPE = 0.15             # O4.9


@dataclass(frozen=True)
class StressAnswers:
    """One user's Step 8 answers.

    `item_responses` are the ten raw PSS-10 responses in item order, each 0-4
    and NOT yet reverse-scored -- reversing is O4.1's job and needs the
    registry's item set. `practices` is the count of stress-management
    practices O4.3 credits.
    """
    item_responses: tuple[float, ...]
    practices: int = 0


def reverse_scored_items() -> frozenset[int]:
    """The 1-based item numbers O4.1 reverses, read from the sheet.

    Not written here. The sheet states them twice and calls the move from
    PSS-4 a correction, so which items reverse is its decision to make and
    this build's to read.
    """
    from sahacore.onboarding.parameters import load_o4_reverse_items
    return load_o4_reverse_items()


def scored_items(answers: StressAnswers) -> tuple[float, ...]:
    """O4.1's inner term: r_i' for each item, reversed where the sheet says.

    Raises rather than truncating or padding: a PSS-10 with nine answers is
    not a PSS-10, and scoring it would produce a total on a different scale
    that O4.2 would then divide by 40.
    """
    if len(answers.item_responses) != _ITEM_COUNT:
        raise ValueError(
            f"PSS-10 needs {_ITEM_COUNT} responses, got "
            f"{len(answers.item_responses)}.")
    for number, response in enumerate(answers.item_responses, start=1):
        if not 0 <= response <= _ITEM_MAX:
            raise ValueError(
                f"item {number} is {response}, outside the 0-{_ITEM_MAX} "
                "scale every PSS-10 item declares.")

    reverse = reverse_scored_items()
    return tuple(_ITEM_MAX - response if number in reverse else response
                 for number, response in
                 enumerate(answers.item_responses, start=1))


def pss10_total(answers: StressAnswers) -> float:
    """O4.1. The PSS-10 total, 0-40."""
    return float(sum(scored_items(answers)))


def stress_index_raw(answers: StressAnswers) -> float:
    """O4.2. PSS10 / 40. Feeds O4.3 and nothing else."""
    return pss10_total(answers) / _PSS10_MAX


def stress_protection(practices: int) -> float:
    """O4.3's inner term: 0.05 per practice, capped at 0.20.

    So the cap binds at four practices; a fifth earns nothing.
    """
    if practices < 0:
        raise ValueError(f"practices is {practices}, which cannot be negative.")
    return min(_PROTECTION_CAP, _PROTECTION_PER_PRACTICE * practices)


def stress_index_adjusted(answers: StressAnswers) -> float:
    """O4.3. max(0, stress_idx_raw - p_stressprot).

    COMPUTED AND CONSUMED BY NOTHING. O4.3 declares O4.4-O4.7 as its
    consumers and none of them reads it -- they all read Theta_AL, which
    O4.4 recomputes from PSS10. Implemented because the sheet specifies it;
    deliberately not wired into `allostatic_load`. See the module docstring.
    """
    return max(0.0, stress_index_raw(answers) - stress_protection(answers.practices))


def allostatic_load(answers: StressAnswers) -> float:
    """O4.4. Theta_AL = PSS10 / 40, feeding Layer C's damage sensitivity.

    The same function as O4.2, and NOT the adjusted index: the protective
    credit for stress practices does not reach here, because the sheet does
    not route it here.
    """
    return pss10_total(answers) / _PSS10_MAX


def cortisol_modifier(answers: StressAnswers) -> float:
    """O4.5. 1 + 0.4*Theta_AL, feeding Layer C's Z3, Z6 and Z7. The +40% the
    High band names is this at Theta_AL = 1."""
    return 1.0 + _CORTISOL_SLOPE * allostatic_load(answers)


def inflammation_modifier(answers: StressAnswers) -> float:
    """O4.6. Feeds Layer C's Z3 inflammation."""
    return 1.0 + _INFLAMMATION_SLOPE * allostatic_load(answers)


def glucose_modifier(answers: StressAnswers) -> float:
    """O4.7. Feeds Layer C's Z1 glycation."""
    return 1.0 + _GLUCOSE_SLOPE * allostatic_load(answers)


def cvd_modifier(answers: StressAnswers) -> float:
    """O4.8. Feeds Layer C's Z7 atherosclerosis."""
    return 1.0 + _CVD_SLOPE * allostatic_load(answers)


def repair_rate_modifier(answers: StressAnswers) -> float:
    """O4.9. 1 - 0.15*Theta_AL, applied to all of Layer C's Z repair rates.

    The only modifier on this sheet that falls with stress. The Moderate
    band's stated "-5% to -10%" is this across PSS-10 totals 14-26, and its
    "-15% maximum" is this at Theta_AL = 1.
    """
    return 1.0 - _REPAIR_SLOPE * allostatic_load(answers)


def stress_level(answers: StressAnswers) -> str:
    """The band a total falls in: 'Low', 'Moderate' or 'High'.

    The boundaries are read from the sheet, not written here -- where
    Moderate ends is a clinical judgement the workbook made. The bands tile
    0-40 with no gap, so exactly one matches.
    """
    from sahacore.onboarding.parameters import load_o4_bands

    total = pss10_total(answers)
    for band in load_o4_bands():
        if band["score_min"] <= total <= band["score_max"]:
            return band["stress_level"]
    raise ValueError(
        f"PSS-10 total {total} falls in none of the sheet's bands, which "
        "should be impossible: they tile 0-40.")
