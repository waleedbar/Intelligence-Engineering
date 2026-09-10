"""Extracts 'O·O2 MVPA Prior' into onboarding_o2.json.

Source: v39sEng2.xlsx, sheet 'O·O2 MVPA Prior'.
'01_IMPORT_MANIFEST' order 72, role ONBOARDING, import YES, backend Yes.

    python -m sahacore.data.build_onboarding_o2 <path-to-workbook>

The authority for ONB-002. Two tables: an INPUT ENCODING that turns the
onboarding screen's ordinal answers into numbers, and eight equations.

    O2.1  MVPA_wk    = (f_mod * dur) + 2 * (f_vig * dur)
    O2.2  MVPA_day   = MVPA_wk / 7
    O2.3  e_MVPA     = 1 - min(1, MVPA_wk / 300)
    O2.4  PA_benefit = 100 * (1 - HR_Arem)
    O2.5  rho_modified = rho_pop * (1 + 0.5*(PA/100 - 0.5))
    O2.6  METmin_wk  = 4.5*(f_mod*dur) + 7.5*(f_vig*dur)
    O2.7  METmin_day = METmin_wk / 7
    O2.8  eta_sed    = I(sitting_hrs > 6) * 0.15

THE INPUT ENCODING IS DATA, NOT UI TRIVIA. "Frequency: 3-4" becomes 3.5
sessions a week; "Duration: <30 min" becomes 20 minutes, which the sheet
labels a "Conservative midpoint" rather than the arithmetic one. Those
choices decide what a user's answers mean, so they are extracted with the
sheet's own reason attached and read by the module rather than retyped.

TWO OF THE EIGHT ARE NOT COMPUTABLE, and it is worth being exact about why.

  O2.4 needs HR_Arem, which the sheet describes -- "hazard ratio from
  dose-response curve, Anchored at 150-300 min/wk zone" -- and never gives.
  No formula, no table, no parameter row, here or anywhere in the workbook.

  O2.5 needs O2.4's output and rho_pop, "population mean repair". `rho_pop`
  appears twice in the whole workbook: in O2.5 itself and in the copy of
  O2.5 on 'P1 Onboarding'. It is not in the 192-parameter registry nor in
  the +20 extension.

AND THE CONSOLIDATED SHEETS GIVE O2.4 A DIFFERENT FORMULA. 'O · Onboarding
Canonical' and 'EQ · Canonical Build Rows' both state ONB-002 as

    PA_benefit = 100*(1-exp(-MET_min_week/K_PA))

which is a saturating exponential in MET-minutes, not an epidemiological
hazard ratio anchored at a dose zone. The two do not reduce to each other.
`K_PA` also appears exactly twice in the workbook -- in those two cells --
and in neither parameter registry.

So PA_benefit has two incompatible definitions and neither is computable.
Both are recorded, with their witnesses, and neither is implemented. See
docs/parameter-gaps.md. PA_benefit feeds Layer C's repair rate through
'O·Engine Connections', so guessing would not stay contained.
"""
import json
import re
import sys
from pathlib import Path

import openpyxl

SHEET = "O·O2 MVPA Prior"
FIRST_COL = 3
OUT = Path(__file__).parent / "onboarding_o2.json"

ENCODING_HEADER_ROW = 9
ENCODING_ROWS = range(10, 21)
ENCODING_LABELS = ["UI Selection", "Mapped Value", "Variable", "Source"]

EQUATION_HEADER_ROW = 25
EQUATION_ROWS = range(26, 34)
EQUATION_LABELS = ["ID", "Name", "Formula", "Variables", "Units", "Value/Range"]

EXPECTED_EQUATIONS = 8
EXPECTED_ENCODINGS = 11

# Equations that cannot be implemented, and the symbol each one waits on.
# Written by hand: an extractor that inferred "unresolvable" from a formula
# would either miss cases or invent them.
UNRESOLVED: dict[str, dict] = {
    "O2.4": {
        "missing_symbol": "HR_Arem",
        "reason": (
            "The authority sheet describes HR_Arem as a 'hazard ratio from "
            "dose-response curve, Anchored at 150-300 min/wk zone' and never "
            "gives it -- no formula, no table, no parameter row anywhere in "
            "the workbook."),
        "conflicting_definition": {
            "formula": "PA_benefit = 100*(1-exp(-MET_min_week/K_PA))",
            "declared_by": ["O · Onboarding Canonical",
                            "EQ · Canonical Build Rows"],
            "missing_symbol": "K_PA",
            "note": (
                "A saturating exponential in MET-minutes, not a hazard ratio "
                "anchored at a dose zone; the two are different functions. "
                "K_PA appears exactly twice in the workbook -- in these two "
                "cells -- and in neither parameter registry."),
        },
    },
    "O2.5": {
        "missing_symbol": "rho_pop",
        "reason": (
            "Needs O2.4's output and rho_pop, 'population mean repair'. "
            "rho_pop appears twice in the workbook: in O2.5 and in the copy "
            "of O2.5 on 'P1 Onboarding'. It is in neither parameter registry."),
        "conflicting_definition": None,
    },
}


def _text(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _cell(ws, row: int, offset: int):
    return ws.cell(row=row, column=FIRST_COL + offset).value


_LEADING_NUMBER = re.compile(r"-?\d+(?:\.\d+)?")


def _mapped_number(text: str, where: str) -> float | int:
    """The number inside a mapped-value cell.

    The cells are written for a reader -- '1.5 sessions/wk', '20 min/session',
    'eta_sed = 0.15 (penalty active)'. Each contains exactly one number, and
    that number is what the encoding means. Parsed here rather than in the
    module, so the module never sees a string where it expects a quantity,
    and so a cell that stops carrying exactly one number fails the extract.
    """
    found = _LEADING_NUMBER.findall(text)
    if len(found) != 1:
        raise SystemExit(
            f"{where}: mapped value {text!r} contains {len(found)} numbers, "
            "expected exactly one.")
    value = found[0]
    return int(value) if "." not in value else float(value)


def _check_header(ws, row: int, labels: list[str]) -> None:
    for offset, expected in enumerate(labels):
        found = _text(_cell(ws, row, offset))
        if found != expected:
            raise SystemExit(
                f"{SHEET}: header row {row} column {FIRST_COL + offset} reads "
                f"{found!r}, expected {expected!r}.")


def extract(path: str) -> dict:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb[SHEET]

    _check_header(ws, ENCODING_HEADER_ROW, ENCODING_LABELS)
    _check_header(ws, EQUATION_HEADER_ROW, EQUATION_LABELS)

    encodings = []
    for row in ENCODING_ROWS:
        selection = _text(_cell(ws, row, 0))
        if selection is None:
            continue
        # 'Frequency: 3-4' -> field 'Frequency', option '3-4'.
        field, _, option = selection.partition(":")
        encodings.append({
            "source_row": row,
            "ui_selection": selection,
            "field": field.strip(),
            "option": option.strip(),
            "mapped_value": _text(_cell(ws, row, 1)),
            "numeric_value": _mapped_number(
                _text(_cell(ws, row, 1)) or "",
                f"{SHEET} row {row} ({selection})"),
            "variable": _text(_cell(ws, row, 2)),
            "source": _text(_cell(ws, row, 3)),
        })

    equations = []
    for row in EQUATION_ROWS:
        equation_id = _text(_cell(ws, row, 0))
        if equation_id is None:
            raise SystemExit(f"{SHEET}: equation row {row} has no id.")
        unresolved = UNRESOLVED.get(equation_id)
        equations.append({
            "equation_id": equation_id,
            "source_row": row,
            "name": _text(_cell(ws, row, 1)),
            "formula": _text(_cell(ws, row, 2)),
            "variables": _text(_cell(ws, row, 3)),
            "units": _text(_cell(ws, row, 4)),
            "value_range": _text(_cell(ws, row, 5)),
            "computable": unresolved is None,
            "unresolved": unresolved,
        })

    wb.close()
    return {"sheet": SHEET, "input_encoding": encodings, "equations": equations}


def check(data: dict) -> None:
    equations = data["equations"]
    if len(equations) != EXPECTED_EQUATIONS:
        raise SystemExit(f"{SHEET}: expected {EXPECTED_EQUATIONS} equations, "
                         f"got {len(equations)}.")
    expected = [f"O2.{n}" for n in range(1, EXPECTED_EQUATIONS + 1)]
    if [e["equation_id"] for e in equations] != expected:
        raise SystemExit(f"{SHEET}: equations are not O2.1..O2.{EXPECTED_EQUATIONS}.")
    for equation in equations:
        for field in ("name", "formula", "units", "value_range"):
            if not equation[field]:
                raise SystemExit(
                    f"{SHEET}: {equation['equation_id']} has no {field}.")

    blocked = {e["equation_id"] for e in equations if not e["computable"]}
    if blocked != set(UNRESOLVED):
        raise SystemExit(f"{SHEET}: blocked equations are {sorted(blocked)}, "
                         f"expected {sorted(UNRESOLVED)}.")

    # The symbol each blocked equation waits on must still be the one the
    # formula actually uses -- otherwise the recorded gap has drifted from
    # the source it describes.
    for equation in equations:
        if equation["computable"]:
            continue
        symbol = equation["unresolved"]["missing_symbol"]
        if symbol not in equation["formula"] and symbol not in equation["variables"]:
            raise SystemExit(
                f"{SHEET}: {equation['equation_id']} is recorded as waiting on "
                f"{symbol!r}, which no longer appears in it.")

    if len(data["input_encoding"]) != EXPECTED_ENCODINGS:
        raise SystemExit(f"{SHEET}: expected {EXPECTED_ENCODINGS} encoding "
                         f"rows, got {len(data['input_encoding'])}.")
    fields = {e["field"] for e in data["input_encoding"]}
    if fields != {"Frequency", "Duration", "Activity"}:
        raise SystemExit(f"{SHEET}: encoding fields are {sorted(fields)}.")
    for encoding in data["input_encoding"]:
        if encoding["numeric_value"] is None:
            raise SystemExit(
                f"{SHEET}: encoding row {encoding['source_row']} has no "
                "numeric value.")
        if not encoding["mapped_value"] or not encoding["source"]:
            raise SystemExit(
                f"{SHEET}: encoding row {encoding['source_row']} is missing a "
                "mapped value or the reason for it.")

    # O2.1 counts vigorous minutes double and O2.6 weights them by MET. Both
    # relationships are stated in the formulas and are what makes the two
    # equations different rather than redundant.
    o2_1 = next(e for e in equations if e["equation_id"] == "O2.1")["formula"]
    if "2 * (f_vig" not in o2_1.replace("2*(f_vig", "2 * (f_vig"):
        raise SystemExit(f"{SHEET}: O2.1 no longer doubles vigorous minutes: "
                         f"{o2_1!r}")
    o2_6 = next(e for e in equations if e["equation_id"] == "O2.6")["formula"]
    for constant in ("4.5", "7.5"):
        if constant not in o2_6:
            raise SystemExit(f"{SHEET}: O2.6 no longer carries {constant}: "
                             f"{o2_6!r}")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m sahacore.data.build_onboarding_o2 "
                         "<path-to-workbook>")
    data = extract(sys.argv[1])
    check(data)
    OUT.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")

    computable = [e["equation_id"] for e in data["equations"] if e["computable"]]
    blocked = [e["equation_id"] for e in data["equations"] if not e["computable"]]
    print(f"wrote {OUT.name}")
    print(f"  {len(data['input_encoding'])} input encodings over "
          f"{len({e['field'] for e in data['input_encoding']})} fields")
    print(f"  computable: {len(computable)}  {computable}")
    print(f"  blocked:    {len(blocked)}  {blocked} -- "
          + ", ".join(f"{k} needs {v['missing_symbol']}"
                      for k, v in UNRESOLVED.items()))


if __name__ == "__main__":
    main()
