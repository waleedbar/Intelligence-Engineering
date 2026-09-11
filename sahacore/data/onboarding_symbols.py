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
  a user input     'O·Step-by-Step Questions' says the interface collects it
  a sheet spelling the O-sheet's own name for one of the above (SHEET_SPELLINGS)

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
from functools import lru_cache
from pathlib import Path

DATA_DIR = Path(__file__).parent

# Function names and operators that appear in formulas but are not quantities.
FUNCTIONS = {"min", "max", "exp", "sqrt", "ln", "log", "abs", "I",
             "MifflinStJeor", "DualHill", "SUMXMY2", "SUMSQ", "SUM",
             # O6.9 writes "P(disease) = Phi((l - threshold)/sigma)".
             # Phi is the standard normal CDF and P(...) is probability
             # notation -- both are functions, neither is a quantity.
             "Phi", "P",
             # O7.1 writes "C_f(0)_i ~ N(mu_pattern_i, sigma2_pattern_i)".
             # N names the Normal distribution, not a quantity.
             "N"}

# English the sheets write inside formula cells. 'O3.5' reads
# "0 if 7<=h<=9; min(1,(7-h)/2) if h<7" and 'O3.1' continues on a second
# line with "where quality_factor = 1 - (quality_rating - 1)/4". These are
# prose, not quantities, and a tokeniser that took them for symbols would
# report five holes per sheet and be switched off within a week.
# 'in' joins them via O4.1's "for i in {4,5,7,8}", and 'cap'/'practice' via
# O4.3's parenthetical "0.05 per practice (cap 0.20)" -- English written
# inside a formula cell, describing a constant the same cell already gives.
# 'disease' and 'positive' join via O6.9's "P(disease)" and O6.11's "if FH
# positive" -- English inside function notation and inside a condition.
KEYWORDS = {"where", "if", "else", "and", "or", "for", "otherwise", "each",
            "from", "per", "with", "of", "the", "to", "in", "cap", "practice",
            "disease", "positive"}

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

# A case guard opening a branch: O5.6's "Female: e_alcohol = ..." and
# "Male: e_alcohol = ...". The guard names which branch applies; it is not a
# quantity, and it must not stop the branch from defining its left-hand side.
# Anchored and single-word so it cannot swallow O5.7's "tobacco_idx: Never=0",
# which is an encoding rather than a guard -- that case is handled by passing
# the encoded variable in as a definition.
_CASE_GUARD = re.compile(r"^(Female|Male)\s*:\s*")

# A trailing subscript, tokenised out of an expression rather than named as a
# quantity: O7.1's "C_f(0)_i" yields a bare `_i` after the bracket. A leading
# underscore never starts a symbol anywhere in this workbook, so a token that
# begins with one is notation.
_SUBSCRIPT = re.compile(r"^_")

# A formula cell that is PROSE rather than an equation. O7.3's whole cell
# reads "Days 1-7: prior dominates (k small) / Day 14+: food logs dominate
# (k large)" -- a schedule, with no relation asserted anywhere in it.
# Tokenising that yields ten English words as missing symbols, which is how a
# useful check becomes one nobody reads.
#
# The test is the absence of any relation operator in the WHOLE cell: '=' or
# '~'. Every real formula in the O-sheets carries one, including O7.1, whose
# '~' is what makes C_f(0) a definition rather than a use.
_RELATION = re.compile(r"[=~]")


def _states_a_value(right: str) -> bool:
    return bool(_COMPUTABLE.search(_WORD_HYPHEN.sub("", right)))


@lru_cache(maxsize=1)
def ui_inputs() -> frozenset[str]:
    """Every variable the interface collects, read from the UI contract.

    THIS USED TO BE A HAND-WRITTEN SET, and it carried this comment: "written
    by hand because 'this is an answer the user gives' is not something a
    parser can tell from a name."

    That was true only while 'O·Step-by-Step Questions' was unimported. The
    sheet is manifest order 70 -- BEFORE all five O-sheets that consume it --
    and its 'Maps To' column says exactly that, for all 62 inputs, in the
    workbook's own words. Nine of the twenty-one hand-written entries were
    simply this list, retyped.

    What a hand-written set could never do is report an input the sheets
    declare and the UI does not collect. This one can, and it found one --
    see `sitting_hrs` in KNOWN_UNRESOLVED.
    """
    data = json.loads((DATA_DIR / "step_questions.json").read_text(encoding="utf-8"))
    return frozenset(question["variable"] for question in data["questions"])


# An O-sheet's own spelling for something already accounted for, and what it
# stands for. Every entry is a BRIDGE DECLARED BY A PERSON, in the style of
# build_eq_param_fk.ALIASES -- never inferred from resemblance, which is the
# whole reason f_u_ref is still an open hole rather than quietly tied to
# parameter #37.
#
# Nothing that merely LOOKS like a UI variable belongs here. `sitting_hrs`
# resembles `standing_hrs` closely enough to be tempting and means something
# different, so it is reported instead.
SHEET_SPELLINGS = {
    # Unit conversions and abbreviations O1 declares in its own Variables
    # column: the UI collects centimetres, O1.1 works in metres.
    "height_m": "height_cm converted to metres, declared in O1.1's variables",
    "waist": "waist_cm, abbreviated by O1",
    "neck": "neck_cm, abbreviated by O1",
    # O1.10's per-sex thresholds are values in its Variables column and rows
    # in the parameters table under longer names.
    "threshold_lo": "O1.10's lower per-sex threshold, from the parameters table",
    "threshold_hi": "O1.10's upper per-sex threshold, from the parameters table",
    # Abbreviations for a value defined elsewhere on the same sheet.
    "PA": "PA_benefit, abbreviated by O2.5 in its own formula",
    "h": "sleep_hrs, abbreviated by O3.5",
    "deficit": "deficit_hrs, abbreviated by O3.4",
    # The UI calls these sleep_quality and sched_consistency; O3 renames both.
    "quality_rating": "sleep_quality, renamed by O3.1",
    "quality": "sleep_quality, abbreviated by O3.7",
    "consistency_score": "sched_consistency, renamed by O3.6",
    # The UI collects SSB_serv as a band; O5.5 works in servings per day.
    "SSB_serv_day": "SSB_serv, converted to servings/day by O5.5's midpoints",
    # O5's five smoking categories are a join of smoke_status and quit_time,
    # and no sheet gives the rule -- the join itself is reported in
    # docs/parameter-gaps.md. The symbol is accounted for; the rule is not.
    "smoke_status": "collected by the UI, though O5's five categories are a "
                    "join of it with quit_time that no sheet specifies",
    # O6.1 is the GENERAL form -- "delta_FH = I(FH) * ln(RR)", with its
    # Variables cell reading "I(FH) = 1 if family history present". FH is a
    # placeholder for whichever of the six histories is being shifted, and
    # O6.2-O6.7 instantiate it. O6.11's "if FH positive" uses the same
    # placeholder -- which is itself the ambiguity recorded against O6.11.
    "FH": "the generic family history in O6.1's general form, instantiated "
          "by O6.2-O6.7 as FH_T2D, FH_CVD, FH_stroke, FH_colon, FH_breast "
          "and FH_AD -- all six of which the UI collects",
    # O6.1's Variables cell defines RR as "relative risk" and every
    # instantiation supplies a value with a cited source.
    "RR": "the relative risk in O6.1's general form; O6.2-O6.7 each supply "
          "one, and the reference table cites a study for all six",
    # O7.1's "C_f(0)_i" is the fast nutrient state at t=0. The state vector
    # registry names that block C_fast and gives it slots 1-81, and O7.1's
    # own engine target reads "Layer E: x_hat(0)[1..81]" -- the same 81. A
    # structural match, not a resemblance between two names.
    "C_f": "C_fast, the 81-slot nutrient block of the 219-state vector; "
           "O7.1's engine target names exactly those slots, x_hat(0)[1..81]",
}

SHEETS = {
    "O1": ("onboarding_o1.json", "O·O1 Anthropometrics"),
    "O2": ("onboarding_o2.json", "O·O2 MVPA Prior"),
    "O3": ("onboarding_o3.json", "O·O3 Sleep Deficit"),
    "O4": ("onboarding_o4.json", "O·O4 Stress Index"),
    "O5": ("onboarding_o5.json", "O·O5 Substance Exposure"),
    "O6": ("onboarding_o6.json", "O·O6 Family History"),
    "O7": ("onboarding_o7.json", "O·O7 Diet Pattern Priors"),
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
               "bridged here -- matching a range is not evidence of identity, "
               "and their roles differ: #37 is 'Computed from B7 or published "
               "values', while f_u_ref is the REFERENCE that O1.8 then "
               "adjusts for BMI. The 81-nutrient registry has no "
               "unbound-fraction column.\n"
               "             WHAT IS KNOWN, which an earlier version of this "
               "entry omitted: the workbook cites a source for the quantity "
               "(Benet & Hoener 2002); variable #39 says it is 'Fraction "
               "unbound for molecules where protein binding is relevant; NOT "
               "A UNIVERSAL NUTRIENT PARAMETER', so an 81-row table is the "
               "wrong thing to expect; and one concrete value exists -- "
               "caffeine f_u=0.65, on 'MERGE·Bev Engine Params'. The gap is "
               "the per-nutrient table and the list of nutrients it applies "
               "to, not the concept or its provenance.",
    "HR_Arem": "O2.4's hazard ratio 'from dose-response curve, Anchored at "
               "150-300 min/wk zone'. Described, never given -- but the "
               "citation IS given, Arem 2015, so this is a number to be read "
               "out of a named paper rather than one nobody can obtain. No "
               "hazard ratio appears anywhere in the workbook for it.",
    "rho_pop": "O2.5's 'population mean repair'. In neither parameter registry.",
    "sitting_hrs":
        "O2.8 is eta_sed = I(sitting_hrs > 6) * 0.15 and its Variables cell "
        "says 'sitting_hrs from Step 2 UI'. Step 2 does not collect it. It "
        "asks 'Hours spent standing daily' (standing_hrs, options <1 hr / "
        "2 hrs / 3 hrs / 5 hrs), which is a different quantity -- time not "
        "spent standing is not time spent sitting. The symbol appears nowhere "
        "in the workbook except O·O2 and its duplicate on 'P1 Onboarding'.\n"
        "             Sitting time itself is real elsewhere in the engine: "
        "canonical state 188 is SED_smooth, 'Smoothed sedentary time' in "
        "min/day, and 'P1 DataMap' row 53 carries 'Sedentary time / Minutes "
        "of sitting/inactivity', 0-1440, from 'Activity Sensors'. (An earlier "
        "version of this entry said slot 185. That was a ROW NUMBER on "
        "'P1 Variables 219', not a state index; the state vector this build "
        "loads says 188.) So the quantity exists -- what is missing is any "
        "way to get it AT ONBOARDING, before a device is connected, which is "
        "exactly when O2.8 runs. State 188's own declared source is "
        "'Wearable/self-report', so self-report is an admitted route and "
        "Step 2 simply never asks.\n"
        "             AND STEP 2 IS NOT SILENT ABOUT SEDENTARINESS, which "
        "this entry also used to imply. Its FIRST question is 'General daily "
        "activity level: Sedentary / Lightly Active / Active / Very Active / "
        "Other', mapped to activity_level -> O2. A sedentary signal IS "
        "collected; it is a category where O2.8 wants hours. Turning one into "
        "the other is the same kind of band midpoint O2 already declares for "
        "session frequency (1-2 -> 1.5) -- and therefore the same kind of "
        "thing that has to be declared rather than assumed here.\n"
        "             Found only after 'O·Step-by-Step Questions' was "
        "imported, because until then the analyser took O2.8's own word for "
        "where its input came from.",

    # --- O6.8, the Pearson-Aitken posterior ------------------------------
    #
    # mu_post = mu + Sigma_12 * Sigma_22^-1 * (x2 - mu_2). Standard, complete
    # as mathematics, and the workbook supplies not one of its five inputs.
    # There is no covariance anywhere between a family history and a damage
    # state, and no population mean vector. Recorded one symbol at a time
    # rather than as a single note, because each is separately missing.
    "Sigma_12": "O6.8's cross-covariance between the damage states and the "
                "observed family history. Nothing in the workbook states a "
                "covariance between the two.",
    "Sigma_22": "O6.8's covariance of the observed family history with "
                "itself. Same absence -- and the six histories are collected "
                "as independent checkboxes, so even their mutual correlation "
                "is unstated.",
    "mu":       "O6.8's population mean for the states being updated. The "
                "Variables cell says 'mu=population mean' and no sheet gives "
                "one.",
    "mu_2":     "O6.8's population mean for the family-history block -- the "
                "base rate of each history. Not in the workbook.",
    "x2":       "O6.8's observed family history as a NUMBER. The UI collects "
                "six booleans; how they become the vector this subtracts a "
                "mean from is unstated.",

    # --- O6.9, the liability threshold model ------------------------------
    "g":         "O6.9's genetic component of liability. Named, never given, "
                 "and no sheet says how a family history becomes one.",
    "e":         "O6.9's environmental component of liability. Same.",
    "threshold": "O6.9's liability threshold, above which disease occurs. "
                 "Not given for any of the six conditions.",
    "sigma":     "O6.9's liability standard deviation. Not given either, and "
                 "P(disease) = Phi((l - threshold)/sigma) needs both it and "
                 "the threshold to mean anything.",

    # --- O6.10 and O6.11 --------------------------------------------------
    "FH_relevant": "O6.10 raises damage sensitivity by 30% when a family "
                   "history is 'relevant per pathway', and defines relevance "
                   "nowhere. The RR reference table's Z-Pathway Affected "
                   "column DOES map each condition to its pathways, and that "
                   "is what sahacore.onboarding.family_history reads -- but "
                   "the sheet never says that column is what FH_relevant "
                   "means, so the bridge is not declared here.",
    "eta_hi":     "O6.10's base damage sensitivity. THE STRONGEST BRIDGE "
                  "CANDIDATE IN THIS LIST, and still not bridged: parameter "
                  "#47 is 'eta_hi,k', layer C, equation C2, full name 'High "
                  "damage sensitivity', and O6.10's Variables cell says "
                  "'eta_hi = base damage sensitivity'. Same base spelling, "
                  "same layer, same words -- the ',k' is the per-cluster "
                  "subscript O6.10 drops while stating a general rule. That "
                  "is far better evidence than f_u_ref had, and it is still "
                  "inference rather than a declaration, so it is put to the "
                  "author instead of assumed.",
    "sigma2_base": "O6.11's default prior variance, which it multiplies by "
                   "1.5. Layer E's P(0) diagonal is its engine target and no "
                   "sheet gives its default. Searched both parameter "
                   "registries for a prior variance and there is none.",

    # --- O7.1, the largest gap in the build -------------------------------
    #
    # C_f(0)_i ~ N(mu_pattern_i, sigma2_pattern_i), engine target
    # "Layer E: x_hat(0)[1..81]". Eight patterns x 81 nutrients = 648 MEANS,
    # and the workbook has none of them. The variance is a separate matter:
    # see sigma2_pattern_i below.
    "mu_pattern_i":
        "O7.1's expected intake of nutrient i under dietary pattern m -- the "
        "STARTING VALUE of 81 of the engine's 219 states. Eight patterns x 81 "
        "nutrients = 648 means, and the sheet gives prose instead: 'High "
        "omega-3, olive oil, fiber'.\n"
        "             Searched before concluding: mu_pattern appears in the "
        "whole workbook only on O·O7 and its duplicate at 'P1 Onboarding' row "
        "328; the 81-nutrient registry carries kinetics and no baseline "
        "intake column; and the only other 'pattern' sheet is Layer W's "
        "behavioural alarms. This is the largest single gap found so far.",
    "sigma2_pattern_i":
        "O7.1's variance on that same prior, which Layer E's P(0) diagonal "
        "would be initialised from. NOT ABSENT, and this entry used to say it "
        "was: 'O·O12-O14 State Init' O13.2 gives 'sigma^2 = (0.3-0.5)^2 per "
        "typed nutrient/exposure prior unless a stronger source exists' for "
        "states [1..162].\n"
        "             Unresolved here only because it is undefined AS A "
        "SYMBOL on this sheet, and because O13.2 is pattern-independent -- it "
        "is one rule for all 162 PK states, so O7's per-pattern subscript has "
        "nothing behind it. It also still leaves a choice inside 0.3-0.5. The "
        "earlier claim that it was missing came from searching for the NAME "
        "sigma2_pattern rather than for the quantity.",

    # --- O7.2 -------------------------------------------------------------
    "sigma2_prior":
        "O7.2's prior variance, described by its own Variables cell as 'from "
        "pattern'. That is sigma2_pattern_i, so this is the SAME hole seen "
        "from the equation that consumes it: O7.2 is correct arithmetic that "
        "cannot be run until O7.1's priors exist.",
    "sigma2_obs":
        "O7.2's observation variance, 'from food logs'. A RUNTIME quantity "
        "rather than a missing constant -- the sheet says where it comes "
        "from and the source is one the engine will have. Reported because "
        "nothing defines it as a symbol, not because it is unobtainable; "
        "sahacore.onboarding.diet_priors takes it as an argument.",
    "k": "O7.2's observation count, 'k=days'. Runtime like sigma2_obs, and "
         "adequately located by the sheet. Also an argument.",
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

    # A prose cell asserts no relation, so it names no quantities either.
    # Its Variables column is still read, because that is where such a row
    # says what its symbols mean.
    if not _RELATION.search(formula):
        formula = ""
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
            # So does a case guard. O5.6 is written as two cases,
            # "Female: e_alcohol = ..." and "Male: e_alcohol = ...", and the
            # guard is a condition on which branch applies -- not a symbol
            # anything supplies, and not something that stops e_alcohol being
            # defined here.
            guard = _CASE_GUARD.match(statement)
            if guard:
                statement = statement[guard.end():].strip()
            # '~' asserts a distribution and defines its left-hand side
            # exactly as '=' defines a value: O7.1's "C_f(0)_i ~ N(...)" is
            # what says C_f(0) is being given a prior.
            separator = "~" if ("~" in statement and "=" not in statement) else "="
            left, sep, right = statement.partition(separator)
            yield statement, left.strip(), sep, right

    for statement, left, sep, right in statements(formula):
        if sep and _IDENTIFIER.fullmatch(left) and left not in excluded:
            defined.add(left)
            source = right
        else:
            source = statement
        used |= {name for name in _IDENTIFIER.findall(source)
                 if name not in excluded and not _SUBSCRIPT.match(name)}

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
        # AN ANSWER ENCODING IS A DEFINITION, AND ITS LABELS ARE DATA.
        #
        # 'O·O5 Substance Exposure' writes four of them -- "where: Never=0,
        # Former(>1yr)=2, ..." for pack_years, and the same shape for
        # units_week, tobacco_idx and the SSB midpoints. Read naively that is
        # five assignments to five symbols called Never, Former, Daily and so
        # on, while the quantity the table actually defines -- pack_years --
        # never appears on a left-hand side at all and looks like a hole.
        #
        # Both halves are wrong in the same way, so both are fixed here: the
        # option labels join the excluded set (they are answers, not
        # quantities), and the encoded variable is credited to the equation
        # that encodes it.
        encoded: dict[str, set[str]] = {}
        encoded_options: dict[str, set[str]] = {}
        for encoding in data.get("encodings", []):
            equation_id = encoding["equation_id"]
            encoded.setdefault(equation_id, set()).add(encoding["encodes"])
            if encoding.get("option"):
                # Tokenised the same way a formula is, not split on spaces:
                # 'Former(>1yr)' is one label and two identifiers, and it is
                # the identifiers the tokeniser will go looking for.
                encoded_options.setdefault(equation_id, set()).update(
                    _IDENTIFIER.findall(encoding["option"]))

        for equation in data["equations"]:
            equation_id = equation["equation_id"]
            options = {word
                       for option in equation.get("ordinal_scale", [])
                       for word in option["option"].split()}
            options |= encoded_options.get(equation_id, set())
            defined, used = formula_parts(
                equation["formula"], equation.get("variables") or "", options)
            defined |= encoded.get(equation_id, set())
            equations.append({
                "equation_id": equation_id,
                "sheet": sheet,
                "defines": sorted(defined),
                "uses": sorted(used - defined),
                "engine_target": equation.get("engine_target") or "",
            })

    defined_anywhere = {name for e in equations for name in e["defines"]}
    resolvable = defined_anywhere | parameters | ui_inputs() | set(SHEET_SPELLINGS)

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
