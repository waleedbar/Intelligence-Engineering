"""Finds symbols an onboarding equation uses that nothing in the workbook defines.

    python -m sahacore.data.onboarding_symbols

WHY THIS EXISTS. Implementing ONB-002 turned up three symbols the workbook
names and never defines -- HR_Arem, K_PA, rho_pop -- and they were found by
hand, one at a time, while reading. A later audit found three more that the
same reading had walked straight past: e_WHtR and e_BMI in O1.9, and f_u_ref
in O1.8. ONB-001 had already been committed as complete.

Catching them by eye does not scale to twelve more O-sheets, and missing one
is worse than the others because an undefined symbol reaching code becomes a
guess. So the check is mechanical: take every equation this build has
imported, pull the symbols off the right-hand side, and account for each one
against the parameters, the other equations, and the user's own answers.
Whatever is left over is a hole in the source.

WHAT COUNTS AS RESOLVED
  a parameter      the sheet's PARAMETERS table supplies a value with a source
  another equation the symbol is some equation's left-hand side
  a user input     the onboarding screen collects it (DECLARED_INPUTS)

Everything else is unresolved, and an unresolved symbol is not a defect in
this code -- it is a question for the workbook's author.

WHAT THIS DELIBERATELY DOES NOT DO. It does not guess that `f_u_ref` is
parameter #37 `f_unbound,i` because their declared ranges happen to match, or
that `e_BMI` is some normalisation of BMI. Those are exactly the bridges that
have to be declared by a person and recorded, in the style of
build_eq_param_fk.ALIASES, rather than inferred from resemblance.
"""
import json
import re
from pathlib import Path

DATA_DIR = Path(__file__).parent

# Function names and operators that appear in formulas but are not quantities.
FUNCTIONS = {"min", "max", "exp", "sqrt", "ln", "log", "abs", "I",
             "MifflinStJeor", "DualHill", "SUMXMY2", "SUMSQ"}

# Version tags the workbook appends to cells: '[v39l F-DM]', '[v39s QA]'.
_TAG = re.compile(r"\[[^\]]*\]")

# An identifier not preceded by a digit, so '40cm' does not yield 'cm' and
# '6.25*height_cm' still yields 'height_cm'.
_IDENTIFIER = re.compile(r"(?<![0-9A-Za-z_.])([A-Za-z_][A-Za-z0-9_]*)")

# What the onboarding screens collect, read off the Variables columns of the
# O-sheets and 'P1 DataMap' section B. Written by hand because "this is an
# answer the user gives" is not something a parser can tell from a name.
DECLARED_INPUTS = {
    # O1, step 1
    "BW", "height_m", "height_cm", "waist_cm", "waist", "age", "sex", "neck",
    # O1.10's per-sex thresholds, given as values in the Variables column and
    # held in the parameters table under their long names.
    "threshold_lo", "threshold_hi",
    # O2, step 2
    "f_mod", "f_vig", "dur", "sitting_hrs",
    # O2.5 abbreviates PA_benefit as PA in its own formula.
    "PA",
}

SHEETS = {
    "O1": ("onboarding_o1.json", "O·O1 Anthropometrics"),
    "O2": ("onboarding_o2.json", "O·O2 MVPA Prior"),
}

# Symbols already reported, with what each one is missing. Anything the
# analyser finds that is NOT in here is a new hole nobody has looked at.
KNOWN_UNRESOLVED = {
    "e_WHtR":  "O1.9 weights it 0.30 and calls it a 'normalized [0,1] index'. "
               "No formula, no thresholds, no parameter row. Appears only "
               "inside O1.9 and its duplicate on 'P1 Onboarding'.",
    "e_BMI":   "O1.9 weights it 0.20, same wording, same absence.",
    "f_u_ref": "O1.8's per-nutrient reference for the unbound fraction. "
               "Parameter #37 f_unbound,i carries the same declared range "
               "(0.01-1.0) under a different spelling, and the two are NOT "
               "bridged here -- matching a range is not evidence of identity. "
               "The 81-nutrient registry has no unbound-fraction column.",
    "HR_Arem": "O2.4's hazard ratio 'from dose-response curve, Anchored at "
               "150-300 min/wk zone'. Described, never given.",
    "rho_pop": "O2.5's 'population mean repair'. In neither parameter registry.",
}


def formula_parts(formula: str) -> tuple[set[str], set[str]]:
    """The left-hand sides an equation defines and the symbols it reads."""
    defined: set[str] = set()
    used: set[str] = set()
    text = _TAG.sub(" ", formula)
    for statement in re.split(r"[;\n]", text):
        if not statement.strip():
            continue
        left, sep, right = statement.partition("=")
        if sep and _IDENTIFIER.fullmatch(left.strip() or "x"):
            defined.add(left.strip())
            source = right
        else:
            source = statement
        used |= {name for name in _IDENTIFIER.findall(source)
                 if name not in FUNCTIONS}
    return defined, used


def analyse() -> dict:
    """Every imported onboarding equation, and what each symbol resolves to."""
    equations: list[dict] = []
    parameters: set[str] = set()

    for prefix, (filename, sheet) in SHEETS.items():
        data = json.loads((DATA_DIR / filename).read_text(encoding="utf-8"))
        for parameter in data.get("parameters", []):
            # The sheet's parameter NAMES are prose ('k_IR (sigmoid slope)');
            # the symbol used in a formula is the part before any bracket.
            parameters.add(parameter["name"].split("(")[0].strip())
        for equation in data["equations"]:
            defined, used = formula_parts(equation["formula"])
            equations.append({
                "equation_id": equation["equation_id"],
                "sheet": sheet,
                "defines": sorted(defined),
                "uses": sorted(used),
            })

    defined_anywhere = {name for e in equations for name in e["defines"]}
    resolvable = defined_anywhere | parameters | DECLARED_INPUTS

    for equation in equations:
        equation["unresolved"] = sorted(
            name for name in equation["uses"] if name not in resolvable)

    unresolved: dict[str, list[str]] = {}
    for equation in equations:
        for name in equation["unresolved"]:
            unresolved.setdefault(name, []).append(equation["equation_id"])

    return {
        "equations": equations,
        "parameters": sorted(parameters),
        "defined_by_equations": sorted(defined_anywhere),
        "unresolved": unresolved,
    }


def main() -> None:
    result = analyse()
    print(f"{len(result['equations'])} equations, "
          f"{len(result['parameters'])} parameters, "
          f"{len(result['defined_by_equations'])} symbols defined by equations")
    print()
    if not result["unresolved"]:
        print("every symbol resolves.")
        return
    print("SYMBOLS NOTHING DEFINES:")
    for name, used_by in sorted(result["unresolved"].items()):
        status = "known" if name in KNOWN_UNRESOLVED else "*** NEW ***"
        print(f"  {name:<10} used by {', '.join(used_by):<12} {status}")
        if name in KNOWN_UNRESOLVED:
            print(f"             {KNOWN_UNRESOLVED[name]}")


if __name__ == "__main__":
    main()
