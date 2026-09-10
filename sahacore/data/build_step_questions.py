"""Extracts 'O·Step-by-Step Questions' into step_questions.json.

Source: v39sEng2.xlsx, sheet 'O·Step-by-Step Questions'.
'01_IMPORT_MANIFEST' order 70, role ONBOARDING, import YES, backend Yes.

    python -m sahacore.data.build_step_questions <path-to-workbook>

WHAT THE SHEET IS, in its own words: "Onboarding Questionnaire -- All 12
Steps", "Exact questions and answer options from SahaPlusAI Figma UI". Every
row is one field the user fills in, what it may be answered with, and which
O-module consumes it.

WHY IT COMES FIRST, AND WHY THAT WAS MISSED. It is manifest order 70 --
BEFORE O1 at 71, O2 at 72, O3 at 73, O4 at 74. Four O-modules were built
before it, so four modules were built before the contract that says what
their inputs are. Nothing failed, because an O-sheet names its own inputs in
a Variables column; what was lost is the ability to CHECK them.

Concretely, sahacore.data.onboarding_symbols carries DECLARED_INPUTS, a set
written by hand with the comment "written by hand because 'this is an answer
the user gives' is not something a parser can tell from a name". That was
true only because this sheet had not been imported. It says exactly that, for
every input, in a column called "Maps To".

WHAT THIS SHEET CORROBORATES

  The PSS-10 reverse set, a THIRD time. O4 states it twice -- a Reverse?
  column and O4.1's formula. Step 8 states it again, in the question text
  ("...(REVERSE)") and in Maps To ("r4 -> O4 (reverse)"). All three agree on
  items 4, 5, 7 and 8.

  O4.3's protection cap. Step 8 offers four stress-reduction practices plus
  "None", and O4.3 credits 0.05 per practice capped at 0.20 -- which is
  exactly four. The cap is reachable and cannot be exceeded, and neither
  sheet mentions the other.

  O3.6's consistency scale. Step 9 offers four ordered options and O3.6
  scores them 1 to 4. O3 abbreviates two of the labels; the full text is
  here.

WHAT IT CONTRADICTS is recorded in docs/parameter-gaps.md rather than
resolved -- most sharply, Step 3's sugary-drink bands against O5.5's declared
"midpoints", and Step 10's two smoking questions against O5's five tobacco
categories. Those are checked in the O5 extractor, where both halves exist.
"""
import json
import re
import sys
from pathlib import Path

import openpyxl

from sahacore.data.sheet_header import check_header

SHEET = "O·Step-by-Step Questions"
FIRST_COL = 3
OUT = Path(__file__).parent / "step_questions.json"

HEADER_ROW = 7
DATA_ROWS = range(8, 93)
LABELS = ["Step", "Category", "Question / Field", "Answer Options", "Maps To",
          "Required"]

EXPECTED_STEPS = 12

# A step banner: 'Step 3: "What is fueling your body?"' alone in column C.
_STEP_BANNER = re.compile(r'^Step (\d+):\s*(.*)$')

# A question's step cell: 'Step 3'.
_STEP_LABEL = re.compile(r"^Step (\d+)$")

# 'SSB_serv → O5, O11' and 'r4 → O4 (reverse)'.
_MAPS_TO = re.compile(r"^(?P<variable>[^→]+)→(?P<targets>.*)$")

# The options are slash-separated, but an option may itself contain a slash
# with no spaces -- 'Low-carb/Keto', 'Yoga/Tai Chi'. Splitting on a spaced
# slash keeps those whole.
_OPTION_SPLIT = re.compile(r"\s+/\s+")

# An Answer Options cell that describes an input control rather than listing
# choices: 'Date picker', 'Numeric entry', 'Slider 0-8+ hours'. These are
# recorded as free-form, because inventing options for them would be
# inventing the UI.
_FREE_FORM = ("picker", "entry", "slider", "search", "input", "checkboxes",
              "multi-select", "or ")

REQUIRED_VALUES = ("Mandatory", "Optional", "Conditional")


def _text(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _cell(ws, row: int, offset: int):
    return ws.cell(row=row, column=FIRST_COL + offset).value


def _parse_options(cell: str) -> tuple[list[str], bool]:
    """The listed choices, and whether the cell lists choices at all."""
    options = [o.strip() for o in _OPTION_SPLIT.split(cell) if o.strip()]
    if len(options) > 1:
        return options, True
    if any(word in cell.lower() for word in _FREE_FORM):
        return [], False
    # A single option is not a choice; treat it as free-form so a one-item
    # list never looks like a settled enumeration.
    return [], False


def extract(path: str) -> dict:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb[SHEET]
    check_header(ws, SHEET, HEADER_ROW, FIRST_COL, LABELS)

    steps: list[dict] = []
    questions: list[dict] = []
    current: int | None = None

    for row in DATA_ROWS:
        first = _text(_cell(ws, row, 0))
        if first is None:
            continue

        banner = _STEP_BANNER.match(first)
        if banner and _text(_cell(ws, row, 2)) is None:
            current = int(banner.group(1))
            steps.append({"step_number": current, "source_row": row,
                          "title": banner.group(2).strip().strip('"')})
            continue

        label = _STEP_LABEL.match(first)
        if not label:
            raise SystemExit(
                f"{SHEET}: row {row} starts with {first!r}, which is neither a "
                "step banner nor a 'Step N' label.")
        if current is None or int(label.group(1)) != current:
            raise SystemExit(
                f"{SHEET}: row {row} is labelled {first!r} but sits under step "
                f"{current}. A question filed under the wrong step would be "
                "asked at the wrong point in onboarding.")

        question = _text(_cell(ws, row, 2))
        options_cell = _text(_cell(ws, row, 3))
        maps_to = _text(_cell(ws, row, 4))
        required = _text(_cell(ws, row, 5))
        if not question or not options_cell or not maps_to or not required:
            raise SystemExit(
                f"{SHEET}: row {row} is incomplete ({question!r}, "
                f"{options_cell!r}, {maps_to!r}, {required!r}). A question "
                "with no destination collects an answer nothing reads.")
        if required not in REQUIRED_VALUES:
            raise SystemExit(
                f"{SHEET}: row {row} is marked {required!r}, which is not one "
                f"of {REQUIRED_VALUES}.")

        matched = _MAPS_TO.match(maps_to)
        if not matched:
            raise SystemExit(
                f"{SHEET}: row {row} maps to {maps_to!r}, which has no "
                "'variable → target' arrow.")
        targets_text = matched.group("targets").strip()
        # 'O4 (reverse)' -> targets ['O4'], reverse True
        reverse = "(reverse)" in targets_text.lower()
        targets_text = re.sub(r"\(reverse\)", "", targets_text,
                              flags=re.IGNORECASE)
        targets = [t.strip() for t in targets_text.split(",") if t.strip()]

        options, is_choice = _parse_options(options_cell)
        questions.append({
            "source_row": row,
            "step_number": current,
            "category": _text(_cell(ws, row, 1)),
            "question": question,
            "answer_options_text": options_cell,
            "answer_options": options,
            "is_choice": is_choice,
            "variable": matched.group("variable").strip(),
            "targets": targets,
            "reverse_scored": reverse,
            "required": required,
        })

    wb.close()
    return {"sheet": SHEET, "steps": steps, "questions": questions}


def check(data: dict) -> None:
    steps, questions = data["steps"], data["questions"]

    if len(steps) != EXPECTED_STEPS:
        raise SystemExit(f"{SHEET}: expected {EXPECTED_STEPS} steps, got "
                         f"{len(steps)}. The sheet calls itself 'All 12 Steps'.")
    if [s["step_number"] for s in steps] != list(range(1, EXPECTED_STEPS + 1)):
        raise SystemExit(f"{SHEET}: the steps are not numbered 1..{EXPECTED_STEPS}.")
    for step in steps:
        if not step["title"]:
            raise SystemExit(f"{SHEET}: step {step['step_number']} has no title.")

    if not questions:
        raise SystemExit(f"{SHEET}: no questions were extracted.")
    for step in steps:
        if not any(q["step_number"] == step["step_number"] for q in questions):
            raise SystemExit(
                f"{SHEET}: step {step['step_number']} has no questions.")

    # THE PSS-10 REVERSE SET, STATED A THIRD TIME. Step 8's question text
    # carries '(REVERSE)' and its Maps To carries '(reverse)'. Both must name
    # the same items, and O4's own two statements are checked against this in
    # tests/test_step_questions.py.
    pss10 = [q for q in questions if q["variable"].startswith("r")
             and q["variable"][1:].isdigit()]
    if len(pss10) != 10:
        raise SystemExit(
            f"{SHEET}: found {len(pss10)} PSS-10 item rows, expected 10.")
    numbered = sorted(int(q["variable"][1:]) for q in pss10)
    if numbered != list(range(1, 11)):
        raise SystemExit(f"{SHEET}: the PSS-10 items are {numbered}, not 1..10.")

    by_maps_to = {int(q["variable"][1:]) for q in pss10 if q["reverse_scored"]}
    in_question_text = {int(q["variable"][1:]) for q in pss10
                        if "(REVERSE)" in q["question"]}
    if by_maps_to != in_question_text:
        raise SystemExit(
            f"{SHEET}: the question text marks items {sorted(in_question_text)} "
            f"as reverse-scored and Maps To marks {sorted(by_maps_to)}. The "
            "sheet contradicts itself.")
    if by_maps_to != {4, 5, 7, 8}:
        raise SystemExit(
            f"{SHEET}: Step 8 reverse-scores {sorted(by_maps_to)}, and "
            "'O·O4 Stress Index' reverses 4, 5, 7 and 8. One of the two "
            "changed; read both before importing.")

    # Every question must reach at least one named destination.
    for question in questions:
        if not question["targets"]:
            raise SystemExit(
                f"{SHEET}: row {question['source_row']} "
                f"({question['variable']!r}) names no destination.")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m sahacore.data.build_step_questions "
                         "<path-to-workbook>")
    data = extract(sys.argv[1])
    check(data)
    OUT.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")

    questions = data["questions"]
    choices = sum(1 for q in questions if q["is_choice"])
    mandatory = sum(1 for q in questions if q["required"] == "Mandatory")
    destinations = sorted({t for q in questions for t in q["targets"]})
    print(f"wrote {OUT.name}")
    print(f"  {len(data['steps'])} steps, {len(questions)} questions")
    print(f"  {choices} offer a fixed choice list, {len(questions) - choices} "
          "are free-form controls")
    print(f"  {mandatory} mandatory")
    print(f"  {len(destinations)} destinations: {', '.join(destinations)}")


if __name__ == "__main__":
    main()
