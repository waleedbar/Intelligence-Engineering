"""Extracts 'O·O7 Diet Pattern Priors' into onboarding_o7.json.

Source: v39sEng2.xlsx, sheet 'O·O7 Diet Pattern Priors'.
'01_IMPORT_MANIFEST' order 77, role ONBOARDING, import YES, backend Yes.

    python -m sahacore.data.build_onboarding_o7 <path-to-workbook>

The authority for ONB-007. Onboarding step 3, "81-nutrient Normal priors",
feeding Layers A, B and E. Two tables:

    FOUR EQUATIONS    O7.1 the per-pattern nutrient prior, O7.2 its Bayesian
                      update, O7.3 when logs overtake the prior, O7.4 a diet
                      quality index
    EIGHT PATTERNS    each with its nutrient shifts, typical deficiencies and
                      the label the interface is supposed to show

THE HEADLINE FINDING: O7.1 IS THE WHOLE SHEET AND IT HAS NO NUMBERS.

    C_f(0)_i ~ N(mu_pattern_i, sigma2_pattern_i)

Its engine target is "Layer E: x_hat(0)[1..81]" -- the initial state of 81 of
the 219 states, which is every nutrient the engine tracks. Eight patterns
times 81 nutrients is 648 means and 648 variances, and the sheet supplies
NONE of them. What it gives instead is prose: "High omega-3, olive oil,
fiber", "B12, Iron (heme), Zinc, Omega-3".

Searched before concluding: `mu_pattern` and `sigma2_pattern` appear in the
whole workbook only here and on this sheet's duplicate at 'P1 Onboarding'
row 328. The 81-nutrient registry carries kinetics -- gamma shapes, decay
constants, half-lives -- and no baseline intake column of any kind. The only
other sheet whose name suggests patterns, 'M-WPAT Patterns Alarms', is Layer
W behavioural patterns and has nothing to do with diet.

So ONB-007 is substantively blocked in the same way ONB-011 and ONB-012 are,
and for a sharper reason: those are missing a mapping, this is missing 1,296
numbers. What IS buildable is built -- O7.2's update, O7.4's index, and the
pattern catalogue -- and O7.1 is transcribed and left as a declared gap.

THREE STATEMENTS OF THE DIET PATTERN LIST, AND THEY DISAGREE.

    this sheet        8 patterns, and its own "UI Label" column marks two of
                      them "Not in current UI"
    'P1 DataMap' 125  "Radio (8 options)", default "Standard Balanced"
    the questionnaire 6 options, one of which is Intermittent Fasting

The sheet already knows about two of the three gaps -- it says so. What it
does not say is that the interface offers a seventh pattern it has never
heard of. A user who selects Intermittent Fasting gets no prior at all.
"""
import json
import re
import sys
from pathlib import Path

import openpyxl

from sahacore.data.sheet_header import check_header

SHEET = "O·O7 Diet Pattern Priors"
FIRST_COL = 3
DATA_DIR = Path(__file__).parent
OUT = DATA_DIR / "onboarding_o7.json"

EQUATION_HEADER_ROW = 9
EQUATION_ROWS = range(10, 14)
EQUATION_LABELS = ["ID", "Name", "Formula", "Variables", "Units",
                   "Value/Range", "Engine Target"]

PATTERN_HEADER_ROW = 18
PATTERN_ROWS = range(19, 27)
PATTERN_LABELS = ["Pattern", "Key Nutrient Shifts", "Typical Deficiencies",
                  "UI Label"]

EXPECTED_EQUATIONS = 4
EXPECTED_PATTERNS = 8

# What the sheet writes in its UI Label column when a pattern has no place in
# the interface. Its own admission, and the reason two of the three
# discrepancies below are already known to its author.
NOT_IN_UI = "Not in current UI"

# The symbols O7.1 needs and the workbook never gives a value for.
UNSUPPLIED = ("mu_pattern", "sigma2_pattern")

# A digit that is a QUANTITY rather than part of a name. The nutrient names
# on this sheet are full of digits -- omega-3, B12, VitD -- and a plain
# search for `\d` reads "High omega-3, olive oil, fiber" as a table of
# numbers. Same shape as the hyphen in "dose-response" that once made a
# description look computable.
_STANDALONE_NUMBER = re.compile(r"(?<![A-Za-z0-9-])\d")


def _text(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _cell(ws, row: int, offset: int):
    return ws.cell(row=row, column=FIRST_COL + offset).value


def _ui_diet_options() -> list[str]:
    data = json.loads((DATA_DIR / "step_questions.json").read_text(encoding="utf-8"))
    matching = [q for q in data["questions"] if q["variable"] == "diet_pattern"]
    if len(matching) != 1:
        raise SystemExit(
            f"{SHEET}: the UI contract has {len(matching)} diet_pattern "
            "questions, expected exactly one.")
    return matching[0]["answer_options"]


def extract(path: str) -> dict:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb[SHEET]
    check_header(ws, SHEET, EQUATION_HEADER_ROW, FIRST_COL, EQUATION_LABELS)
    check_header(ws, SHEET, PATTERN_HEADER_ROW, FIRST_COL, PATTERN_LABELS)

    equations = []
    for row in EQUATION_ROWS:
        equation_id = _text(_cell(ws, row, 0))
        if equation_id is None:
            raise SystemExit(f"{SHEET}: row {row} has no equation id.")
        equations.append({
            "equation_id": equation_id,
            "source_row": row,
            "name": _text(_cell(ws, row, 1)),
            "formula": _text(_cell(ws, row, 2)) or "",
            "variables": _text(_cell(ws, row, 3)),
            "units": _text(_cell(ws, row, 4)),
            "value_range": _text(_cell(ws, row, 5)),
            "engine_target": _text(_cell(ws, row, 6)),
        })

    offered = _ui_diet_options()
    patterns = []
    for row in PATTERN_ROWS:
        pattern = _text(_cell(ws, row, 0))
        if pattern is None:
            raise SystemExit(f"{SHEET}: pattern row {row} has no name.")
        ui_label = _text(_cell(ws, row, 3))

        # Three states, and they are kept apart because they mean different
        # things. The sheet DECLARING a pattern absent from the interface is
        # not the same as its label failing to match one.
        if ui_label == NOT_IN_UI:
            status = "DECLARED_NOT_IN_UI"
        elif ui_label in offered:
            status = "MATCHES_UI_EXACTLY"
        else:
            status = "LABEL_DOES_NOT_MATCH_ANY_UI_OPTION"

        patterns.append({
            "pattern": pattern,
            "source_row": row,
            "key_nutrient_shifts": _text(_cell(ws, row, 1)),
            "typical_deficiencies": _text(_cell(ws, row, 2)),
            "ui_label": ui_label,
            "ui_status": status,
        })

    # A UI option no pattern claims by an EXACT label. Deliberately exact:
    # 'Mediterranean Diet' plainly means 'Mediterranean', and saying so is a
    # bridge for a person to declare, not for this to assume.
    claimed = {p["ui_label"] for p in patterns}
    unclaimed = [option for option in offered if option not in claimed]

    wb.close()
    return {"sheet": SHEET, "equations": equations, "patterns": patterns,
            "ui_options": offered, "ui_options_no_pattern_claims": unclaimed}


def check(data: dict) -> None:
    equations, patterns = data["equations"], data["patterns"]

    if len(equations) != EXPECTED_EQUATIONS:
        raise SystemExit(f"{SHEET}: expected {EXPECTED_EQUATIONS} equations, "
                         f"got {len(equations)}.")
    if [e["equation_id"] for e in equations] != [f"O7.{n}" for n in range(1, 5)]:
        raise SystemExit(f"{SHEET}: equations are not O7.1..O7.4.")
    by_id = {e["equation_id"]: e for e in equations}
    for equation in equations:
        for field in ("name", "formula", "variables", "units", "value_range",
                      "engine_target"):
            if not equation[field]:
                raise SystemExit(
                    f"{SHEET}: {equation['equation_id']} has no {field}.")

    if len(patterns) != EXPECTED_PATTERNS:
        raise SystemExit(f"{SHEET}: expected {EXPECTED_PATTERNS} patterns, got "
                         f"{len(patterns)}.")
    if len({p["pattern"] for p in patterns}) != EXPECTED_PATTERNS:
        raise SystemExit(f"{SHEET}: the pattern names are not distinct.")
    for pattern in patterns:
        for field in ("key_nutrient_shifts", "typical_deficiencies", "ui_label"):
            if not pattern[field]:
                raise SystemExit(
                    f"{SHEET}: pattern {pattern['pattern']!r} has no {field}.")

    # THE HEADLINE FINDING, ASSERTED. O7.1 names two quantities per nutrient
    # per pattern and the sheet gives neither, for any of them. If a table of
    # them ever appears this stops the extract, which is the moment to read
    # it -- 1,296 numbers arriving is not something to absorb silently.
    o7_1 = by_id["O7.1"]
    for symbol in UNSUPPLIED:
        if symbol not in o7_1["formula"] + " " + o7_1["variables"]:
            raise SystemExit(
                f"{SHEET}: O7.1 no longer names {symbol!r}: "
                f"{o7_1['formula']!r}. The finding that its 648 means and 648 "
                "variances are absent was recorded against this wording.")
    if o7_1["value_range"] != "varies per nutrient":
        raise SystemExit(
            f"{SHEET}: O7.1's range is now {o7_1['value_range']!r}. It used to "
            "be 'varies per nutrient', which is the sheet declining to give "
            "one -- a real range would mean the priors had arrived.")
    if _STANDALONE_NUMBER.search(o7_1["variables"]):
        raise SystemExit(
            f"{SHEET}: O7.1's Variables cell now carries a number: "
            f"{o7_1['variables']!r}. It was pure prose, which is the whole "
            "finding. Read it before changing this check.")

    # The pattern table must not have quietly grown numbers either.
    for pattern in patterns:
        if _STANDALONE_NUMBER.search(pattern["key_nutrient_shifts"]):
            raise SystemExit(
                f"{SHEET}: {pattern['pattern']!r} now states a NUMBER in its "
                f"nutrient shifts: {pattern['key_nutrient_shifts']!r}. That "
                "would be the start of the missing prior table.")

    # THE THREE-WAY DISAGREEMENT ABOUT WHAT THE INTERFACE OFFERS.
    declared_absent = [p for p in patterns if p["ui_status"] == "DECLARED_NOT_IN_UI"]
    if len(declared_absent) != 2:
        raise SystemExit(
            f"{SHEET}: {len(declared_absent)} patterns are marked "
            f"{NOT_IN_UI!r}, and the finding was recorded against two (DASH "
            "and Carnivore).")
    if {p["pattern"] for p in declared_absent} != {"DASH", "Carnivore"}:
        raise SystemExit(
            f"{SHEET}: the patterns absent from the UI are now "
            f"{sorted(p['pattern'] for p in declared_absent)}.")

    unclaimed = data["ui_options_no_pattern_claims"]
    if "Intermittent Fasting" not in unclaimed:
        raise SystemExit(
            f"{SHEET}: the interface no longer offers Intermittent Fasting, "
            "or a pattern now claims it. That was the one UI option with no "
            "prior of any kind -- re-read docs/parameter-gaps.md.")

    # O7.4 needs an encoding for Step 3's serving bands, and nothing gives one.
    o7_4 = by_id["O7.4"]
    if "fruit_serv" not in o7_4["formula"] or "veg_serv" not in o7_4["formula"]:
        raise SystemExit(
            f"{SHEET}: O7.4 is now {o7_4['formula']!r} and no longer reads the "
            "two serving counts the finding was recorded against.")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m sahacore.data.build_onboarding_o7 "
                         "<path-to-workbook>")
    data = extract(sys.argv[1])
    check(data)
    OUT.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")

    patterns = data["patterns"]
    exact = sum(1 for p in patterns if p["ui_status"] == "MATCHES_UI_EXACTLY")
    absent = sum(1 for p in patterns if p["ui_status"] == "DECLARED_NOT_IN_UI")
    print(f"wrote {OUT.name}")
    print(f"  {len(data['equations'])} equations O7.1..O7.4, "
          "each with its engine target")
    print(f"  {len(patterns)} dietary patterns, {len(data['ui_options'])} "
          "options in the interface")
    print(f"    {exact} labels match the UI exactly, {absent} declared "
          f"'{NOT_IN_UI}', {len(patterns) - exact - absent} match nothing")
    print("    UI options no pattern claims: "
          + ", ".join(data["ui_options_no_pattern_claims"]))
    print("  O7.1 supplies NO mu_pattern and NO sigma2_pattern -- 8 patterns "
          "x 81 nutrients, 648 means and 648 variances, all absent")


if __name__ == "__main__":
    main()
