"""Extracts 'O · Onboarding Canonical' into onboarding_canonical.json.

Source: v39sEng2.xlsx, sheet 'O · Onboarding Canonical'.
'01_IMPORT_MANIFEST' order 128, role ONBOARDING, import YES, backend Yes.

    python -m sahacore.data.build_onboarding_canonical <path-to-workbook>

WHAT THE SHEET IS: the build contract for Layer 0, and the most directly
actionable sheet imported so far. Fourteen steps, ONB-001 to ONB-014, each
carrying its operational equation, inputs, outputs, parameter references,
the QA that must pass -- and the name of the Python function that implements
it, from `sahacore.onboarding.anthropometrics` to
`sahacore.onboarding.control_input`.

'★ Build Guide Python' step 3 is this sheet: "Implement onboarding
warm-start", package `sahacore.onboarding`, acceptance "length x0=219;
PSD P0".

THE 219 SLOT LAYOUT IS CORROBORATED, NOT ASSUMED. ONB-012 states it:

    x0=[C_fast(81)@1-81, C_slow(81)@82-162, Z_hi(12)@163-174,
        Z_lo(12)@175-186, lifestyle(24)@187-210, N1 G/X/I@211-213,
        N2 V@214, N3 x_c/y_c@215-216, N4 F/L@217-218, N5 A_v@219]

and `check()` verifies every block against state_vector_219.json, which was
imported days earlier from a different sheet. They agree exactly.

TWO MODULES ARE BLOCKED, AND THE REASON IS RECORDED RATHER THAN WORKED
AROUND. ONB-011's authority sheet, 'O·O11 Damage State Init', produces
FIFTEEN pathway values and says on every one of its fifteen rows:

    "15->12 bridge -> xi_hi/xi_lo; no direct x_hat slot"

The slots ONB-012 fills at 163-186 are twelve CLUSTERS. Going from fifteen
pathways to twelve clusters needs a bridge, which five separate places call
"the canonical 15->12 bridge" -- and which is not in this workbook. See
BLOCKED_BY below and docs/parameter-gaps.md for the search that establishes
that.

The other twelve steps do not depend on it. That is what DEPENDS_ON_BRIDGE
records, so the buildable set is a fact in the data rather than a judgement
made again each time someone reads the sheet.
"""
import json
import sys
from pathlib import Path

import openpyxl

SHEET = "O · Onboarding Canonical"
FIRST_COL = 1
HEADER_ROW = 2
DATA_ROWS = range(3, 17)
OUT = Path(__file__).parent / "onboarding_canonical.json"

COLUMNS = ["authority_sheets", "operational_equation", "inputs", "outputs",
           "parameter_refs", "python_function", "validation_qa"]
HEADER_LABELS = ["Step", "Authority sheet(s)", "Operational equation / rule",
                 "Inputs", "Outputs", "Parameter refs", "Python function",
                 "Validation / QA"]

EXPECTED_STEPS = 14
PACKAGE = "sahacore.onboarding"

# The blocks ONB-012 declares, checked against state_vector_219.json. The
# sheet writes the damage slots as Z_hi/Z_lo; the state vector registry
# names those blocks xi_hi/xi_lo with unit log(AU), and the log coordinate
# is what the slot actually holds -- Z = exp(xi) - eps is derived from it,
# never stored in it. Battery test C3 ("Damage positivity (log-coordinates)")
# depends on that distinction, so the mapping is declared here rather than
# matched on the name.
DECLARED_BLOCKS: list[tuple[str, str, int, int]] = [
    ("C_fast",    "C_fast",    1,   81),
    ("C_slow",    "C_slow",    82,  162),
    ("Z_hi",      "xi_hi",     163, 174),
    ("Z_lo",      "xi_lo",     175, 186),
    ("lifestyle", "lifestyle", 187, 210),
    ("N1",        "N1",        211, 213),
    ("N2",        "N2",        214, 214),
    ("N3",        "N3",        215, 216),
    ("N4",        "N4",        217, 218),
    ("N5",        "N5",        219, 219),
]

# Steps that cannot be implemented until the 15->12 pathway-to-cluster
# bridge exists. ONB-011 produces the fifteen pathway values; ONB-012 needs
# the twelve cluster values for slots 163-186 and can build the other 195
# slots without it.
DEPENDS_ON_BRIDGE = {"ONB-011", "ONB-012"}
BLOCKED_BY = (
    "The canonical 15->12 pathway-to-cluster bridge. Named as a required "
    "step by 'O·O11 Damage State Init', 'O·O12-O14 State Init', "
    "'O·Engine Connections', '★ Build Map — concept to code' and "
    "'M-MAP Integration'. 'P1 Cluster Map 15-12' is titled as that bridge "
    "but holds a 12-organ x 13-pathway matrix -- its own v35.9.3 banner "
    "says the rows are ORGAN SYSTEMS keyed SYS1-SYS12 and 'must never be "
    "referenced by a bare C-code'. No sheet in the workbook carries twelve "
    "cluster ids and fifteen pathway ids together."
)


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

    for offset, expected in enumerate(HEADER_LABELS):
        found = _text(_cell(ws, HEADER_ROW, offset))
        if found != expected:
            raise SystemExit(
                f"{SHEET}: header row {HEADER_ROW} column {FIRST_COL + offset} "
                f"reads {found!r}, expected {expected!r}. The sheet moved.")

    steps = []
    for row in DATA_ROWS:
        step_id = _text(_cell(ws, row, 0))
        if step_id is None:
            raise SystemExit(f"{SHEET}: row {row} has no step id.")
        record = {"step_id": step_id, "source_row": row}
        for offset, name in enumerate(COLUMNS, start=1):
            record[name] = _text(_cell(ws, row, offset))
        record["blocked_by"] = BLOCKED_BY if step_id in DEPENDS_ON_BRIDGE else None
        steps.append(record)

    wb.close()
    return {"sheet": SHEET, "steps": steps,
            "declared_blocks": [
                {"sheet_name": a, "registry_block": b, "first_index": c,
                 "last_index": d}
                for a, b, c, d in DECLARED_BLOCKS]}


def check(data: dict) -> None:
    steps = data["steps"]
    if len(steps) != EXPECTED_STEPS:
        raise SystemExit(f"{SHEET}: expected {EXPECTED_STEPS} steps, got "
                         f"{len(steps)}.")

    expected_ids = [f"ONB-{n:03d}" for n in range(1, EXPECTED_STEPS + 1)]
    if [s["step_id"] for s in steps] != expected_ids:
        raise SystemExit(f"{SHEET}: steps are not ONB-001..ONB-{EXPECTED_STEPS:03d}: "
                         f"{[s['step_id'] for s in steps]}")

    for step in steps:
        for field in COLUMNS:
            if not step[field]:
                raise SystemExit(
                    f"{SHEET}: {step['step_id']} has no {field}. Every step "
                    "must name its equation, its I/O, its function and the QA "
                    "that proves it.")
        function = step["python_function"]
        if not function.startswith(PACKAGE + "."):
            raise SystemExit(
                f"{SHEET}: {step['step_id']} names {function!r}, which is not "
                f"in {PACKAGE}. '★ Build Guide Python' step 3 puts the whole "
                "of Layer 0 in that package.")

    functions = [s["python_function"] for s in steps]
    if len(set(functions)) != len(functions):
        raise SystemExit(f"{SHEET}: two steps name the same Python function.")

    # ONB-012's slot layout against the state vector imported from a
    # different sheet days earlier. Agreement here is corroboration; a
    # disagreement would mean one of the two is wrong about the engine's
    # own state, which nothing downstream could survive.
    vector = json.loads(
        (Path(__file__).parent / "state_vector_219.json").read_text(encoding="utf-8"))
    if len(vector) != 219:
        raise SystemExit(f"state_vector_219.json holds {len(vector)} rows, not 219.")
    by_index = {row["idx"]: row for row in vector}
    for block in data["declared_blocks"]:
        for index in range(block["first_index"], block["last_index"] + 1):
            row = by_index.get(index)
            if row is None:
                raise SystemExit(f"state vector has no slot {index}.")
            if row["block"] != block["registry_block"]:
                raise SystemExit(
                    f"{SHEET}: ONB-012 puts {block['sheet_name']} at slot "
                    f"{index}, but the state vector registry has "
                    f"{row['block']} there.")
    covered = sum(b["last_index"] - b["first_index"] + 1
                  for b in data["declared_blocks"])
    if covered != 219:
        raise SystemExit(f"{SHEET}: ONB-012's blocks cover {covered} slots, not 219.")

    blocked = [s["step_id"] for s in steps if s["blocked_by"]]
    if set(blocked) != DEPENDS_ON_BRIDGE:
        raise SystemExit(f"{SHEET}: blocked steps are {blocked}, expected "
                         f"{sorted(DEPENDS_ON_BRIDGE)}.")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m sahacore.data.build_onboarding_canonical "
                         "<path-to-workbook>")
    data = extract(sys.argv[1])
    check(data)
    OUT.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")

    buildable = [s["step_id"] for s in data["steps"] if not s["blocked_by"]]
    blocked = [s["step_id"] for s in data["steps"] if s["blocked_by"]]
    print(f"wrote {OUT.name}")
    print(f"  {len(data['steps'])} steps, each naming a {PACKAGE} function")
    print(f"  219 slots verified against state_vector_219.json, block by block")
    print(f"  buildable now: {len(buildable)}  ({buildable[0]}..{buildable[-1]})")
    print(f"  blocked:       {len(blocked)}  {blocked} -- no 15->12 bridge")


if __name__ == "__main__":
    main()
