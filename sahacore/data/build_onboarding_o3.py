"""Extracts 'O·O3 Sleep Deficit' into onboarding_o3.json.

Source: v39sEng2.xlsx, sheet 'O·O3 Sleep Deficit'.
'01_IMPORT_MANIFEST' order 73, role ONBOARDING, import YES, backend Yes.

    python -m sahacore.data.build_onboarding_o3 <path-to-workbook>

The authority for ONB-003. Eight equations, from onboarding step 9:

    O3.1  SDS = (7 - sleep_hrs)/7 * quality_factor,
          quality_factor = 1 - (quality_rating - 1)/4
    O3.2  k_inflam_mod = 1 + 0.081 * deficit_hrs,
          deficit_hrs = max(0, 7 - sleep_hrs)
    O3.3  k_IR_sleep = 1 - 0.045 * deficit_hrs
    O3.4  FSR_mod = 1 - 0.18 * I(deficit > 1)
    O3.5  sleep_def = 0 if 7<=h<=9; min(1,(7-h)/2) if h<7;
                      min(1,(h-9)/2) if h>9
    O3.6  e_sched = (consistency_score - 1)/3
    O3.7  mu_sleep = 0.5*sleep_def + 0.3*e_sleepqual + 0.2*e_sched
    O3.8  sleep_minutes = 60 * sleep_hrs

NO PARAMETERS TABLE. Unlike O1, this sheet has none: every constant lives
inside a formula -- the 7-hour threshold, 0.081, 0.045, 0.18, the 7-9 hour
window, O3.7's composite weights. So there is nothing here to read from a
registry, and the module transcribes them with the equations. That is a
difference in the SOURCE, not a relaxation of the rule: a value the sheet
puts in a formula is part of the formula.

TWO THINGS O3 GETS RIGHT THAT O1 AND O2 DID NOT.

  O3.7 uses e_sleepqual, and defines it in the same row: "e_sleepqual =
  (5-quality)/4". Compare O1.9, which weights e_WHtR and e_BMI at 0.30 and
  0.20 and defines neither anywhere in the workbook.

  O3.6 carries its ordinal encoding inline -- "Very Inconsistent=1,
  Somewhat=2, Fairly=3, Very Consistent=4" -- rather than in a separate
  table as O2 does. Extracted into `ordinal_encodings` so the module reads
  it rather than retyping it.

TWO DEFINITIONS OF SLEEP DEFICIT, AND THEY ARE NOT THE SAME FUNCTION.
O3.1's SDS and O3.5's sleep_def both measure sleep shortfall and disagree:

  * SDS is signed. At 9 hours it is (7-9)/7 = -0.29 times the quality
    factor, so oversleeping makes it NEGATIVE. Its declared range is 0-1.
  * sleep_def is two-sided and clamped: zero across 7-9 hours, rising
    either side, never negative.

Both are extracted as written. The disagreement is recorded rather than
resolved -- see docs/parameter-gaps.md -- and the module implements each
under its own name so a caller cannot take one for the other.
"""
import json
import re
import sys
from pathlib import Path

import openpyxl

from sahacore.data.sheet_header import check_header

SHEET = "O·O3 Sleep Deficit"
FIRST_COL = 3
OUT = Path(__file__).parent / "onboarding_o3.json"

HEADER_ROW = 9
DATA_ROWS = range(10, 18)
LABELS = ["ID", "Name", "Formula", "Variables", "Units", "Value/Range",
          "Engine Target"]

EXPECTED_EQUATIONS = 8

# 'Very Inconsistent=1, Somewhat=2, Fairly=3, Very Consistent=4' inside a
# formula cell. The pairs are what a user's answer means, so they are pulled
# out rather than left as prose for the module to re-read.
_ORDINAL = re.compile(r"([A-Za-z][A-Za-z /-]*?)\s*=\s*(\d+(?:\.\d+)?)")

# The equations whose formula cell carries an inline ordinal scale.
ORDINAL_EQUATIONS = {"O3.6"}


def _text(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _cell(ws, row: int, offset: int):
    return ws.cell(row=row, column=FIRST_COL + offset).value


def _ordinal_scale(formula: str) -> list[dict]:
    """The 'where X=1, Y=2, ...' clause of a formula, as pairs."""
    _, _, clause = formula.partition("where")
    if not clause.strip():
        return []
    return [{"option": option.strip(), "value": float(value)
             if "." in value else int(value)}
            for option, value in _ORDINAL.findall(clause)]


def extract(path: str) -> dict:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb[SHEET]
    check_header(ws, SHEET, HEADER_ROW, FIRST_COL, LABELS)

    equations = []
    for row in DATA_ROWS:
        equation_id = _text(_cell(ws, row, 0))
        if equation_id is None:
            raise SystemExit(f"{SHEET}: row {row} has no equation id.")
        formula = _text(_cell(ws, row, 2)) or ""
        equations.append({
            "equation_id": equation_id,
            "source_row": row,
            "name": _text(_cell(ws, row, 1)),
            "formula": formula,
            "variables": _text(_cell(ws, row, 3)),
            "units": _text(_cell(ws, row, 4)),
            "value_range": _text(_cell(ws, row, 5)),
            "engine_target": _text(_cell(ws, row, 6)),
            "ordinal_scale": (_ordinal_scale(formula)
                              if equation_id in ORDINAL_EQUATIONS else []),
        })

    wb.close()
    return {"sheet": SHEET, "equations": equations}


def check(data: dict) -> None:
    equations = data["equations"]
    if len(equations) != EXPECTED_EQUATIONS:
        raise SystemExit(f"{SHEET}: expected {EXPECTED_EQUATIONS} equations, "
                         f"got {len(equations)}.")
    expected = [f"O3.{n}" for n in range(1, EXPECTED_EQUATIONS + 1)]
    if [e["equation_id"] for e in equations] != expected:
        raise SystemExit(f"{SHEET}: equations are not O3.1..O3.8.")

    by_id = {e["equation_id"]: e for e in equations}
    for equation in equations:
        for field in ("name", "formula", "units", "value_range",
                      "engine_target"):
            if not equation[field]:
                raise SystemExit(
                    f"{SHEET}: {equation['equation_id']} has no {field}.")

    # The seven-hour threshold appears in three equations and must be the
    # same number in all of them, or 'deficit' means different things to
    # O3.2, O3.3 and O3.5.
    for equation_id in ("O3.1", "O3.2", "O3.5"):
        if "7" not in by_id[equation_id]["formula"]:
            raise SystemExit(
                f"{SHEET}: {equation_id} no longer carries the 7-hour "
                f"threshold: {by_id[equation_id]['formula']!r}")

    # O3.4 is a step, not a ramp, and the sheet says so in its range.
    if by_id["O3.4"]["value_range"] != "0.82 or 1.0":
        raise SystemExit(
            f"{SHEET}: O3.4's range is now {by_id['O3.4']['value_range']!r}; "
            "it was a two-valued step.")

    # O3.7's weights are a stated composite and must still sum to one.
    weights = [float(w) for w in re.findall(r"(\d\.\d)\*", by_id["O3.7"]["formula"])]
    if len(weights) != 3 or abs(sum(weights) - 1.0) > 1e-12:
        raise SystemExit(
            f"{SHEET}: O3.7's weights are {weights}, which do not sum to 1.")

    # e_sleepqual is defined in O3.7's own Variables cell. If that ever stops
    # being true it joins e_WHtR and e_BMI as a symbol nothing defines, and
    # the module must stop deriving it.
    if "e_sleepqual=(5-quality)/4" not in by_id["O3.7"]["variables"].replace(" ", ""):
        raise SystemExit(
            f"{SHEET}: O3.7 no longer defines e_sleepqual inline: "
            f"{by_id['O3.7']['variables']!r}")

    # O3.7 mixes two badness indices with one goodness index. sleep_def and
    # e_sleepqual both run 0 = good, 1 = bad; e_sched runs the other way,
    # 1 = very consistent. So the best possible sleeper scores 0.2 and the
    # worst 0.8, and the sheet's declared range of 0-1 is unreachable at both
    # ends. Asserted rather than corrected -- flipping a term would change
    # what a Layer E state prior means. See docs/parameter-gaps.md.
    if "0.2*e_sched" not in by_id["O3.7"]["formula"].replace(" ", ""):
        raise SystemExit(
            f"{SHEET}: O3.7 no longer weights e_sched at 0.2: "
            f"{by_id['O3.7']['formula']!r}. The polarity finding was recorded "
            "against that term.")
    if "(consistency_score-1)/3" not in by_id["O3.6"]["formula"].replace(" ", ""):
        raise SystemExit(
            f"{SHEET}: O3.6 is no longer (consistency_score - 1)/3, so its "
            "polarity may have been corrected. Re-read it and re-check O3.7.")

    # O3.1 declares O3.2, O3.3 and O3.4 as its consumers, and none of the
    # three reads SDS -- they all compute from deficit_hrs, which carries no
    # quality weighting. Recorded, not corrected. If a later revision makes
    # any of them read SDS the finding is resolved and must be re-read rather
    # than left standing in docs/parameter-gaps.md.
    if by_id["O3.1"]["engine_target"] != "O3.2, O3.3, O3.4, O11":
        raise SystemExit(
            f"{SHEET}: O3.1's engine target is now "
            f"{by_id['O3.1']['engine_target']!r}. The finding that its named "
            "consumers do not read it was recorded against the old wording.")
    for equation_id in ("O3.2", "O3.3", "O3.4"):
        equation = by_id[equation_id]
        if "SDS" in equation["formula"] + " " + (equation["variables"] or ""):
            raise SystemExit(
                f"{SHEET}: {equation_id} now reads SDS. O3.1's quality "
                "weighting used to reach none of its declared consumers; "
                "re-check docs/parameter-gaps.md.")

    scale = by_id["O3.6"]["ordinal_scale"]
    if [s["value"] for s in scale] != [1, 2, 3, 4]:
        raise SystemExit(
            f"{SHEET}: O3.6's consistency scale is {scale}, expected four "
            "ordered options numbered 1 to 4.")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m sahacore.data.build_onboarding_o3 "
                         "<path-to-workbook>")
    data = extract(sys.argv[1])
    check(data)
    OUT.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    scale = next(e for e in data["equations"]
                 if e["equation_id"] == "O3.6")["ordinal_scale"]
    print(f"wrote {OUT.name}")
    print(f"  {len(data['equations'])} equations O3.1..O3.8, "
          "each with its engine target")
    print(f"  {len(scale)} inline ordinal options: "
          + ", ".join(f"{s['option']}={s['value']}" for s in scale))
    print("  no PARAMETERS table on this sheet -- every constant is inside a "
          "formula")


if __name__ == "__main__":
    main()
