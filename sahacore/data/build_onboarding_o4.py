"""Extracts 'O·O4 Stress Index' into onboarding_o4.json.

Source: v39sEng2.xlsx, sheet 'O·O4 Stress Index'.
'01_IMPORT_MANIFEST' role ONBOARDING, import YES, backend Yes.

    python -m sahacore.data.build_onboarding_o4 <path-to-workbook>

The authority for ONB-004. Onboarding step 8, feeding Layers C and E. Three
tables, and the sheet is the best-specified of the four O-sheets imported so
far: every symbol resolves, every constant is stated, and two of its own
claims can be checked against each other.

    THE INSTRUMENT   ten PSS-10 items, each with its scale, its scoring rule
                     and whether it is reverse-scored
    THE EQUATIONS    O4.1..O4.9, each with its engine target
    THE BANDS        three PSS-10 score ranges with their stated effects

PSS-10, AND THE SHEET SAYS SO IN CAPITALS. Its own header reads "PSS-10
SCORING (CORRECTED: PSS-10, NOT PSS-4)", so an earlier revision used the
four-item form. The ten items are extracted with their reverse flags rather
than assumed from the published instrument, and O4.1's formula is then held
to them: the sheet names {4,5,7,8} as reverse-scored inside the formula AND
in a separate column, and this extractor refuses to import a sheet where
those two disagree. That is the one cross-check the source makes possible,
so it is made.

THE BANDS CORROBORATE THE EQUATIONS, which is rare enough to record. Row 41
says High stress is "+40% damage sensitivity" and O4.5 is
gamma_cort = 1 + 0.4*Theta_AL, which is +40% at Theta_AL = 1. Row 40 says
"approx -5% to -10% repair efficiency across the Moderate band; -15% is the
maximum at Theta_AL=1" and O4.9 is lambda_rep_mod = 1 - 0.15*Theta_AL, which
over the Moderate band's 14-26 gives -5.25% to -9.75%. Both are checked.

NO PARAMETERS TABLE, as on O3: every constant -- 0.4, 0.3, 0.15, the 40-point
denominator, p_stressprot's 0.05 per practice and its 0.20 cap -- is written
inside a formula, so it is transcribed with the formula rather than read from
a registry.

THE FINDING: p_stressprot REACHES NOTHING. O4.3 computes

    stress_idx_adj = max(0, stress_idx_raw - p_stressprot)
    where p_stressprot = 0.05 per practice (cap 0.20)

and its Engine Target column names O4.4, O4.5, O4.6 and O4.7. Not one of
those four reads it. O4.4 is Theta_AL = PSS10/40 -- computed from the total
again, not from the adjusted index -- and O4.5 through O4.9 all read Theta_AL.
So the protective credit for stress-management practices, worth up to 0.20 of
a 0-1 scale, is computed and then consumed by nothing.

This is the same shape as O3.1, where the quality weighting reached none of
its declared consumers. Recorded, not resolved: routing O4.3 into O4.4 would
change every downstream modifier, and that is the author's decision.

AND O4.2 IS O4.4. stress_idx_raw = PSS10/40 and Theta_AL = PSS10/40 are the
same function under two names. Harmless as written -- they agree -- but it is
why the O4.3 break is easy to miss: Theta_AL looks like it descends from the
stress index, and it does not.
"""
import json
import re
import sys
from pathlib import Path

import openpyxl

from sahacore.data.sheet_header import check_header

SHEET = "O·O4 Stress Index"
FIRST_COL = 3
OUT = Path(__file__).parent / "onboarding_o4.json"

ITEM_HEADER_ROW = 9
ITEM_ROWS = range(10, 20)
ITEM_LABELS = ["Item", "Question (abbreviated)", "Scale", "Scoring", "Reverse?"]

EQUATION_HEADER_ROW = 24
EQUATION_ROWS = range(25, 34)
EQUATION_LABELS = ["ID", "Name", "Formula", "Variables", "Units",
                   "Value/Range", "Engine Target"]

BAND_HEADER_ROW = 38
BAND_ROWS = range(39, 42)
BAND_LABELS = ["PSS-10 Score", "Stress Level", "Cortisol/ALI Impact",
               "System Response"]

EXPECTED_ITEMS = 10
EXPECTED_EQUATIONS = 9
EXPECTED_BANDS = 3

# The PSS-10's item scale. Every item must declare it; an item scored on a
# different range would change what the 0-40 total means.
ITEM_SCALE = "0-4"

# '14-26' -> (14, 26)
_BAND = re.compile(r"^(\d+)\s*-\s*(\d+)$")

# "r_i' = 4-r_i for i in {4,5,7,8}" -> the set
_REVERSE_SET = re.compile(r"\{([\d,\s]+)\}")


def _text(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _cell(ws, row: int, offset: int):
    return ws.cell(row=row, column=FIRST_COL + offset).value


def extract(path: str) -> dict:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb[SHEET]
    check_header(ws, SHEET, ITEM_HEADER_ROW, FIRST_COL, ITEM_LABELS)
    check_header(ws, SHEET, EQUATION_HEADER_ROW, FIRST_COL, EQUATION_LABELS)
    check_header(ws, SHEET, BAND_HEADER_ROW, FIRST_COL, BAND_LABELS)

    items = []
    for row in ITEM_ROWS:
        number = _text(_cell(ws, row, 0))
        reverse = _text(_cell(ws, row, 4))
        if number is None or reverse is None:
            raise SystemExit(f"{SHEET}: PSS-10 item at row {row} is incomplete.")
        if reverse not in ("YES", "No"):
            raise SystemExit(
                f"{SHEET}: item {number} row {row} has Reverse? = {reverse!r}, "
                "which is neither 'YES' nor 'No'. Whether an item is "
                "reverse-scored cannot be guessed.")
        items.append({
            "item_number": int(number),
            "source_row": row,
            "question": _text(_cell(ws, row, 1)),
            "scale": _text(_cell(ws, row, 2)),
            "scoring": _text(_cell(ws, row, 3)),
            "reverse_scored": reverse == "YES",
        })

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

    bands = []
    for row in BAND_ROWS:
        score_range = _text(_cell(ws, row, 0))
        matched = _BAND.match(score_range or "")
        if not matched:
            raise SystemExit(
                f"{SHEET}: band at row {row} has score range {score_range!r}, "
                "which is not a 'low-high' pair.")
        bands.append({
            "source_row": row,
            "score_range": score_range,
            "score_min": int(matched.group(1)),
            "score_max": int(matched.group(2)),
            "stress_level": _text(_cell(ws, row, 1)),
            "cortisol_impact": _text(_cell(ws, row, 2)),
            "system_response": _text(_cell(ws, row, 3)),
        })

    wb.close()
    return {"sheet": SHEET, "items": items, "equations": equations,
            "bands": bands}


def check(data: dict) -> None:
    items, equations, bands = data["items"], data["equations"], data["bands"]

    if len(items) != EXPECTED_ITEMS:
        raise SystemExit(f"{SHEET}: expected {EXPECTED_ITEMS} PSS-10 items, "
                         f"got {len(items)}.")
    if [i["item_number"] for i in items] != list(range(1, EXPECTED_ITEMS + 1)):
        raise SystemExit(f"{SHEET}: items are not numbered 1..{EXPECTED_ITEMS}.")
    for item in items:
        if item["scale"] != ITEM_SCALE:
            raise SystemExit(
                f"{SHEET}: item {item['item_number']} is scored {item['scale']!r}, "
                f"not {ITEM_SCALE!r}. The 0-40 total assumes every item shares "
                "one scale.")
        if not item["question"] or not item["scoring"]:
            raise SystemExit(
                f"{SHEET}: item {item['item_number']} has no question or no "
                "scoring rule.")

    if len(equations) != EXPECTED_EQUATIONS:
        raise SystemExit(f"{SHEET}: expected {EXPECTED_EQUATIONS} equations, "
                         f"got {len(equations)}.")
    expected = [f"O4.{n}" for n in range(1, EXPECTED_EQUATIONS + 1)]
    if [e["equation_id"] for e in equations] != expected:
        raise SystemExit(f"{SHEET}: equations are not O4.1..O4.9.")
    by_id = {e["equation_id"]: e for e in equations}
    for equation in equations:
        for field in ("name", "formula", "units", "value_range",
                      "engine_target"):
            if not equation[field]:
                raise SystemExit(
                    f"{SHEET}: {equation['equation_id']} has no {field}.")

    # THE ONE CROSS-CHECK THE SOURCE MAKES POSSIBLE. The reverse-scored items
    # are stated twice: in the Reverse? column, and inside O4.1's formula. If
    # those two ever disagree, the PSS-10 total is wrong and neither statement
    # is more authoritative than the other.
    flagged = {i["item_number"] for i in items if i["reverse_scored"]}
    matched = _REVERSE_SET.search(by_id["O4.1"]["formula"])
    if not matched:
        raise SystemExit(
            f"{SHEET}: O4.1's formula no longer names its reverse-scored items "
            f"as a set: {by_id['O4.1']['formula']!r}")
    in_formula = {int(n) for n in matched.group(1).split(",") if n.strip()}
    if flagged != in_formula:
        raise SystemExit(
            f"{SHEET}: the Reverse? column flags items {sorted(flagged)} but "
            f"O4.1's formula reverses {sorted(in_formula)}. The sheet "
            "contradicts itself about how the PSS-10 is scored.")
    if flagged != {4, 5, 7, 8}:
        raise SystemExit(
            f"{SHEET}: the reverse-scored items are {sorted(flagged)}. The "
            "published PSS-10 reverses 4, 5, 7 and 8, and this sheet's own "
            "header calls the change from PSS-4 a correction -- so a "
            "difference here needs reading, not importing.")

    # The bands must tile the whole 0-40 range with no gap and no overlap, or
    # some PSS-10 total has no stated interpretation.
    if len(bands) != EXPECTED_BANDS:
        raise SystemExit(f"{SHEET}: expected {EXPECTED_BANDS} bands, got "
                         f"{len(bands)}.")
    if bands[0]["score_min"] != 0 or bands[-1]["score_max"] != 40:
        raise SystemExit(
            f"{SHEET}: the bands span {bands[0]['score_min']}-"
            f"{bands[-1]['score_max']}, not the PSS-10's full 0-40.")
    for lower, upper in zip(bands, bands[1:]):
        if upper["score_min"] != lower["score_max"] + 1:
            raise SystemExit(
                f"{SHEET}: bands {lower['score_range']} and "
                f"{upper['score_range']} leave a gap or overlap. Every "
                "PSS-10 total must fall in exactly one band.")

    # THE BANDS CORROBORATE THE EQUATIONS at Theta_AL = 1, which is what the
    # top band means. Checked because a sheet that agrees with itself in two
    # places is evidence, and one that stops agreeing is a change worth
    # stopping for.
    if "+40%" not in bands[-1]["system_response"]:
        raise SystemExit(
            f"{SHEET}: the High band's system response is "
            f"{bands[-1]['system_response']!r}, which no longer states the "
            "+40% that O4.5's 1 + 0.4*Theta_AL produces at Theta_AL = 1.")
    if "0.4 * Theta_AL" not in by_id["O4.5"]["formula"]:
        raise SystemExit(
            f"{SHEET}: O4.5 is now {by_id['O4.5']['formula']!r} and no longer "
            "matches the High band's stated +40% damage sensitivity.")
    if "0.15 * Theta_AL" not in by_id["O4.9"]["formula"]:
        raise SystemExit(
            f"{SHEET}: O4.9 is now {by_id['O4.9']['formula']!r} and no longer "
            "matches the Moderate band's stated -15% maximum.")

    # THE FINDING. O4.3 names four consumers and none of them reads it.
    if by_id["O4.3"]["engine_target"] != "O4.4, O4.5, O4.6, O4.7":
        raise SystemExit(
            f"{SHEET}: O4.3's engine target is now "
            f"{by_id['O4.3']['engine_target']!r}. The finding that its named "
            "consumers do not read it was recorded against the old wording.")
    for equation_id in ("O4.4", "O4.5", "O4.6", "O4.7"):
        equation = by_id[equation_id]
        if "stress_idx_adj" in equation["formula"] + " " + (equation["variables"] or ""):
            raise SystemExit(
                f"{SHEET}: {equation_id} now reads stress_idx_adj. "
                "p_stressprot used to reach none of O4.3's declared "
                "consumers; re-check docs/parameter-gaps.md.")

    # AND O4.2 IS O4.4 -- the same formula under two names. If one of them
    # changes they stop agreeing silently, and Theta_AL feeds five modifiers.
    def _rhs(equation_id: str) -> str:
        return by_id[equation_id]["formula"].partition("=")[2].strip().replace(" ", "")

    if _rhs("O4.2") != _rhs("O4.4") != "PSS10/40":
        raise SystemExit(
            f"{SHEET}: O4.2 and O4.4 used to be the same function of PSS10; "
            f"they are now {_rhs('O4.2')!r} and {_rhs('O4.4')!r}.")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m sahacore.data.build_onboarding_o4 "
                         "<path-to-workbook>")
    data = extract(sys.argv[1])
    check(data)
    OUT.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")
    reverse = [i["item_number"] for i in data["items"] if i["reverse_scored"]]
    print(f"wrote {OUT.name}")
    print(f"  {len(data['items'])} PSS-10 items, {len(reverse)} reverse-scored "
          f"({', '.join(str(n) for n in reverse)}), agreeing with O4.1")
    print(f"  {len(data['equations'])} equations O4.1..O4.9, "
          "each with its engine target")
    print(f"  {len(data['bands'])} bands tiling 0-40: "
          + ", ".join(f"{b['score_range']} {b['stress_level']}"
                      for b in data["bands"]))
    print("  no PARAMETERS table on this sheet -- every constant is inside a "
          "formula")


if __name__ == "__main__":
    main()
