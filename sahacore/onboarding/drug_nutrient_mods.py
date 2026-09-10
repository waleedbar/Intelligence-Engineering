"""ONB-009 — drug-nutrient modifiers, and what is NOT an absorption effect.

Authority: 'O·O9 Drug-Nutrient Mods', via sahacore/data/onboarding_o9.json.

Onboarding step 7, twenty rows, feeding Layers A, B, C and H.

O8'S RULE, VERIFIED BY THIS SHEET'S OWN ARITHMETIC. Five rows carry both a
legacy multiplier and its converted shift, and every one is ln(m) to six
decimals:

    Metformin x B12   m = 0.70 -> -0.356675      PPIs x Ca  0.80 -> -0.223144
    PPIs      x Mg    m = 0.75 -> -0.287682      PPIs x B12 0.85 -> -0.162519
    PPIs      x Fe    m = 0.80 -> -0.223144

That is the first place in this build where one sheet's rule is confirmed by
another sheet's numbers rather than by its own restatement.

THE OTHER FIFTEEN ROWS ARE NOT ABSORPTION EFFECTS AND THIS MODULE WILL NOT
PRETEND THEY ARE. Their rule cell holds an action class -- TIMING, MONITOR,
VETO, VETO/MONITOR, CLEARANCE or N/A -- and the sheet spells out twice, in
the production target itself, what that means:

    Levothyroxine    "Layer H: timing VETO; do not alter nutrient F_abs"
    Fluoroquinolones "Layer H: timing VETO; nutrient F_abs unchanged"

Chelation there reduces absorption of the DRUG. Code that read it the other
way would cut a user's calcium target because they take thyroid medication.
So `delta_logit_abs` RAISES on those rows, with the sheet's own sentence in
the message, rather than returning a number or a convenient zero.

Statins x CoQ10 is the same distinction from the other side: CRITICAL, real,
and "Biosynthesis depletion; not intestinal F_abs".

THE FINDING THAT MATTERS MOST. This sheet and the 339-row drug-nutrient VETO
registry disagree about the same interaction, and they disagree downwards:

    VETO-DN-0265  Insulin (any)  x Carbohydrate intake  CRITICAL
    VETO-DN-0267  Sulfonylureas  x Carbohydrate intake  CRITICAL
                  both: "STABLE PATTERN - discuss with prescriber"

    O9 row 29     Insulin/sulfonylureas x Glucose       MODERATE
                  "MONITOR", "Layer H: glucose safety"

Same drug class, the same hypoglycaemia hazard, and one registry routes it to
a prescriber while the other asks for a measurement. Recorded, not resolved;
`severity_disagreements` reports it rather than picking a winner.

It is not an isolated mismatch. O9's severity scale is CRITICAL / MODERATE /
LOW and the VETO registry's is CRITICAL / HIGH / MODERATE / LOW /
CONTROVERSIAL. O9 has NO HIGH tier, and HIGH is the VETO registry's largest --
111 of its 339 rows, just under a third. An O9 row cannot express what the
biggest slice of that registry says.
"""
from dataclasses import dataclass


class NotAnAbsorptionEffect(LookupError):
    """This row carries an action class, not a multiplier.

    Its own type because the wrong recovery -- treating it as zero, or as
    some default shift -- is exactly what the sheet's production targets
    warn against in so many words.
    """


@dataclass(frozen=True)
class Interaction:
    """One row of the sheet, with its severity and its production target."""
    drug: str
    nutrient: str
    rule_text: str
    legacy_multiplier: float | None
    delta_logit_abs: float | None
    mechanism_class: str
    severity: str
    production_target: str

    @property
    def is_absorption_effect(self) -> bool:
        return self.delta_logit_abs is not None


def _rows() -> tuple[Interaction, ...]:
    from sahacore.onboarding.parameters import load_o9_interactions
    return tuple(Interaction(
        drug=row["drug"], nutrient=row["nutrient"],
        rule_text=row["rule_text"],
        legacy_multiplier=row["legacy_multiplier"],
        delta_logit_abs=row["delta_logit_abs"],
        mechanism_class=row["mechanism_class"],
        severity=row["severity"],
        production_target=row["production_target"],
    ) for row in load_o9_interactions())


def interactions() -> tuple[Interaction, ...]:
    """Every row, in the sheet's order."""
    return _rows()


def interactions_for(drug: str) -> tuple[Interaction, ...]:
    """Every row for one drug or class. Empty is a real answer: seven of the
    medications the interface names have no row at all."""
    return tuple(row for row in _rows() if row.drug == drug)


def find(drug: str, nutrient: str) -> Interaction:
    for row in _rows():
        if row.drug == drug and row.nutrient == nutrient:
            return row
    raise LookupError(
        f"no row for {drug!r} x {nutrient!r}. Seven medications the interface "
        "names have no row on this sheet -- see docs/parameter-gaps.md.")


def delta_logit_abs(drug: str, nutrient: str) -> float:
    """The log-odds absorption shift for this pair, for O8's production
    equation.

    RAISES on the fifteen rows that carry an action class instead. The
    message quotes the sheet's own production target, because on two of them
    that sentence explicitly says the nutrient's absorption is unchanged and
    a caller reaching for a number here has misread which way the effect
    runs.
    """
    row = find(drug, nutrient)
    if not row.is_absorption_effect:
        raise NotAnAbsorptionEffect(
            f"{drug!r} x {nutrient!r} is {row.rule_text!r}, not a multiplier. "
            f"The sheet routes it to: {row.production_target!r}. Returning 0.0 "
            "would be as wrong as returning a shift -- this is a different "
            "kind of effect, not a smaller one.")
    return row.delta_logit_abs


def absorption_shifts(drugs: tuple[str, ...], nutrient: str) -> tuple[float, ...]:
    """Every absorption shift a user's medications impose on one nutrient.

    Rows that are not absorption effects are SKIPPED rather than raising --
    a user on four medications, two of which are timing rules, still has two
    real shifts. The skipping is safe here precisely because the shifts are
    being summed for O8's equation, where an omitted action class contributes
    nothing by definition; `delta_logit_abs` remains strict for the caller
    who asks about one pair.
    """
    shifts = []
    for row in _rows():
        if row.drug in drugs and row.nutrient == nutrient and row.is_absorption_effect:
            shifts.append(row.delta_logit_abs)
    return tuple(shifts)


def critical() -> tuple[Interaction, ...]:
    return tuple(row for row in _rows() if row.severity == "CRITICAL")


def severity_disagreements() -> tuple[dict, ...]:
    """Where this sheet and the drug-nutrient VETO registry rate the same
    drug class differently.

    Reported, never resolved. The one that matters is insulin and
    sulfonylureas: CRITICAL with a prescriber referral in the VETO registry,
    MODERATE with a monitoring action here.
    """
    from sahacore.onboarding.parameters import load_o9_severity_disagreements
    return load_o9_severity_disagreements()
