"""Extracts 'Live Verification Lab' into verification_labs.json.

Source: v39sEng2.xlsx, sheet 'Live Verification Lab'.
'01_IMPORT_MANIFEST' order 5, role VALIDATION, import YES, backend Yes.

    python -m sahacore.data.build_verification_labs <path-to-workbook>

WHAT THIS SHEET IS, in its own words:

    "★ v38 LIVE VERIFICATION LAB · the load-bearing numbers, re-derived by
     live formulas in front of you"
    "Blue cells are inputs -- change them and watch the PASS/FAIL verdicts
     move. Black cells are live formulas."

Six labs, each a worked example with named inputs, derived quantities and a
verdict:

    LAB 1  C1   the gamma absorption kernel integrates to 1
    LAB 2  C5   zero-order-hold gain vs Euler
    LAB 3  C8   cascade stability: power iteration on Gamma
    LAB 4  LM-P01/P03  the Layer-M scar update
    LAB 5  T3   the Layer-T anomaly score
    LAB 6       restored v37.2 Layer-M formula set

WHY IT IS IMPORTED AS TEST VECTORS AND NOT AS PARAMETER VALUES. The sheet
calls its own inputs inputs -- they are there to be changed. A number in
LAB 4 is a point at which the formula was exercised, not a calibrated value
for the engine to use, and 'P1 Parameters 134+' remains the registry. So
every quantity is stored with the role the workbook gives it and none of
them reach the parameter tables. What the import buys is different and
worth more: each derived quantity carries the source's exact Excel formula
alongside its cached result, so the engine's own implementation can be held
to a number the workbook already published.

HOW INPUT AND DERIVED ARE TOLD APART. Not by cell colour, which is a
rendering detail, but by whether the cell stores a formula: the workbook is
read twice, once for cached values and once for formulas. That is the same
distinction the banner draws in prose, and it cannot drift out of step with
the sheet the way a hard-coded list of row numbers could. A derived cell
whose cached value is text is a VERDICT.

ONE DEMO POINT FALLS OUTSIDE THE ADMITTED PARAMETER REGION. LAB 4 and LAB 6
both run at gamma_scar = 0.69 with alpha_scar/beta_autophagy = 4, so
gamma*r = 2.76. '★ Scarring Bistability Guard' caps gamma*r per cluster, and
2.76 is above the cap for eleven of the twelve. Both labs return PASS, and
correctly so -- LM-P01 asks only whether 0 <= S_next <= 1 -- but neither lab
evaluates the bistability margin at all. That is recorded here and in
docs/parameter-gaps.md rather than corrected: changing a published worked
example is the workbook owner's call, not the importer's.
"""
import json
import sys
from pathlib import Path

import openpyxl

from sahacore.data.sheet_header import check_header

SHEET = "Live Verification Lab"
OUT = Path(__file__).parent / "verification_labs.json"

# This sheet starts at column A. Most sheets in this workbook indent by one
# column and start at B; assuming that here would shift every label by one.
FIRST_COL = 1

# lab_id -> (title row, rows of the label/value pane at columns A/B).
# Explicit rather than scanned: the pane rows are interleaved with the wide
# numeric grids, and a scan would have to guess where a lab ends.
LAB_BLOCKS: dict[str, tuple[int, range]] = {
    "LAB 1": (4, range(5, 14)),
    "LAB 2": (90, range(91, 92)),
    "LAB 3": (99, range(100, 101)),
    "LAB 4": (123, range(124, 141)),
    "LAB 5": (153, range(160, 166)),
    "LAB 6": (170, range(174, 182)),
}
# LAB 3's verdict block sits below its 12x12 matrix rather than beside it.
LAB_3_RESULT_ROWS = range(115, 121)

# Three labs keep part of themselves in a wide side table instead of in the
# A/B pane, and the missing half differs each time: LAB 2 states only its
# damage rate beside the labels and derives the gains across the grid, LAB 3
# reads its twelve-by-twelve coupling matrix, and LAB 5 reads two persistence
# vectors. A lab is complete only when its pane and its side table are taken
# together, so the side table is named here and `check` counts it.
SIDE_TABLE: dict[str, tuple[str, str]] = {
    "LAB 2": ("zoh_grid", "DERIVED"),
    "LAB 3": ("gamma_matrix", "INPUT"),
    "LAB 5": ("topology_vectors", "INPUT"),
}

# LAB 2's grid: three step sizes, analytic gain vs Euler gain.
ZOH_HEADER_ROW = 92
ZOH_ROWS = range(93, 96)
ZOH_LABELS = ["Δt (days)", "analytic g = (1−e^(−kΔt))/k", "Euler g = Δt",
              "relative error"]
ZOH_FIRST_COL = 4

# LAB 3's coupling matrix. Row 101 is the header; the driver label is in
# column C and the twelve weights run C1..C12.
GAMMA_HEADER_ROW = 101
GAMMA_ROWS = range(102, 114)
GAMMA_LABEL_COL = 3
GAMMA_FIRST_COL = 4
GAMMA_N = 12

# LAB 5's persistence vectors, 30 days apart.
TOPO_HEADER_ROW = 154
TOPO_ROWS = range(155, 160)
TOPO_LABELS = ["component", "τ(t−30d)", "τ(t)", "difference"]
TOPO_FIRST_COL = 4

# LAB 6's closing rules -- the production equation and the replay rule.
RULE_ROWS = range(185, 190)

# Five of the six verdicts are text -- PASS, FAIL or FIRE. LAB 6's 'bounds
# check' is the exception: it resolves to a boolean instead. It is a verdict
# all the same, so it is stored as one, with the boolean rendered TRUE/FALSE
# rather than being filed as the number 1. Python would otherwise class it as
# an integer, bool being a subclass of int, and a passing gate would land in
# the numeric column as 1.0.
VERDICT_WORDS = ("PASS", "FAIL", "FIRE", "TRUE", "FALSE")
FAILING_VERDICTS = ("FAIL", "FALSE")

# LAB 4 and LAB 6 exercise the same Layer-M update at the same eight inputs,
# spelled once in Greek and once in ASCII. Re-keying them to canonical names
# lets the demo point be stored as one typed row and compared against
# '★ Scarring Bistability Guard' -- and because both labs must supply every
# one of the eight, the pair also cross-checks each other. A label that stops
# matching fails the extract rather than silently yielding a partial point.
DEMO_POINT_LABELS: dict[str, tuple[str, str]] = {
    "s_t":                    ("S_t (current scar)",     "S_t"),
    "z_t":                    ("Z_t (cluster damage)",   "Z_t"),
    "theta_elastic":          ("θ_elastic",              "theta_elastic"),
    "alpha_scar_per_day":     ("α_scar (/day)",          "alpha_scar /day"),
    "beta_autophagy_per_day": ("β_autophagy (/day)",     "beta_autophagy /day"),
    "gamma_scar":             ("γ_scar",                 "gamma_scar"),
    "dt_days":                ("Δt (days)",              "dt_days"),
    "vmax_base":              ("Vmax_base",              "Vmax_base"),
}


def _text(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _classify(formula, value) -> str:
    """INPUT if the cell stores a constant, DERIVED if it stores a formula,
    VERDICT if it stores a formula that resolves to text."""
    if not (isinstance(formula, str) and formula.startswith("=")):
        return "INPUT"
    if isinstance(value, (str, bool)):
        return "VERDICT"
    return "DERIVED"


def _quantity(row: int, name: str, formula, value) -> dict:
    role = _classify(formula, value)
    if isinstance(value, bool):
        text, number = str(value).upper(), None
    elif isinstance(value, str):
        text, number = _text(value), None
    else:
        text, number = None, value
    return {
        "source_row": row,
        "name": name,
        "role": role,
        "formula": formula if role != "INPUT" else None,
        "value_num": number,
        "value_text": text,
    }


def _demo_point(labs: list[dict]) -> dict:
    """The eight Layer-M inputs, taken from LAB 4 and confirmed by LAB 6."""
    panes = {lab["lab_id"]: {q["name"]: q for q in lab["quantities"]}
             for lab in labs}
    point: dict[str, float] = {}
    rows: dict[str, list[int]] = {}
    for field, (lab4_label, lab6_label) in DEMO_POINT_LABELS.items():
        found = []
        for lab_id, label in (("LAB 4", lab4_label), ("LAB 6", lab6_label)):
            q = panes[lab_id].get(label)
            if q is None:
                raise SystemExit(
                    f"{SHEET}: {lab_id} has no input labelled {label!r}, so the "
                    f"Layer-M demo point cannot be read for {field}.")
            if q["role"] != "INPUT":
                raise SystemExit(
                    f"{SHEET}: {lab_id} {label!r} is a {q['role']}, not an "
                    "input; it cannot be part of the demo point.")
            found.append(q)
        if found[0]["value_num"] != found[1]["value_num"]:
            raise SystemExit(
                f"{SHEET}: LAB 4 and LAB 6 disagree on {field} -- "
                f"{found[0]['value_num']} vs {found[1]['value_num']}. They are "
                "documented as the same worked example.")
        point[field] = found[0]["value_num"]
        rows[field] = [q["source_row"] for q in found]
    point["source_rows"] = rows
    return point


def extract(path: str) -> dict:
    values = openpyxl.load_workbook(path, read_only=True, data_only=True)[SHEET]
    formulas = openpyxl.load_workbook(path, read_only=True, data_only=False)[SHEET]

    def v(row, col):
        return values.cell(row=row, column=col).value

    def f(row, col):
        return formulas.cell(row=row, column=col).value

    labs = []
    for lab_id, (title_row, pane) in LAB_BLOCKS.items():
        title = _text(v(title_row, FIRST_COL))
        if title is None or not title.startswith(lab_id):
            raise SystemExit(
                f"{SHEET}: row {title_row} reads {title!r}, expected it to "
                f"start with {lab_id!r}.")

        rows = list(pane)
        if lab_id == "LAB 3":
            rows += list(LAB_3_RESULT_ROWS)

        quantities = []
        for row in rows:
            name = _text(v(row, FIRST_COL))
            if name is None:
                raise SystemExit(f"{SHEET}: row {row} of {lab_id} has no label.")
            quantities.append(_quantity(row, name, f(row, FIRST_COL + 1),
                                        v(row, FIRST_COL + 1)))

        if lab_id == "LAB 6":
            # LAB 6 lays its derived quantities in a second pane at D/E
            # rather than below its inputs.
            check_header(values, SHEET, 173, 1, ["Input", "Value"])
            check_header(values, SHEET, 173, 4, ["Derived quantity", "Formula result"])
            for row in range(174, 184):
                name = _text(v(row, 4))
                if name is None:
                    continue
                quantities.append(_quantity(row, name, f(row, 5), v(row, 5)))

        side_table, _ = SIDE_TABLE.get(lab_id, (None, None))
        labs.append({
            "lab_id": lab_id,
            "source_row": title_row,
            "title": title,
            "side_table": side_table,
            "quantities": quantities,
        })

    check_header(values, SHEET, ZOH_HEADER_ROW, ZOH_FIRST_COL, ZOH_LABELS)
    zoh = [{
        "source_row": row,
        "dt_days": v(row, ZOH_FIRST_COL),
        "analytic_gain": v(row, ZOH_FIRST_COL + 1),
        "euler_gain": v(row, ZOH_FIRST_COL + 2),
        "relative_error": v(row, ZOH_FIRST_COL + 3),
    } for row in ZOH_ROWS]

    clusters = [_text(v(GAMMA_HEADER_ROW, GAMMA_FIRST_COL + i))
                for i in range(GAMMA_N)]
    gamma = [{
        "source_row": row,
        "driver": _text(v(row, GAMMA_LABEL_COL)),
        "weights": [v(row, GAMMA_FIRST_COL + i) for i in range(GAMMA_N)],
    } for row in GAMMA_ROWS]

    check_header(values, SHEET, TOPO_HEADER_ROW, TOPO_FIRST_COL, TOPO_LABELS)
    topo = [{
        "source_row": row,
        "component": _text(v(row, TOPO_FIRST_COL)),
        "tau_reference": v(row, TOPO_FIRST_COL + 1),
        "tau_now": v(row, TOPO_FIRST_COL + 2),
        "difference": v(row, TOPO_FIRST_COL + 3),
    } for row in TOPO_ROWS]

    rules = []
    for row in RULE_ROWS:
        name = _text(v(row, FIRST_COL))
        statement = _text(v(row, FIRST_COL + 1))
        if name and statement:
            rules.append({"source_row": row, "name": name, "statement": statement})

    return {
        "sheet": SHEET,
        "banner": _text(v(1, FIRST_COL)),
        "layer_m_demo_point": _demo_point(labs),
        "labs": labs,
        "zoh_grid": zoh,
        "gamma_matrix": {"clusters": clusters, "rows": gamma},
        "topology_vectors": topo,
        "layer_m_rules": rules,
    }


def check(data: dict) -> None:
    if len(data["labs"]) != len(LAB_BLOCKS):
        raise SystemExit(f"{SHEET}: expected {len(LAB_BLOCKS)} labs, "
                         f"got {len(data['labs'])}.")

    for lab in data["labs"]:
        roles = {q["role"] for q in lab["quantities"]}
        side_table, contributes = SIDE_TABLE.get(lab["lab_id"], (None, None))
        if side_table:
            if not data[side_table]:
                raise SystemExit(f"{SHEET}: {lab['lab_id']} declares side table "
                                 f"{side_table!r} but it came back empty.")
            roles.add(contributes)
        if "INPUT" not in roles:
            raise SystemExit(f"{SHEET}: {lab['lab_id']} has no inputs. A lab "
                             "with nothing to vary is not a lab.")
        if "DERIVED" not in roles:
            raise SystemExit(f"{SHEET}: {lab['lab_id']} derives nothing.")
        for q in lab["quantities"]:
            if q["role"] == "INPUT" and q["value_num"] is None:
                raise SystemExit(
                    f"{SHEET}: {lab['lab_id']} input {q['name']!r} at row "
                    f"{q['source_row']} is not a number.")
            if q["role"] == "DERIVED" and q["value_num"] is None:
                raise SystemExit(
                    f"{SHEET}: {lab['lab_id']} derived {q['name']!r} at row "
                    f"{q['source_row']} has no cached value. The workbook was "
                    "saved without recalculating; the numbers cannot be trusted.")

    # Every verdict the sheet publishes must be one it is willing to state.
    # A blank verdict cell would mean an unevaluated gate imported as a pass.
    verdicts = [q for lab in data["labs"] for q in lab["quantities"]
                if q["role"] == "VERDICT"]
    if not verdicts:
        raise SystemExit(f"{SHEET}: no verdicts found -- the classification "
                         "broke, because the sheet is built around them.")
    for q in verdicts:
        if not q["value_text"] or not q["value_text"].startswith(VERDICT_WORDS):
            raise SystemExit(
                f"{SHEET}: verdict at row {q['source_row']} reads "
                f"{q['value_text']!r}, which is not one of {VERDICT_WORDS}.")
    failed = [q for q in verdicts if q["value_text"].startswith(FAILING_VERDICTS)]
    if failed:
        raise SystemExit(
            f"{SHEET}: the source publishes a FAIL verdict at rows "
            f"{[q['source_row'] for q in failed]}. Refusing to import a lab "
            "the workbook itself says is failing.")

    matrix = data["gamma_matrix"]
    if len(matrix["clusters"]) != GAMMA_N or len(matrix["rows"]) != GAMMA_N:
        raise SystemExit(f"{SHEET}: Gamma must be {GAMMA_N}x{GAMMA_N}, got "
                         f"{len(matrix['rows'])}x{len(matrix['clusters'])}.")
    for row in matrix["rows"]:
        if len(row["weights"]) != GAMMA_N or any(w is None for w in row["weights"]):
            raise SystemExit(f"{SHEET}: Gamma row {row['driver']!r} is ragged.")
        if row["driver"] not in matrix["clusters"]:
            raise SystemExit(
                f"{SHEET}: Gamma driver {row['driver']!r} is not one of the "
                "twelve column headers; the matrix is not square in its labels.")

    for row in data["zoh_grid"]:
        if row["euler_gain"] != row["dt_days"]:
            raise SystemExit(
                f"{SHEET}: LAB 2 row {row['source_row']} has Euler gain "
                f"{row['euler_gain']} for dt {row['dt_days']}; the sheet "
                "defines Euler g = dt.")

    for row in data["topology_vectors"]:
        stated = row["difference"]
        computed = row["tau_now"] - row["tau_reference"]
        if abs(stated - computed) > 1e-12:
            raise SystemExit(
                f"{SHEET}: LAB 5 {row['component']!r} states difference "
                f"{stated} but tau(t) - tau(t-30d) = {computed}.")

    names = [r["name"] for r in data["layer_m_rules"]]
    for required in ("Production equation", "Exact update", "Parameter rules",
                     "Replay rule"):
        if required not in names:
            raise SystemExit(f"{SHEET}: LAB 6 is missing its {required!r} row.")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m sahacore.data.build_verification_labs "
                         "<path-to-workbook>")
    data = extract(sys.argv[1])
    check(data)
    OUT.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")

    roles: dict[str, int] = {}
    for lab in data["labs"]:
        for q in lab["quantities"]:
            roles[q["role"]] = roles.get(q["role"], 0) + 1
    print(f"wrote {OUT.name}")
    print(f"  {len(data['labs'])} labs: "
          + ", ".join(f"{k} {v}" for k, v in sorted(roles.items())))
    print(f"  Gamma {GAMMA_N}x{GAMMA_N}, {len(data['zoh_grid'])} step sizes, "
          f"{len(data['topology_vectors'])} topology components, "
          f"{len(data['layer_m_rules'])} Layer-M rules")


if __name__ == "__main__":
    main()
