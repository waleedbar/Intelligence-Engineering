"""Extracts 'O·O5 Substance Exposure' into onboarding_o5.json.

Source: v39sEng2.xlsx, sheet 'O·O5 Substance Exposure'.
'01_IMPORT_MANIFEST' order 75, role ONBOARDING, import YES, backend Yes.

    python -m sahacore.data.build_onboarding_o5 <path-to-workbook>

The authority for ONB-005. Onboarding steps 3 (sugary drinks) and 10
(tobacco, alcohol), feeding Layers C and E. Seven equations:

    O5.1  lambda_smoke   = 1 + 0.02 * pack_years
    O5.2  lambda_alcohol = 1 + 0.01 * units_week
    O5.3  k_ox           = lambda_smoke * lambda_alcohol
    O5.4  GSH_depletion  = 0.8 * I(drinks_wk >= 8)
    O5.5  e_SSB          = min(1, SSB_serv_day / 1.5)
    O5.6  e_alcohol      = min(1, max(0, (drinks_wk - T)/T)), T = 7 F / 14 M
    O5.7  tobacco_idx    : Never=0 ... Daily=1.0

FOUR ENCODINGS, ALL READ RATHER THAN RETYPED. This sheet turns a user's
answer into a number four separate times -- pack_years, units_week,
tobacco_idx and O5.5's SSB midpoints -- and each mapping is the sheet's
decision about what an answer is worth. They are extracted into `encodings`
so the module reads them.

THIS IS THE FIRST SHEET IMPORTED AFTER ITS OWN UI CONTRACT. 'O·Step-by-Step
Questions' is manifest order 70 and was imported before this one, so for the
first time an O-sheet's inputs can be checked against what the interface
actually collects rather than against the same sheet's Variables column. Three
of the four findings below exist only because that check is now possible.

WHAT THE SHEET CORROBORATES

  O5.2's alcohol midpoints are exact. Step 10 offers 0 / 1-3 / 4-7 / 8+ and
  O5.2 encodes 0 / 2 / 5.5 / 10 -- 2 and 5.5 are the true midpoints of 1-3
  and 4-7. The sheet demonstrably knows how to write a midpoint, which is
  what makes finding 1 below a discrepancy rather than a convention.

  O5.3's declared range. k_ox = lambda_smoke * lambda_alcohol tops out at
  1.4 * 1.1 = 1.54, and the sheet declares "1.0-1.5+".

FOUR FINDINGS, none corrected. All in docs/parameter-gaps.md.

  1. O5.5's "midpoints" are not midpoints. Its Variables cell reads
     "(midpoint: 0/0.5/1.75/3)" against Step 3's bands 0 / 1-2 / 3-4 / 5+,
     whose true midpoints are 0 / 1.5 / 3.5. It moves a Layer C input: a
     user answering "1-2 drinks a day" scores e_SSB = 0.333 instead of 1.0.

  2. The five tobacco categories are not what the UI collects. O5.1 and
     O5.7 both map Never / Former(>1yr) / Former(<1yr) / Occasional / Daily.
     Step 10 asks TWO questions -- smoke_status (Yes daily / Yes
     occasionally / No) and quit_time -- and neither offers "Former". The
     five categories must be a join of the two, and no sheet gives the rule.

  3. O5.1 and O5.7 rank the same five categories differently. pack_years
     ties Former(<1yr) and Occasional at 5; tobacco_idx separates them,
     0.35 against 0.5. One answer, two indices, two orderings.

  4. O5.6's male branch is unreachable. The UI collects alcohol once, so
     units_week and drinks_wk are the same answer, and its largest encoded
     value is 10. min(1, max(0, (10-14)/14)) is 0, so a male scores zero on
     hepatic-fibrosis alcohol exposure for every answer the UI accepts;
     a female tops out at 0.43. Both are declared 0-1.
"""
import json
import re
import sys
from pathlib import Path

import openpyxl

from sahacore.data.sheet_header import check_header

SHEET = "O·O5 Substance Exposure"
FIRST_COL = 3
DATA_DIR = Path(__file__).parent
OUT = DATA_DIR / "onboarding_o5.json"

HEADER_ROW = 9
DATA_ROWS = range(10, 17)
LABELS = ["ID", "Name", "Formula", "Variables", "Units", "Value/Range",
          "Engine Target"]

EXPECTED_EQUATIONS = 7

# equation -> (what the encoding produces, the marker its list follows).
# O5.1 and O5.2 write "where:"; O5.7 leads with the variable's own name.
LABELLED_ENCODINGS = {
    "O5.1": ("pack_years", "where:"),
    "O5.2": ("units_week", "where:"),
    "O5.7": ("tobacco_idx", "tobacco_idx:"),
}

# 'Never=0', 'Former(>1yr)=2', '1-3=2', '8+=10'. The option may carry
# brackets, comparison signs and digits, so it is everything up to the '='
# that is not a separator.
_PAIR = re.compile(r"([^,=]+?)\s*=\s*(-?\d+(?:\.\d+)?)")

# O5.5 puts its encoding in the Variables column and gives no labels:
# 'SSB_serv_day from Step 3 (midpoint: 0/0.5/1.75/3)'.
_MIDPOINTS = re.compile(r"midpoint:\s*([\d./]+)")

# The five smoking categories both tobacco equations encode.
SMOKE_CATEGORIES = {"Never", "Former(>1yr)", "Former(<1yr)", "Occasional",
                    "Daily"}


def _text(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _cell(ws, row: int, offset: int):
    return ws.cell(row=row, column=FIRST_COL + offset).value


def _number(text: str) -> float | int:
    value = float(text)
    return int(value) if value.is_integer() and "." not in text else value


def _labelled(text: str, marker: str) -> list[dict]:
    _, found, clause = text.partition(marker)
    if not found:
        return []
    return [{"option": option.strip(), "value": _number(value),
             "ordinal_position": position}
            for position, (option, value) in enumerate(_PAIR.findall(clause),
                                                       start=1)]


def extract(path: str) -> dict:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb[SHEET]
    check_header(ws, SHEET, HEADER_ROW, FIRST_COL, LABELS)

    equations, encodings = [], []
    for row in DATA_ROWS:
        equation_id = _text(_cell(ws, row, 0))
        if equation_id is None:
            raise SystemExit(f"{SHEET}: row {row} has no equation id.")
        formula = _text(_cell(ws, row, 2)) or ""
        variables = _text(_cell(ws, row, 3))
        equations.append({
            "equation_id": equation_id,
            "source_row": row,
            "name": _text(_cell(ws, row, 1)),
            "formula": formula,
            "variables": variables,
            "units": _text(_cell(ws, row, 4)),
            "value_range": _text(_cell(ws, row, 5)),
            "engine_target": _text(_cell(ws, row, 6)),
        })

        if equation_id in LABELLED_ENCODINGS:
            encodes, marker = LABELLED_ENCODINGS[equation_id]
            pairs = _labelled(formula, marker)
            if not pairs:
                raise SystemExit(
                    f"{SHEET}: {equation_id} no longer carries a "
                    f"{marker!r} encoding: {formula!r}")
            for pair in pairs:
                encodings.append({"equation_id": equation_id,
                                  "encodes": encodes, **pair})

        # O5.5's encoding is unlabelled and lives in the Variables column.
        # Recorded with option = None rather than paired with Step 3's bands
        # here: what each number means is the sheet's to say, and it does not.
        if equation_id == "O5.5":
            matched = _MIDPOINTS.search(variables or "")
            if not matched:
                raise SystemExit(
                    f"{SHEET}: O5.5 no longer declares SSB midpoints: "
                    f"{variables!r}")
            for position, value in enumerate(matched.group(1).split("/"),
                                             start=1):
                encodings.append({"equation_id": "O5.5",
                                  "encodes": "SSB_serv_day",
                                  "option": None,
                                  "value": _number(value),
                                  "ordinal_position": position})

    wb.close()
    return {"sheet": SHEET, "equations": equations, "encodings": encodings}


def _ui_options(variable: str) -> list[str]:
    """The answer options 'O·Step-by-Step Questions' offers for a variable."""
    data = json.loads((DATA_DIR / "step_questions.json").read_text(encoding="utf-8"))
    matching = [q for q in data["questions"] if q["variable"] == variable]
    if len(matching) != 1:
        raise SystemExit(
            f"{SHEET}: the UI contract has {len(matching)} questions for "
            f"{variable!r}, expected exactly one.")
    return matching[0]["answer_options"]


def _band_midpoint(band: str) -> float | None:
    """The midpoint of '1-3'. None for an open band like '8+'."""
    band = band.split()[0] if " " in band else band     # '8+ drinks' -> '8+'
    if band.endswith("+"):
        return None
    if "-" in band:
        low, high = (float(part) for part in band.split("-"))
        return (low + high) / 2
    return float(band)


def check(data: dict) -> None:
    equations = data["equations"]
    if len(equations) != EXPECTED_EQUATIONS:
        raise SystemExit(f"{SHEET}: expected {EXPECTED_EQUATIONS} equations, "
                         f"got {len(equations)}.")
    expected = [f"O5.{n}" for n in range(1, EXPECTED_EQUATIONS + 1)]
    if [e["equation_id"] for e in equations] != expected:
        raise SystemExit(f"{SHEET}: equations are not O5.1..O5.7.")

    by_id = {e["equation_id"]: e for e in equations}
    for equation in equations:
        for field in ("name", "formula", "variables", "units", "value_range",
                      "engine_target"):
            if not equation[field]:
                raise SystemExit(
                    f"{SHEET}: {equation['equation_id']} has no {field}.")

    encodings = data["encodings"]
    by_encodes: dict[str, list[dict]] = {}
    for encoding in encodings:
        by_encodes.setdefault(encoding["encodes"], []).append(encoding)
    for encodes in ("pack_years", "units_week", "tobacco_idx", "SSB_serv_day"):
        if encodes not in by_encodes:
            raise SystemExit(f"{SHEET}: no encoding was extracted for {encodes}.")

    # --- the two tobacco encodings ---------------------------------------
    #
    # O5.1 and O5.7 turn the SAME answer into two different numbers. If they
    # ever stop covering the same categories, one of them is being fed an
    # answer it has no value for.
    pack = {e["option"]: e["value"] for e in by_encodes["pack_years"]}
    tobacco = {e["option"]: e["value"] for e in by_encodes["tobacco_idx"]}
    if set(pack) != set(tobacco):
        raise SystemExit(
            f"{SHEET}: O5.1 encodes {sorted(pack)} and O5.7 encodes "
            f"{sorted(tobacco)}. Both read smoke_status and must cover the "
            "same answers.")
    if set(pack) != SMOKE_CATEGORIES:
        raise SystemExit(
            f"{SHEET}: the smoking categories are now {sorted(pack)}. "
            "Findings 2 and 3 in docs/parameter-gaps.md were recorded "
            "against the old five.")

    # FINDING 3, asserted rather than corrected. pack_years ties
    # Former(<1yr) with Occasional; tobacco_idx does not. One answer, two
    # indices, two orderings of the same five categories.
    if pack["Former(<1yr)"] != pack["Occasional"]:
        raise SystemExit(
            f"{SHEET}: O5.1 no longer ties Former(<1yr) with Occasional "
            f"({pack['Former(<1yr)']} vs {pack['Occasional']}). The ranking "
            "disagreement with O5.7 may have been resolved -- re-read both.")
    if tobacco["Former(<1yr)"] >= tobacco["Occasional"]:
        raise SystemExit(
            f"{SHEET}: O5.7 now ranks Former(<1yr) at or above Occasional "
            f"({tobacco['Former(<1yr)']} vs {tobacco['Occasional']}), which "
            "changes the disagreement recorded against O5.1.")

    # FINDING 2. Neither UI question offers "Former", so the five categories
    # are a join of two answers and nothing states the rule.
    smoke_status = _ui_options("smoke_status")
    quit_time = _ui_options("quit_time")
    if any("Former" in option for option in smoke_status + quit_time):
        raise SystemExit(
            f"{SHEET}: the UI now offers a 'Former' option "
            f"({smoke_status}, {quit_time}), so O5's five categories may no "
            "longer need a join rule. Re-read docs/parameter-gaps.md.")

    # --- alcohol ----------------------------------------------------------
    #
    # The sheet's midpoints must be the true midpoints of the bands the UI
    # offers. They are, which is what makes O5.5 below a discrepancy.
    units = {e["option"]: e["value"] for e in by_encodes["units_week"]}
    drinks_bands = _ui_options("drinks_wk")
    if len(units) != len(drinks_bands):
        raise SystemExit(
            f"{SHEET}: O5.2 encodes {len(units)} alcohol bands and the UI "
            f"offers {len(drinks_bands)}: {sorted(units)} vs {drinks_bands}.")
    for band, (option, value) in zip(drinks_bands, units.items()):
        midpoint = _band_midpoint(band)
        if midpoint is not None and value != midpoint:
            raise SystemExit(
                f"{SHEET}: O5.2 encodes the UI's {band!r} as {value}, but its "
                f"midpoint is {midpoint}. O5.2's midpoints being exact is the "
                "evidence that O5.5's are not -- re-read both.")

    # FINDING 4. The UI collects alcohol once, so drinks_wk cannot exceed
    # units_week's largest encoded value, and O5.6's male threshold is above
    # it.
    highest = max(units.values())
    male_threshold = 14
    if f"drinks_wk-{male_threshold}" not in by_id["O5.6"]["formula"].replace(" ", ""):
        raise SystemExit(
            f"{SHEET}: O5.6's male branch no longer subtracts "
            f"{male_threshold}: {by_id['O5.6']['formula']!r}")
    if highest >= male_threshold:
        raise SystemExit(
            f"{SHEET}: units_week now reaches {highest}, at or above O5.6's "
            f"male threshold of {male_threshold}. The male branch used to be "
            "unreachable -- re-read docs/parameter-gaps.md.")

    # --- FINDING 1: O5.5's midpoints are not midpoints --------------------
    ssb_values = [e["value"] for e in
                  sorted(by_encodes["SSB_serv_day"],
                         key=lambda e: e["ordinal_position"])]
    ssb_bands = _ui_options("SSB_serv")
    if len(ssb_values) != len(ssb_bands):
        raise SystemExit(
            f"{SHEET}: O5.5 declares {len(ssb_values)} midpoints and Step 3 "
            f"offers {len(ssb_bands)} bands: {ssb_values} vs {ssb_bands}.")
    disagreeing = [(band, declared, _band_midpoint(band))
                   for band, declared in zip(ssb_bands, ssb_values)
                   if _band_midpoint(band) is not None
                   and declared != _band_midpoint(band)]
    if not disagreeing:
        raise SystemExit(
            f"{SHEET}: O5.5's declared midpoints {ssb_values} now match "
            f"Step 3's bands {ssb_bands}. Finding 1 in docs/parameter-gaps.md "
            "is resolved and this check should be replaced by an equality.")

    # --- what the sheet gets right ----------------------------------------
    #
    # k_ox = lambda_smoke * lambda_alcohol, so its ceiling is the product of
    # the two ceilings, and the sheet declares it.
    ceiling = (1 + 0.02 * max(pack.values())) * (1 + 0.01 * highest)
    declared = by_id["O5.3"]["value_range"]
    if not declared.startswith("1.0-1.5"):
        raise SystemExit(
            f"{SHEET}: O5.3 declares {declared!r}; its computed ceiling is "
            f"{ceiling:.2f}.")
    if not 1.5 <= ceiling < 1.6:
        raise SystemExit(
            f"{SHEET}: O5.3's ceiling is now {ceiling:.4f}, outside the "
            f"declared {declared!r}.")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m sahacore.data.build_onboarding_o5 "
                         "<path-to-workbook>")
    data = extract(sys.argv[1])
    check(data)
    OUT.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")

    by_encodes: dict[str, int] = {}
    for encoding in data["encodings"]:
        by_encodes[encoding["encodes"]] = by_encodes.get(encoding["encodes"], 0) + 1
    print(f"wrote {OUT.name}")
    print(f"  {len(data['equations'])} equations O5.1..O5.7, "
          "each with its engine target")
    print(f"  {len(data['encodings'])} encoded answers across "
          f"{len(by_encodes)} variables: "
          + ", ".join(f"{k} {v}" for k, v in sorted(by_encodes.items())))
    print("  checked against the UI contract: O5.2's alcohol midpoints are "
          "exact, O5.5's SSB midpoints are not")


if __name__ == "__main__":
    main()
