"""Extracts 'O·O6 Family History' into onboarding_o6.json.

Source: v39sEng2.xlsx, sheet 'O·O6 Family History'.
'01_IMPORT_MANIFEST' order 76, role ONBOARDING, import YES, backend Yes.

    python -m sahacore.data.build_onboarding_o6 <path-to-workbook>

The authority for ONB-006. Onboarding step 6, "Bayesian prior shifts",
feeding Layers C, E and O11. Two tables:

    ELEVEN EQUATIONS  O6.1 the general log-hazard shift, O6.2-O6.7 one per
                      condition, O6.8-O6.11 the machinery that applies them
    SIX RR ROWS       each condition's relative risk, its natural log, the
                      study it comes from, and the Z-pathway it moves

THE BEST-SOURCED SHEET IN THE BUILD. Every relative risk names where it came
from -- "EPIC-InterAct consortium", "AHA journal meta-analysis" -- which no
other O-sheet does for any of its constants. That is worth recording, because
most of docs/parameter-gaps.md is about numbers with no provenance.

THREE STATEMENTS OF EVERY RELATIVE RISK, AND THEY ARE CHECKED AGAINST EACH
OTHER. Each of O6.2-O6.7 writes its RR inside the formula ("ln(2.72)"), again
as a pre-computed log ("* 1.000"), and again in its Variables cell
("RR=2.72"); the reference table then states RR and ln(RR) a fourth time. So
this extractor recomputes ln(RR) and holds all of it together. Nothing here
is taken on one cell's word.

WHY THE LOG TOLERANCE IS 1e-3 AND NOT TIGHTER. ln(2.72) = 1.000632, which
rounds to 1.001, and the sheet writes 1.000. The reason is visible once
stated: the T2D relative risk is *e*, whose log is exactly 1, and 2.72 is
that rounded for display. So the ln column is the exact one and the RR column
is the rounded one -- the same "each column is independently rounded" shape
already recorded for '★ Scarring Bistability Guard'. Every other row is
simply correct rounding to three decimals, an error of at most 5e-4; T2D's
6.3e-4 is the only one that is not.

WHAT THE SHEET DOES NOT SUPPLY. O6.8's Pearson-Aitken update and O6.9's
liability-threshold model are written as standard statistics with none of
their inputs given -- no covariance blocks, no population means, no liability
threshold, no genetic/environmental split. They are transcribed as written
and implemented no further than that; see docs/parameter-gaps.md.
"""
import json
import math
import re
import sys
from pathlib import Path

import openpyxl

from sahacore.data.sheet_header import check_header

SHEET = "O·O6 Family History"
FIRST_COL = 3
DATA_DIR = Path(__file__).parent
OUT = DATA_DIR / "onboarding_o6.json"

EQUATION_HEADER_ROW = 9
EQUATION_ROWS = range(10, 21)
EQUATION_LABELS = ["ID", "Name", "Formula", "Variables", "Units",
                   "Value/Range", "Engine Target"]

RR_HEADER_ROW = 25
RR_ROWS = range(26, 32)
RR_LABELS = ["Condition", "RR", "ln(RR)", "Source", "Z-Pathway Affected"]

EXPECTED_EQUATIONS = 11
EXPECTED_CONDITIONS = 6

# O6.2..O6.7 are the per-condition shifts; the rest are general or machinery.
PER_CONDITION = [f"O6.{n}" for n in range(2, 8)]

# 'delta_FH_T2D = I(FH_T2D) * ln(2.72) = I(FH_T2D) * 1.000'
_INDICATOR = re.compile(r"I\((FH[A-Za-z0-9_]*)\)")
_LOG_OF = re.compile(r"ln\((\d+(?:\.\d+)?)\)")
_TRAILING_VALUE = re.compile(r"\*\s*(\d+\.\d+)\s*$")

# 'RR=2.72 (EPIC-InterAct)' in the Variables column.
_RR_IN_VARIABLES = re.compile(r"RR\s*=\s*(\d+(?:\.\d+)?)")

# 'Z1 Glycation, Z6 Insulin Resistance' -> Z1, Z6. This column is the only
# statement in the workbook of which damage pathway each family history
# moves, so O6.10's "FH_relevant per pathway" is answerable from it.
_Z_PATHWAY = re.compile(r"\bZ(\d+)\b")

# ln(2.72) = 1.000632 against a stated 1.000: the RR column is a rounded e.
LOG_TOLERANCE = 1e-3


def _text(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _cell(ws, row: int, offset: int):
    return ws.cell(row=row, column=FIRST_COL + offset).value


def _number(value) -> float:
    """The sheet stores numbers as text on most sheets; this one is mixed."""
    return float(str(value).strip())


def extract(path: str) -> dict:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb[SHEET]
    check_header(ws, SHEET, EQUATION_HEADER_ROW, FIRST_COL, EQUATION_LABELS)
    check_header(ws, SHEET, RR_HEADER_ROW, FIRST_COL, RR_LABELS)

    equations = []
    for row in EQUATION_ROWS:
        equation_id = _text(_cell(ws, row, 0))
        if equation_id is None:
            raise SystemExit(f"{SHEET}: row {row} has no equation id.")
        formula = _text(_cell(ws, row, 2)) or ""
        variables = _text(_cell(ws, row, 3)) or ""

        # ONLY the per-condition equations state a relative risk. O6.1 is the
        # general form and its I(FH) is a placeholder; O6.10's I(FH_relevant)
        # is a different thing again -- whether a history touches a given
        # pathway. Matching either as an indicator would put a placeholder
        # into the registry the module reads its six log-hazards from.
        per_condition = equation_id in PER_CONDITION
        logged = _LOG_OF.search(formula) if per_condition else None
        trailing = _TRAILING_VALUE.search(formula) if per_condition else None
        declared = _RR_IN_VARIABLES.search(variables) if per_condition else None
        indicator = _INDICATOR.search(formula) if per_condition else None
        equations.append({
            "equation_id": equation_id,
            "source_row": row,
            "name": _text(_cell(ws, row, 1)),
            "formula": formula,
            "variables": variables,
            "units": _text(_cell(ws, row, 4)),
            "value_range": _text(_cell(ws, row, 5)),
            "engine_target": _text(_cell(ws, row, 6)),
            # What the formula itself asserts, so check() can hold the three
            # statements of each relative risk against one another.
            "indicator": indicator.group(1) if indicator else None,
            "rr_in_formula": float(logged.group(1)) if logged else None,
            "log_in_formula": float(trailing.group(1)) if trailing else None,
            "rr_in_variables": float(declared.group(1)) if declared else None,
            # The table row this equation is about. Joined by NAME, not by
            # log-hazard: CVD, colon cancer and breast cancer all carry
            # ln(2.0) = 0.693, so a join on the number silently collapses
            # three conditions into one -- which it did, giving CVD the
            # breast-cancer pathway, until a test caught it.
            "condition": (_text(_cell(ws, row, 1)) or "").removeprefix("FH ")
                         if per_condition else None,
        })

    conditions = []
    for row in RR_ROWS:
        condition = _text(_cell(ws, row, 0))
        if condition is None:
            raise SystemExit(f"{SHEET}: RR row {row} has no condition.")
        conditions.append({
            "condition": condition,
            "source_row": row,
            "relative_risk": _number(_cell(ws, row, 1)),
            "log_relative_risk": _number(_cell(ws, row, 2)),
            "source": _text(_cell(ws, row, 3)),
            "z_pathways": _text(_cell(ws, row, 4)),
            "z_pathway_codes": [f"Z{n}" for n in
                                _Z_PATHWAY.findall(_text(_cell(ws, row, 4)) or "")],
        })

    wb.close()
    return {"sheet": SHEET, "equations": equations, "conditions": conditions}


def _ui_inputs() -> set[str]:
    data = json.loads((DATA_DIR / "step_questions.json").read_text(encoding="utf-8"))
    return {question["variable"] for question in data["questions"]}


def check(data: dict) -> None:
    equations, conditions = data["equations"], data["conditions"]

    if len(equations) != EXPECTED_EQUATIONS:
        raise SystemExit(f"{SHEET}: expected {EXPECTED_EQUATIONS} equations, "
                         f"got {len(equations)}.")
    expected = [f"O6.{n}" for n in range(1, EXPECTED_EQUATIONS + 1)]
    if [e["equation_id"] for e in equations] != expected:
        raise SystemExit(f"{SHEET}: equations are not O6.1..O6.11.")
    by_id = {e["equation_id"]: e for e in equations}
    for equation in equations:
        for field in ("name", "formula", "variables", "units", "value_range",
                      "engine_target"):
            if not equation[field]:
                raise SystemExit(
                    f"{SHEET}: {equation['equation_id']} has no {field}.")

    if len(conditions) != EXPECTED_CONDITIONS:
        raise SystemExit(f"{SHEET}: expected {EXPECTED_CONDITIONS} conditions, "
                         f"got {len(conditions)}.")

    # EVERY RELATIVE RISK NAMES ITS SOURCE. No other O-sheet does this for any
    # constant, so a row that stopped citing one would be a real regression.
    for condition in conditions:
        if not condition["source"]:
            raise SystemExit(
                f"{SHEET}: {condition['condition']} no longer cites a source "
                "for its relative risk.")
        if not condition["z_pathway_codes"]:
            raise SystemExit(
                f"{SHEET}: {condition['condition']} names no Z-pathway, so "
                "O6.10 has no way to tell whether it is relevant: "
                f"{condition['z_pathways']!r}")
        if condition["relative_risk"] <= 1.0:
            raise SystemExit(
                f"{SHEET}: {condition['condition']} has RR "
                f"{condition['relative_risk']}, which is not a risk increase. "
                "O6.1 is I(FH)*ln(RR), so RR <= 1 would make family history "
                "protective.")

    # THE ARITHMETIC, RECOMPUTED. See the module docstring on why 1e-3.
    for condition in conditions:
        computed = math.log(condition["relative_risk"])
        if abs(computed - condition["log_relative_risk"]) > LOG_TOLERANCE:
            raise SystemExit(
                f"{SHEET}: {condition['condition']} states "
                f"ln({condition['relative_risk']}) = "
                f"{condition['log_relative_risk']}, but it is {computed:.6f}.")

    # THREE STATEMENTS OF EACH RELATIVE RISK, HELD TOGETHER. The formula's
    # ln(RR), the formula's pre-computed log, and the Variables cell -- then
    # the reference table as a fourth.
    by_log = {c["log_relative_risk"]: c for c in conditions}
    for equation_id in PER_CONDITION:
        equation = by_id[equation_id]
        for field in ("indicator", "rr_in_formula", "log_in_formula",
                      "rr_in_variables"):
            if equation[field] is None:
                raise SystemExit(
                    f"{SHEET}: {equation_id} no longer states its {field}: "
                    f"{equation['formula']!r} / {equation['variables']!r}")
        if equation["rr_in_formula"] != equation["rr_in_variables"]:
            raise SystemExit(
                f"{SHEET}: {equation_id}'s formula uses RR "
                f"{equation['rr_in_formula']} and its Variables cell says "
                f"{equation['rr_in_variables']}.")
        computed = math.log(equation["rr_in_formula"])
        if abs(computed - equation["log_in_formula"]) > LOG_TOLERANCE:
            raise SystemExit(
                f"{SHEET}: {equation_id} pre-computes "
                f"ln({equation['rr_in_formula']}) as "
                f"{equation['log_in_formula']}, but it is {computed:.6f}.")
        if equation["log_in_formula"] not in by_log:
            raise SystemExit(
                f"{SHEET}: {equation_id}'s log-hazard "
                f"{equation['log_in_formula']} matches no row of the RR "
                "reference table.")

    # THE NAME JOIN, ASSERTED. Each per-condition equation is named "FH " +
    # its table row's condition, exactly. That is the only unambiguous key
    # between the two tables, since three conditions share ln(2.0) = 0.693.
    named = {c["condition"] for c in conditions}
    for equation_id in PER_CONDITION:
        equation = by_id[equation_id]
        if equation["condition"] not in named:
            raise SystemExit(
                f"{SHEET}: {equation_id} is named {equation['name']!r}, which "
                f"does not correspond to any RR table row {sorted(named)}. "
                "The two tables are joined on this name.")
        row = next(c for c in conditions if c["condition"] == equation["condition"])
        if row["relative_risk"] != equation["rr_in_formula"]:
            raise SystemExit(
                f"{SHEET}: {equation_id} uses RR {equation['rr_in_formula']} "
                f"and the table gives {row['relative_risk']} for "
                f"{row['condition']!r}.")
    if len({by_id[e]["condition"] for e in PER_CONDITION}) != EXPECTED_CONDITIONS:
        raise SystemExit(
            f"{SHEET}: the six equations do not name six distinct conditions.")

    # A placeholder must never reach the registry the module reads its six
    # log-hazards from: O6.1's I(FH) and O6.10's I(FH_relevant) both look
    # like indicators and are not.
    stated = [e["equation_id"] for e in equations if e["indicator"] is not None]
    if stated != PER_CONDITION:
        raise SystemExit(
            f"{SHEET}: relative risks were extracted from {stated}, expected "
            f"exactly {PER_CONDITION}.")

    # Every condition in the table must have an equation, and vice versa.
    table_logs = {c["log_relative_risk"] for c in conditions}
    equation_logs = {by_id[e]["log_in_formula"] for e in PER_CONDITION}
    if table_logs != equation_logs:
        raise SystemExit(
            f"{SHEET}: the RR table's log-hazards {sorted(table_logs)} do not "
            f"match the equations' {sorted(equation_logs)}.")

    # STEP 6 MUST COLLECT EVERY FAMILY HISTORY AN EQUATION READS. Six
    # checkboxes, six per-condition equations -- and the check is possible
    # only because 'O·Step-by-Step Questions' is imported.
    collected = _ui_inputs()
    for equation_id in PER_CONDITION:
        indicator = by_id[equation_id]["indicator"]
        if indicator not in collected:
            raise SystemExit(
                f"{SHEET}: {equation_id} reads {indicator!r} and the "
                "onboarding questionnaire does not collect it.")
    asked = {name for name in collected if name.startswith("FH_")}
    read = {by_id[e]["indicator"] for e in PER_CONDITION}
    if asked != read:
        raise SystemExit(
            f"{SHEET}: Step 6 collects {sorted(asked)} and the equations read "
            f"{sorted(read)}. A family history collected and never read is a "
            "question asked for nothing; one read and never collected is an "
            "equation that cannot run.")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m sahacore.data.build_onboarding_o6 "
                         "<path-to-workbook>")
    data = extract(sys.argv[1])
    check(data)
    OUT.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")

    conditions = data["conditions"]
    print(f"wrote {OUT.name}")
    print(f"  {len(data['equations'])} equations O6.1..O6.11, "
          "each with its engine target")
    print(f"  {len(conditions)} relative risks, every one citing a source, "
          "and every ln(RR) recomputed")
    print("  " + ", ".join(f"{c['condition']} {c['relative_risk']}"
                           for c in conditions))
    pathways = sorted({code for c in conditions for code in c["z_pathway_codes"]})
    print(f"  {len(pathways)} Z-pathways moved by a family history: "
          + ", ".join(pathways))
    print("  checked against the UI contract: Step 6 collects exactly the six "
          "histories the equations read")


if __name__ == "__main__":
    main()
