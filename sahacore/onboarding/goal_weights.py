"""ONB-010 — goal priority weights, and the reward whose terms are undecided.

Authority: 'O·O10 Goal Priority Wts', via sahacore/data/onboarding_o10.json.

Onboarding steps 4 and 11, feeding Layers D and F. Eight goal areas and a
four-rung ladder:

    Primary (1st selected)    pi_k = 2.5
    Secondary (2nd selected)  pi_k = 2.0
    Tertiary (3rd selected)   pi_k = 1.5
    Unselected                pi_k = 1.0

THE LADDER IS MONOTONE AND ITS BASELINE IS EXACTLY 1. That second part
matters: an unselected goal weighted 1.0 makes pi_k a multiplier on a reward
term rather than a rescaling of everything, so a user who ranks nothing gets
the unweighted reward rather than a shrunken one.

ONE OF ONLY TWO SHEETS THAT CITE SOURCES. Every goal area names where its
nutrient targets come from -- AHA and REDUCE-IT, ADA 2024, NOF/IOF, EFSA,
ASRM. 'O·O6 Family History' is the other.

THE FINDING: THE HEAVIEST WEIGHT COMES FROM A QUESTION WHOSE ANSWERS ARE NOT
GOAL AREAS. The rules table says the Primary goal -- pi_k = 2.5, the top rung
-- is the "Highest priority goal from Step 4/11".

Step 11 lines up: its eight options are this sheet's eight rows, six exactly
and two where the sheet truncates the label. That is the cleanest agreement
any O-sheet has with the interface.

Step 4 lines up with nothing. It offers Weight Loss, Muscle Gain, Energy
Levels, Digestive Health, Chronic Condition, Manage Benefits and Healthy
Aging, and not one is a goal area here. "Weight Loss" has no pi_k, no
nutrient targets and no Z-pathways.

So `weight_for` takes a RANK, not a Step 4 answer, and `goal_for_ui_option`
resolves only Step 11 labels. A caller holding `primary_goal` gets an error
naming the problem rather than a silent 1.0.

AND WHAT THESE WEIGHTS MULTIPLY IS UNDECIDED. The engine equation is
"H1: r_t^pi = SUM(pi_k * r_k)". Layer H is the conservative bandit, and
'★ Scoped Builds — LTMLE Bandit' lists its reward proxy as OPEN FOUNDER
DECISION 5 -- with its own note calling it "the single biggest decision".
pi_k is settled; r_k is not.
"""
from dataclasses import dataclass


class NotAGoalArea(LookupError):
    """Asked for the weight of something this sheet does not rank."""


@dataclass(frozen=True)
class GoalArea:
    goal_area: str
    weight: float
    key_nutrient_targets: str
    z_pathways: tuple[str, ...]
    source: str
    ui_status: str


def goal_areas() -> tuple[GoalArea, ...]:
    from sahacore.onboarding.parameters import load_o10_goals
    return tuple(GoalArea(
        goal_area=row["goal_area"], weight=row["weight"],
        key_nutrient_targets=row["key_nutrient_targets"],
        z_pathways=tuple(row["z_pathways"]), source=row["source"],
        ui_status=row["ui_status"]) for row in load_o10_goals())


def weight_ladder() -> dict[str, float]:
    """Priority level -> pi_k, as the rules table gives it."""
    from sahacore.onboarding.parameters import load_o10_rules
    return {rule["priority_level"]: rule["weight"]
            for rule in load_o10_rules()}


def weight_for(rank: int | None) -> float:
    """pi_k for a goal the user ranked 1st, 2nd or 3rd -- or did not rank.

    Takes a RANK rather than a goal name, because ranking is what the ladder
    is a function of. `None` is the unselected baseline, 1.0.

    A fourth choice is refused rather than folded into the baseline: the
    sheet gives three rungs and a baseline, and silently treating a
    4th-ranked goal as unselected would be this build deciding that ranking
    it meant nothing.
    """
    ladder = weight_ladder()
    if rank is None:
        return ladder["Unselected"]
    if rank not in (1, 2, 3):
        raise ValueError(
            f"rank {rank} has no rung. The sheet gives Primary, Secondary and "
            "Tertiary and then an unselected baseline; pass None for "
            "unselected rather than a fourth rank.")
    return ladder[("Primary (1st selected)", "Secondary (2nd selected)",
                   "Tertiary (3rd selected)")[rank - 1]]


def goal_for_ui_option(option: str) -> GoalArea:
    """The goal area a Step 11 answer names.

    Accepts the exact label and the two the sheet truncates -- 'Immunity &
    Inflammation Control' and 'Fertility & Hormone Health' -- because those
    two are recorded as prefixes by the extractor, which is a stated
    relationship rather than an inferred one.

    A Step 4 answer raises. 'Weight Loss' is not a goal area on this sheet
    and there is no mapping anywhere that makes it one.
    """
    for goal in goal_areas():
        if goal.goal_area == option or option.startswith(goal.goal_area):
            return goal
    raise NotAGoalArea(
        f"{option!r} is not one of this sheet's eight goal areas. Step 4's "
        "primary_goal answers -- Weight Loss, Muscle Gain and the rest -- are "
        "none of them, and the rules table still says the Primary weight "
        "comes from 'Step 4/11'. See docs/parameter-gaps.md.")


def weighted_reward(rewards: dict[str, float],
                    ranking: tuple[str, ...] = ()) -> float:
    """H1: r_t^pi = SUM(pi_k * r_k), over the goal areas a caller supplies.

    `ranking` is the user's ordered choices; everything else gets the
    baseline. WHAT r_k IS is open founder decision 5 -- this composes the
    weights the sheet settles with terms it does not, so the caller supplies
    them and the undecided half stays visible.
    """
    ranks = {goal: index + 1 for index, goal in enumerate(ranking)}
    total = 0.0
    for goal, reward in rewards.items():
        goal_for_ui_option(goal)          # refuses anything not on the sheet
        rank = ranks.get(goal)
        total += weight_for(rank if rank in (1, 2, 3) else None) * reward
    return total
