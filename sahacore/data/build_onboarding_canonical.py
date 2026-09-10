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

The slots ONB-012 fills at 163-186 are twelve CLUSTERS.

A CORRECTION. An earlier version of this file said the map from fifteen
pathways to twelve clusters was not in the workbook. It is:
'TVMCD · 15 Pathways Build' has a "Cluster outputs" column giving two or
three clusters for every one of the fifteen pathways. The search that
concluded otherwise matched `C1..C12` and `D1..D15`, and that sheet writes
them zero-padded -- `C02`, `D01` -- so it scored zero on both counts and was
passed over. Re-run with padding allowed it is the only sheet of the 205 that
carries ten or more of each.

What the map gives is membership, not weights, and BLOCKED_BY below records
the three things still missing. The two steps stay blocked; the reason is
now specific rather than an absent artefact.

The other twelve steps do not depend on it. That is what DEPENDS_ON_BRIDGE
records, so the buildable set is a fact in the data rather than a judgement
made again each time someone reads the sheet.
"""
import json
import sys
from pathlib import Path

import openpyxl

from sahacore.data.sheet_header import check_header

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
    "The pathway-to-cluster map exists -- 'TVMCD · 15 Pathways Build' gives "
    "cluster outputs for all fifteen pathways -- but it is MEMBERSHIP, not a "
    "weighted map. Three things are still missing. (1) No weights: C12 is fed "
    "by eight pathways and C11 by one, and nothing states how several pathway "
    "values combine into one cluster value. (2) No pathway lists C01 Membrane "
    "Integrity as an output, so one of the twelve clusters would warm-start "
    "from nothing. (3) ONB-012 fills twenty-four slots, xi_hi[163:174] and "
    "xi_lo[175:186], and nothing says how fifteen values split into a high "
    "and a low side."
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

    check_header(ws, SHEET, HEADER_ROW, FIRST_COL, HEADER_LABELS)
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
    print(f"  blocked:       {len(blocked)}  {blocked} -- the pathway-to-"
          "cluster map has no weights, no C01 and no hi/lo split")


if __name__ == "__main__":
    main()
