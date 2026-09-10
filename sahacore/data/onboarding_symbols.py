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
             "MifflinStJeor", "DualHill", "SUMXMY2", "SUMSQ", "SUM"}

# English the sheets write inside formula cells. 'O3.5' reads
# "0 if 7<=h<=9; min(1,(7-h)/2) if h<7" and 'O3.1' continues on a second
# line with "where quality_factor = 1 - (quality_rating - 1)/4". These are
# prose, not quantities, and a tokeniser that took them for symbols would
# report five holes per sheet and be switched off within a week.
# 'in' joins them via O4.1's "for i in {4,5,7,8}", and 'cap'/'practice' via
# O4.3's parenthetical "0.05 per practice (cap 0.20)" -- English written
# inside a formula cell, describing a constant the same cell already gives.
KEYWORDS = {"where", "if", "else", "and", "or", "for", "otherwise", "each",
            "from", "per", "with", "of", "the", "to", "in", "cap", "practice"}

# Version tags the workbook appends to cells: '[v39l F-DM]', '[v39s QA]'.
_TAG = re.compile(r"\[[^\]]*\]")

# An identifier not preceded by a digit, so '40cm' does not yield 'cm' and
# '6.25*height_cm' still yields 'height_cm'.
_IDENTIFIER = re.compile(r"(?<![0-9A-Za-z_.])([A-Za-z_][A-Za-z0-9_]*)")

# A right-hand side that states a value or a rule rather than describing one:
# it carries a digit or an arithmetic operator.
#
# The hyphen has to be removed from English compounds first. "HR_Arem =
# hazard ratio from dose-response curve" is a description, and the hyphen in
# "dose-response" read as a minus sign made it look computable -- which
# silently un-reported one of the holes this file exists to find.
_WORD_HYPHEN = re.compile(r"(?<=[A-Za-z])-(?=[A-Za-z])")
_COMPUTABLE = re.compile(r"[0-9]|[+\-*/^()]")

# A summation or iteration index, bound by the formula that introduces it:
# O4.1's "SUM(r_i') for i=1..10" and "for i in {4,5,7,8}" both bind `i`.
#
# A bound index is not a quantity anything has to supply, so reporting it as
# undefined would be reporting the notation rather than a hole. It is matched
# against the whole formula before the statement split, because splitting on
# commas cuts "{4,5,7,8}" into pieces.
_BOUND_INDEX = re.compile(r"\bfor\s+([A-Za-z_][A-Za-z0-9_]*)\s*(?:=|\bin\b)")


def _states_a_value(right: str) -> bool:
    return bool(_COMPUTABLE.search(_WORD_HYPHEN.sub("", right)))

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
    # O3, step 9
    "sleep_hrs", "h", "quality_rating", "quality", "consistency_score",
    # O3.2 defines deficit_hrs in its own formula and O3.3/O3.4 read it; the
    # analyser sees the definition on the second line of O3.2's cell, but
    # 'deficit' is O3.4's own abbreviation for it.
    "deficit",
}

SHEETS = {
    "O1": ("onboarding_o1.json", "O·O1 Anthropometrics"),
    "O2": ("onboarding_o2.json", "O·O2 MVPA Prior"),
    "O3": ("onboarding_o3.json", "O·O3 Sleep Deficit"),
    "O4": ("onboarding_o4.json", "O·O4 Stress Index"),
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

# Routings already reported, in the same spirit. Anything broken_routings
# finds that is NOT in here is a break nobody has looked at.
KNOWN_BROKEN_ROUTINGS = {
    "O2.1": "MVPA_wk routes to O2.2, O2.3 and O2.4. The first two read it; "
            "O2.4 is PA_benefit = 100*(1 - HR_Arem) and does not. This is "
            "the SAME hole as HR_Arem seen from the other side, not a "
            "separate one -- and it is evidence about the missing curve: "
            "O2.4 describes HR_Arem as coming from a 'dose-response curve, "
            "Anchored at 150-300 min/wk zone', and min/wk is exactly "
            "MVPA_wk's unit. So the routing says HR_Arem is meant to be a "
            "function OF MVPA_wk. That identifies the missing curve's "
            "argument; it does not supply the curve.",
    "O3.1": "SDS is the quality-WEIGHTED shortfall and routes to O3.2, O3.3 "
            "and O3.4. All three compute from deficit_hrs = max(0, 7 - "
            "sleep_hrs) instead, so sleep quality reaches Layer C's Z3, Z6 "
            "and Z10 nowhere. Two users sleeping five hours who rate quality "
            "1/5 and 5/5 get identical modifiers.",
    "O4.3": "stress_idx_adj subtracts p_stressprot -- 0.05 per stress "
            "practice, capped at 0.20, a fifth of a 0-1 scale -- and routes "
            "to O4.4-O4.7. All four read Theta_AL, which O4.4 recomputes as "
            "PSS10/40 from the total, so the credit reaches no modifier.",
}


def formula_parts(formula: str, variables: str = "",
                  ordinal_options: set[str] | None = None
                  ) -> tuple[set[str], set[str]]:
    """The symbols an equation defines and the symbols it reads.

    Three things the sheets do that a plain split on '=' gets wrong:

      * A continuation line begins with 'where': O3.1's second line is
        "where quality_factor = 1 - (quality_rating - 1)/4", which DEFINES
        quality_factor. Stripping the keyword is what turns that from a
        hole into a definition.
      * The Variables column also defines things. O3.7 says
        "e_sleepqual=(5-quality)/4" there and nowhere else.
      * An inline ordinal scale -- "Very Inconsistent=1, Somewhat=2" --
        looks like four assignments to four symbols. The option names are
        passed in so they can be excluded; they are data, not quantities.
      * A formula can bind its own index: O4.1's "SUM(r_i') for i=1..10".
        `i` is notation, not a quantity anyone has to supply, and it is
        scoped to the equation that binds it rather than pooled.
    """
    # Bound indices are dropped from `used` at the end rather than added to
    # `defined`: `defined` is pooled across every equation to decide what
    # resolves, and O4.1 binding `i` must not make a stray `i` on another
    # sheet look accounted for.
    bound = set(_BOUND_INDEX.findall(formula))
    excluded = (ordinal_options or set()) | KEYWORDS | FUNCTIONS
    defined: set[str] = set()
    used: set[str] = set()

    def statements(text: str):
        for statement in re.split(r"[;\n,]", _TAG.sub(" ", text)):
            statement = statement.strip()
            if not statement:
                continue
            # 'where x = ...' and 'else x = ...' still define x.
            for keyword in ("where", "else"):
                if statement.lower().startswith(keyword + " "):
                    statement = statement[len(keyword) + 1:].strip()
            left, sep, right = statement.partition("=")
            yield statement, left.strip(), sep, right

    for statement, left, sep, right in statements(formula):
        if sep and _IDENTIFIER.fullmatch(left) and left not in excluded:
            defined.add(left)
            source = right
        else:
            source = statement
        used |= {name for name in _IDENTIFIER.findall(source)
                 if name not in excluded}

    # THE VARIABLES COLUMN CONTRIBUTES DEFINITIONS AND NOTHING ELSE.
    #
    # Its job is to say what each symbol is, and it does so two ways: with a
    # formula -- O3.7's "e_sleepqual=(5-quality)/4", the only place that is
    # written -- or with a gloss: "BW=weight (kg)", "k_IR=5 (sigmoid slope)",
    # "deficit_hrs = hours below 7h threshold". Both are statements that the
    # symbol has a stated meaning, so both count as defining it.
    #
    # The RIGHT-hand side is deliberately not read. Half of these are English,
    # and tokenising them reported sixty words -- GENERIC, PRIOR, sigmoid,
    # slope, kg -- as missing symbols, which is how a useful check becomes one
    # nobody reads. The cost is that a symbol appearing ONLY inside a
    # Variables-column formula would be missed; the user's own answers, which
    # is what those are, are covered by DECLARED_INPUTS.
    #
    # AN EQUALS SIGN IS NOT ENOUGH. O2.4's column reads "HR_Arem = hazard
    # ratio from dose-response curve" and O2.5's "rho_pop = population mean
    # repair". Those are DESCRIPTIONS: nothing can be computed from them, and
    # both are holes this file exists to report. An earlier version of this
    # rule counted any `x = ...` as a definition and silently swallowed both.
    #
    # So the right-hand side must look like a value or a formula -- it must
    # contain a digit or an arithmetic operator. That admits
    # "e_sleepqual=(5-quality)/4" and "k_IR=5 (sigmoid slope)", and refuses
    # the two above. "BW=weight (kg)" is refused too and is covered by
    # DECLARED_INPUTS, where a user's own answer belongs.
    for _, left, sep, right in statements(variables):
        if not (sep and _IDENTIFIER.fullmatch(left) and left not in excluded):
            continue
        if _states_a_value(right):
            defined.add(left)

    # A symbol a statement defines is not also a symbol it needs supplied,
    # and neither is an index the formula binds for itself.
    return defined, used - defined - bound


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
            options = {word
                       for option in equation.get("ordinal_scale", [])
                       for word in option["option"].split()}
            defined, used = formula_parts(
                equation["formula"], equation.get("variables") or "", options)
            equations.append({
                "equation_id": equation["equation_id"],
                "sheet": sheet,
                "defines": sorted(defined),
                "uses": sorted(used),
                "engine_target": equation.get("engine_target") or "",
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
        "broken_routings": broken_routings(equations),
    }


# An equation id named inside an Engine Target cell: 'O4.4, O4.5, O4.6, O4.7'
# routes on-sheet, 'Layer C: Z3 Inflammation rate' routes off-sheet.
_ROUTED_TO = re.compile(r"\bO\d+\.\d+\b")


def broken_routings(equations: list[dict]) -> list[dict]:
    """Equations whose declared on-sheet consumers do not read what they define.

    WHY THIS EXISTS, and it is the same lesson as the other checks in this
    file. Two findings of exactly this shape were found by hand, one per
    sheet, by writing a test that had to state a best and worst case:

      O3.1  SDS is quality-weighted and routes to O3.2, O3.3 and O3.4. All
            three read deficit_hrs instead, so sleep QUALITY reaches Layer C
            nowhere.
      O4.3  stress_idx_adj subtracts up to 0.20 of a 0-1 scale for stress
            practices and routes to O4.4-O4.7. All four read Theta_AL, which
            O4.4 recomputes from PSS10, so the credit reaches nothing.

    Finding the second one by hand after the first is a warning: there are
    ten more O-sheets, and an equation that computes something real and is
    then read by nobody is invisible to every other check here. Symbols that
    resolve, formulas that transcribe, headers that match -- all pass.

    THE RULE. An Engine Target cell that names other equations on the same
    sheet is a claim those equations consume this one's output. So each named
    consumer is checked for ANY symbol this equation defines. Targets that
    name a layer instead ('Layer C: Z3') are off-sheet and not checked --
    nothing here can see Layer C.

    A hit is not automatically a defect. It means the sheet says X feeds Y
    and Y does not mention X, which is a question for its author.
    """
    by_id = {e["equation_id"]: e for e in equations}
    broken = []
    for equation in equations:
        named = [eid for eid in _ROUTED_TO.findall(equation["engine_target"])
                 if eid in by_id and eid != equation["equation_id"]]
        if not named:
            continue
        defines = set(equation["defines"])
        deaf = [eid for eid in named if not (defines & set(by_id[eid]["uses"]))]
        if deaf:
            broken.append({
                "equation_id": equation["equation_id"],
                "sheet": equation["sheet"],
                "defines": equation["defines"],
                "engine_target": equation["engine_target"],
                "consumers_that_do_not_read_it": deaf,
            })
    return broken


def main() -> None:
    result = analyse()
    print(f"{len(result['equations'])} equations, "
          f"{len(result['parameters'])} parameters, "
          f"{len(result['defined_by_equations'])} symbols defined by equations")
    print()
    if not result["unresolved"]:
        print("every symbol resolves.")
    else:
        print("SYMBOLS NOTHING DEFINES:")
        for name, used_by in sorted(result["unresolved"].items()):
            status = "known" if name in KNOWN_UNRESOLVED else "*** NEW ***"
            print(f"  {name:<10} used by {', '.join(used_by):<12} {status}")
            if name in KNOWN_UNRESOLVED:
                print(f"             {KNOWN_UNRESOLVED[name]}")

    print()
    if not result["broken_routings"]:
        print("every on-sheet engine target reads what routes to it.")
        return
    print("EQUATIONS WHOSE DECLARED CONSUMERS DO NOT READ THEM:")
    for routing in result["broken_routings"]:
        equation_id = routing["equation_id"]
        status = "known" if equation_id in KNOWN_BROKEN_ROUTINGS else "*** NEW ***"
        print(f"  {equation_id:<10} defines {', '.join(routing['defines'])}, "
              f"routes to {routing['engine_target']!r}  {status}")
        print("             not read by "
              + ", ".join(routing["consumers_that_do_not_read_it"]))
        if equation_id in KNOWN_BROKEN_ROUTINGS:
            print(f"             {KNOWN_BROKEN_ROUTINGS[equation_id]}")


if __name__ == "__main__":
    main()
