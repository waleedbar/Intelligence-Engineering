"""ONB-008 — condition modifiers, and the rule that keeps absorption bounded.

Authority: 'O·O8 Condition Modifiers', via sahacore/data/onboarding_o8.json.

Onboarding step 5, feeding Layers A and C. This sheet has no numbered
equations: it is a ten-row table of conditions plus one rule in prose, and
that rule is the important part.

THE COMPATIBILITY RULE, verbatim from the sheet:

    "any legacy positive F_bio multiplier m is interpreted as an ODDS
     multiplier and converted to Delta_logit_abs = ln(m). The production
     equation is F_abs = F_max * sigmoid(logit(F_base/F_max) +
     sum(Delta_logit_abs)); no direct multiplication may exceed [0,1]."

An absorbed fraction is bounded and a multiplier is not. F_base = 0.8 times
1.5 is 1.2, which is not a fraction of anything. The rule says: never do
that. Convert each multiplier to a shift in log-odds, add the shifts there,
and come back through a sigmoid -- which cannot leave (0, F_max) however
many modifiers are applied or how large they are.

`F_max` is a real column in the 81-nutrient registry, so this composes with
what is already imported rather than needing a number nobody has.

GATES ARE NOT OPTIONAL AND THIS MODULE WILL NOT LET YOU DROP ONE. The table
says "eta_Z7 x1.5 only when calibrated", "eta_Z3 x1.2 only if symptoms
support it", "eta_Z11 x1.5 only when confirmed". Four of the ten rows gate a
number that way and a fifth gates a described modifier.

So `eta_multiplier` REFUSES to return a gated factor unless the caller
states, explicitly and per call, that the gate is satisfied. There is no
default that quietly applies it. What "calibrated" or "confirmed" actually
means is defined nowhere in the workbook, so the decision cannot be made
here -- but it can be made impossible to make by accident.

WHAT THE SHEET DECLARES AND DOES NOT SUPPLY. Its Z-pathways column names 20
condition-to-pathway links and only 9 of them carry a modifier. Celiac
disease declares Z5, Z11 and Z12 and gives a factor for none; GERD declares
Z3 and gives none. `declared_pathways_without_a_modifier` reports them rather
than filling them in with 1.0, because "declared affected, effect unstated"
and "no effect" are different claims.
"""
import math
from dataclasses import dataclass


class GateNotSatisfied(ValueError):
    """A modifier the sheet withholds was requested without its condition.

    Its own type so a caller cannot swallow it with a bare except and so the
    sites that legitimately satisfy a gate are greppable.
    """


class ModifierNotSupplied(LookupError):
    """The sheet declares this pathway affected and gives no factor."""


@dataclass(frozen=True)
class ConditionRow:
    """One row of the sheet, with its gate and its warnings kept."""
    condition: str
    modifier_text: str
    gate: str | None
    modifiers: tuple[tuple[str, float], ...]
    declared_pathways: tuple[str, ...]
    pathways_without_a_modifier: tuple[str, ...]
    bounded_absorption_effect: str
    target_adjustment: str
    evidence_role: str


def _rows() -> dict[str, ConditionRow]:
    from sahacore.onboarding.parameters import load_o8_conditions
    return {row["condition"]: ConditionRow(
        condition=row["condition"],
        modifier_text=row["modifier_text"],
        gate=row["gate"],
        modifiers=tuple((m["z_pathway"], m["factor"]) for m in row["modifiers"]),
        declared_pathways=tuple(row["z_pathways_declared"]),
        pathways_without_a_modifier=tuple(row["z_pathways_without_a_modifier"]),
        bounded_absorption_effect=row["bounded_absorption_effect"],
        target_adjustment=row["target_adjustment"],
        evidence_role=row["evidence_role"],
    ) for row in load_o8_conditions()}


def conditions() -> tuple[ConditionRow, ...]:
    """Every condition the sheet models, in its own order."""
    return tuple(_rows().values())


def condition(name: str) -> ConditionRow:
    rows = _rows()
    if name not in rows:
        raise ModifierNotSupplied(
            f"{name!r} is not one of the sheet's {len(rows)} conditions. The "
            "interface's Step 5 offers conditions this sheet has no row for "
            "-- UC among them -- see docs/parameter-gaps.md.")
    return rows[name]


def eta_multiplier(name: str, z_pathway: str, *,
                   gate_satisfied: bool = False) -> float:
    """The factor to apply to eta for this condition on this pathway.

    `gate_satisfied` is keyword-only and defaults to FALSE, so a gated
    modifier is never applied by omission. Four of the ten rows carry a gate
    -- "only when calibrated", "only if symptoms support it", "only when
    confirmed" -- and a reader who took the number and dropped the clause
    would apply a 50% damage-sensitivity increase the sheet withheld.

    Raises rather than returning 1.0 when the sheet declares a pathway
    affected and gives no factor: "effect unstated" is not "no effect".
    """
    row = condition(name)
    factors = dict(row.modifiers)

    if z_pathway not in factors:
        if z_pathway in row.declared_pathways:
            raise ModifierNotSupplied(
                f"{name!r} declares {z_pathway} affected and the sheet gives "
                f"no factor for it ({row.modifier_text!r}). Returning 1.0 "
                "would turn 'effect unstated' into 'no effect'.")
        raise ModifierNotSupplied(
            f"{name!r} does not declare {z_pathway} affected at all; it names "
            f"{list(row.declared_pathways)}.")

    if row.gate and not gate_satisfied:
        raise GateNotSatisfied(
            f"{name!r} gives eta_{z_pathway} x{factors[z_pathway]} "
            f"{row.gate!r}. Pass gate_satisfied=True only where that has been "
            "established -- what it means is not defined in the workbook.")
    return factors[z_pathway]


def declared_pathways_without_a_modifier() -> dict[str, tuple[str, ...]]:
    """Every condition-to-pathway link the sheet declares and never quantifies.

    Reported rather than defaulted. There are 11 of them across 20 declared
    links, and nine distinct pathways.
    """
    return {row.condition: row.pathways_without_a_modifier
            for row in conditions() if row.pathways_without_a_modifier}


# --- the compatibility rule ----------------------------------------------

def delta_logit_from_multiplier(multiplier: float) -> float:
    """Delta_logit_abs = ln(m). A legacy F_bio multiplier as a log-odds shift.

    A multiplier of 1 is no shift; below 1 it is negative. Zero and negative
    multipliers have no logarithm and are refused rather than clamped --
    a multiplier of 0 means "absorbs nothing", which is a different claim
    from a large negative shift, and the sheet does not make it.
    """
    if multiplier <= 0:
        raise ValueError(
            f"multiplier {multiplier} has no logarithm; the compatibility "
            "rule is Delta_logit_abs = ln(m) for a POSITIVE multiplier.")
    return math.log(multiplier)


def _logit(p: float) -> float:
    return math.log(p / (1.0 - p))


def _sigmoid(z: float) -> float:
    # Written in the numerically stable branches so a large negative sum of
    # log-odds shifts cannot overflow exp().
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    exp_z = math.exp(z)
    return exp_z / (1.0 + exp_z)


def bounded_absorption(f_base: float, f_max: float,
                       delta_logits: tuple[float, ...] = ()) -> float:
    """The sheet's production equation, verbatim:

        F_abs = F_max * sigmoid(logit(F_base / F_max) + sum(Delta_logit_abs))

    THE POINT IS THE BOUND. Whatever shifts are applied and however large,
    the result stays strictly inside (0, F_max) -- because a sigmoid does.
    Multiplying F_base directly, which the sheet forbids in the same
    sentence, does not.

    With no shifts this returns F_base exactly, which is the identity the
    transformation has to satisfy to be a compatible rewrite rather than a
    different model.
    """
    if not 0.0 < f_max <= 1.0:
        raise ValueError(
            f"F_max is {f_max}; it is a maximum absorbed fraction and must "
            "lie in (0, 1].")
    if not 0.0 < f_base < f_max:
        raise ValueError(
            f"F_base is {f_base} against F_max {f_max}. The rule takes "
            "logit(F_base/F_max), which needs F_base strictly between 0 and "
            "F_max.")
    return f_max * _sigmoid(_logit(f_base / f_max) + sum(delta_logits))


def apply_multipliers(f_base: float, f_max: float,
                      multipliers: tuple[float, ...] = ()) -> float:
    """The whole rule end to end: legacy multipliers in, bounded fraction out.

    This is what a caller holding old F_bio multipliers should use. It is
    `bounded_absorption` over `delta_logit_from_multiplier`, and it exists so
    that the conversion is never skipped by someone who has the multipliers
    and reaches for the obvious thing.
    """
    return bounded_absorption(
        f_base, f_max,
        tuple(delta_logit_from_multiplier(m) for m in multipliers))


def compatibility_rule() -> str:
    """The rule as the sheet states it, for a caller that wants to quote it."""
    from sahacore.onboarding.parameters import load_o8_compatibility_rule
    return load_o8_compatibility_rule()
