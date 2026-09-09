"""Extracts '★ Nutrient Class Registry' into nutrient_classes.json.

Source: v39sEng2.xlsx, sheet '★ Nutrient Class Registry'.
'01_IMPORT_MANIFEST' lists it at order 41, role REGISTRY, import YES,
backend Yes.

    python -m sahacore.data.build_nutrient_classes <path-to-workbook>

The sheet holds two tables:

  section 1, rows 5-11   six kinetic classes, A to F, each with its kinetic
                         character and -- the column that matters -- the
                         modelling consequence.
  section 2, rows 16-97  all 81 nutrients, each assigned a class, an
                         observation anchor (what may legitimately be
                         measured to anchor it) and an endogenous-dominant
                         flag.

WHY A CLASS REGISTRY IS NOT DECORATION. The classes carry hard constraints on
what the engine is allowed to do with a nutrient, stated by the sheet itself:

    B  Homeostatically buffered   "Intake != serum. Serum is tightly clamped
                                   by renal and hormonal control."
    D  Gut substrate              "Not a plasma concentration."
    F  Behavioural exposure       applies to the 24 lifestyle states, not to
                                   the 81 nutrient pools.

A two-compartment plasma model is fully justified for class A and is the
wrong shape for classes B and D. Layer B applying the same kinetics to all 81
would produce a serum calcium trajectory that responds to calcium intake --
which the sheet says explicitly does not happen in a healthy person. So this
registry belongs in the foundation, before Layer B is written, not after.

THE OBSERVATION ANCHOR IS A SAFETY COLUMN TOO. It records what may anchor a
state and, often, what may not: "NOT serum Ca (PTH-clamped)", "serum Mg
INSENSITIVE", "serum chol is NOT a dietary readout". Those are transcribed
verbatim rather than reduced to a boolean, because the reason is the useful
part.

NOTHING IS DERIVED. Every field is the cell. The only check applied is that
the 81 canonical IDs are exactly the 81 in the nutrient registry -- if the
two sheets disagreed about the namespace, that is a finding, not something to
paper over with a partial join.
"""
import json
import sys
from pathlib import Path

import openpyxl

SHEET = "★ Nutrient Class Registry"
CLASS_HEADER_ROW = 5
NUTRIENT_HEADER_ROW = 16
OUT = Path(__file__).parent / "nutrient_classes.json"

# Column A is the sheet's indent margin and is always empty; every table on
# this sheet starts at column B.
FIRST_COL = 2

CLASS_COLUMNS = ["class_code", "name", "kinetic_character", "modelling_consequence"]
CLASS_LABELS = ["Class", "Name", "Kinetic character", "Modelling consequence"]

NUTRIENT_COLUMNS = ["num", "nutrient_code", "name", "category", "class_code",
                    "observation_anchor", "endogenous_dominant"]
NUTRIENT_LABELS = ["#", "Canonical ID", "Name", "Cat", "Cls",
                   "Observation anchor  (what may legitimately be measured)",
                   "Endo-dominant"]

EXPECTED_CLASSES = 6
EXPECTED_NUTRIENTS = 81


def _cell(ws, row: int, col: int) -> str | None:
    value = ws.cell(row=row, column=col).value
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def extract(workbook_path: str) -> dict:
    ws = openpyxl.load_workbook(workbook_path, data_only=True)[SHEET]

    got = [_cell(ws, CLASS_HEADER_ROW, c)
           for c in range(FIRST_COL, FIRST_COL + len(CLASS_LABELS))]
    if got != CLASS_LABELS:
        raise SystemExit(f"{SHEET} class header changed: {got}")
    # The nutrient header's sixth cell carries a long parenthetical; compare
    # on the prefix so a wording tweak does not fail the build, while a
    # reordering still does.
    got = [_cell(ws, NUTRIENT_HEADER_ROW, c)
           for c in range(FIRST_COL, FIRST_COL + len(NUTRIENT_LABELS))]
    if got[:5] != NUTRIENT_LABELS[:5] or not (got[5] or "").startswith("Observation anchor"):
        raise SystemExit(f"{SHEET} nutrient header changed: {got}")

    classes = []
    for r in range(CLASS_HEADER_ROW + 1, NUTRIENT_HEADER_ROW):
        code = _cell(ws, r, FIRST_COL)
        if not code or len(code) != 1:
            continue
        row = {"source_row": r}
        for i, name in enumerate(CLASS_COLUMNS, start=FIRST_COL):
            row[name] = _cell(ws, r, i)
        classes.append(row)

    nutrients = []
    for r in range(NUTRIENT_HEADER_ROW + 1, ws.max_row + 1):
        raw = _cell(ws, r, FIRST_COL)
        if raw is None:
            continue
        try:
            num = int(raw)
        except ValueError:
            continue
        row = {"source_row": r, "num": num}
        for i, name in enumerate(NUTRIENT_COLUMNS[1:], start=FIRST_COL + 1):
            row[name] = _cell(ws, r, i)
        # The flag is written as 'YES' or left blank.
        row["endogenous_dominant"] = (row["endogenous_dominant"] or "").upper() == "YES"
        nutrients.append(row)

    return {"classes": classes, "nutrients": nutrients}


def check(data: dict) -> None:
    classes, nutrients = data["classes"], data["nutrients"]

    if len(classes) != EXPECTED_CLASSES:
        raise SystemExit(f"expected {EXPECTED_CLASSES} classes, got {len(classes)}")
    codes = [c["class_code"] for c in classes]
    if codes != list("ABCDEF"):
        raise SystemExit(f"class codes are not A..F: {codes}")
    for c in classes:
        if not c["modelling_consequence"]:
            raise SystemExit(f"class {c['class_code']} states no modelling consequence")

    if len(nutrients) != EXPECTED_NUTRIENTS:
        raise SystemExit(f"expected {EXPECTED_NUTRIENTS} nutrients, got {len(nutrients)}")
    if sorted(n["num"] for n in nutrients) != list(range(1, 82)):
        raise SystemExit("nutrient numbers are not 1..81")

    unknown = {n["class_code"] for n in nutrients} - set(codes)
    if unknown:
        raise SystemExit(f"nutrients assigned to classes the sheet does not define: {unknown}")

    for n in nutrients:
        if not n["observation_anchor"]:
            raise SystemExit(f"#{n['num']} {n['nutrient_code']} has no observation anchor")

    # The two sheets must agree about the 81-nutrient namespace.
    registry = json.loads(
        (Path(__file__).parent / "nutrients_81.json").read_text(encoding="utf-8"))
    by_num = {r["num"]: r["id"] for r in registry}
    for n in nutrients:
        if by_num.get(n["num"]) != n["nutrient_code"]:
            raise SystemExit(
                f"#{n['num']}: this sheet says {n['nutrient_code']!r}, "
                f"'P1 Nutrients 81' says {by_num.get(n['num'])!r}")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m sahacore.data.build_nutrient_classes <workbook.xlsx>")

    data = extract(sys.argv[1])
    check(data)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    counts: dict[str, int] = {}
    for n in data["nutrients"]:
        counts[n["class_code"]] = counts.get(n["class_code"], 0) + 1
    endo = sum(1 for n in data["nutrients"] if n["endogenous_dominant"])

    print(f"wrote {len(data['classes'])} classes and {len(data['nutrients'])} "
          f"nutrient assignments to {OUT.name}")
    for c in data["classes"]:
        print(f"   {c['class_code']}  {counts.get(c['class_code'], 0):>3} nutrients   "
              f"{c['name']}")
    print(f"   endogenous-dominant: {endo}")


if __name__ == "__main__":
    main()
