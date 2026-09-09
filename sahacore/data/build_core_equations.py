"""Extracts 'P1 Core Equations' into core_equations.json.

Source: v39sEng2.xlsx, sheet 'P1 Core Equations' -- "P1 CORE EQUATIONS -
SahaCore v32.1". '01_IMPORT_MANIFEST' order 23, role CORE_ENGINE, import YES,
backend Yes. Header at row 6; 51 equations in layer-banner sections.

    python -m sahacore.data.build_core_equations <path-to-workbook>

NOT A DUPLICATE OF '★ Equation Backbone'. The two overlap on 22 ids and are
written at different levels:

    backbone A1   h_i(τ)=w_i·Γ(τ;k1,λ1)+(1−w_i)·Γ(τ;k2,λ2)
    here     A1   the same, plus the log-gamma form used to evaluate it

The backbone is the wiring summary -- one line per equation, plus what it
reads and feeds. This is the specification: the full formula, its inputs and
outputs, its units, and the corrections applied to it. 29 ids appear only
here (D1-D4, E4-E10, F1-F4, G1-G5, H1-H8: the numbered detail equations) and
35 only in the backbone (ONB, DSC, CHS, M0-M5, QATP...: the named aggregates).
Neither contains the other.

So no formula-equality check is made between them -- they are not two copies
of one statement. What IS checked is that both assign the same layer to a
shared id, which holds for all 22.

THE 'Correction Applied' COLUMN IS THE REASON TO LOAD THIS SHEET. 19 of the
51 equations carry one, and they are engineering history that changes the
implementation:

    B6   "v32.3 FIX: removed redundant f_u (was Q_H*E_H*f_u -- double-counted
          binding)"
    C2   "p = 1 enforced (not p = 2)"
    C6   "P0-8: competitive MM (was independent)"
    C4   "UNITS FIX. The sedentary term was a rate multiplied by dt and added
          to a stock outside..."

Each records a mistake someone already made in this equation. Anyone
implementing it needs them more than they need the formula.
"""
import json
import sys
from pathlib import Path

import openpyxl

SHEET = "P1 Core Equations"
HEADER_ROW = 6
FIRST_COL = 2
OUT = Path(__file__).parent / "core_equations.json"

COLUMNS = ["eq_id", "layer", "name", "formula", "inputs", "outputs", "units",
           "correction_applied"]
LABELS = ["ID", "Layer", "Name", "Formula", "Inputs", "Outputs", "Units",
          "Correction Applied"]

EXPECTED_ROWS = 51
EXPECTED_CORRECTIONS = 19


def _cell(ws, row: int, col: int) -> str | None:
    value = ws.cell(row=row, column=col).value
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def extract(workbook_path: str) -> list[dict]:
    ws = openpyxl.load_workbook(workbook_path, data_only=True)[SHEET]

    got = [_cell(ws, HEADER_ROW, c) for c in range(FIRST_COL, FIRST_COL + len(LABELS))]
    if got != LABELS:
        raise SystemExit(f"{SHEET} header changed: expected {LABELS}, got {got}")

    rows = []
    for r in range(HEADER_ROW + 1, ws.max_row + 1):
        eq_id = _cell(ws, r, FIRST_COL)
        layer = _cell(ws, r, FIRST_COL + 1)
        # Layer-section banners ("LAYER A: NUTRIENT ABSORPTION (7 equations)")
        # occupy the id column alone; a real row has both an id and a layer.
        if not eq_id or not layer or eq_id == "ID":
            continue
        row = {"source_row": r}
        for i, col in enumerate(COLUMNS, start=FIRST_COL):
            row[col] = _cell(ws, r, i)
        rows.append(row)
    return rows


def check(rows: list[dict]) -> None:
    if len(rows) != EXPECTED_ROWS:
        raise SystemExit(f"expected {EXPECTED_ROWS} equations, got {len(rows)}")

    ids = [r["eq_id"] for r in rows]
    if len(set(ids)) != len(ids):
        repeated = sorted({i for i in ids if ids.count(i) > 1})
        raise SystemExit(f"eq_id repeats here: {repeated}")

    for r in rows:
        if not r["formula"]:
            raise SystemExit(f"{r['eq_id']} has no formula")

    corrections = [r for r in rows if r["correction_applied"]]
    if len(corrections) != EXPECTED_CORRECTIONS:
        raise SystemExit(
            f"{len(corrections)} equations carry a correction, expected "
            f"{EXPECTED_CORRECTIONS}. A correction appearing or vanishing is "
            "engineering history and must be looked at.")

    # The two equation sheets must at least agree on which layer an id is in.
    backbone = json.loads(
        (Path(__file__).parent / "equation_backbone.json").read_text(encoding="utf-8"))
    bb: dict[str, list[str]] = {}
    for b in backbone:
        bb.setdefault(b["eq_id"], []).append(b["layer"])
    for r in rows:
        layers = bb.get(r["eq_id"])
        if layers and not any(L.startswith(r["layer"]) for L in layers):
            raise SystemExit(
                f"{r['eq_id']}: this sheet says layer {r['layer']!r}, "
                f"'★ Equation Backbone' says {layers}")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m sahacore.data.build_core_equations <workbook.xlsx>")

    rows = extract(sys.argv[1])
    check(rows)
    OUT.write_text(json.dumps(rows, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    layers: dict[str, int] = {}
    for r in rows:
        layers[r["layer"]] = layers.get(r["layer"], 0) + 1
    print(f"wrote {len(rows)} equations to {OUT.name}")
    print("   by layer:", dict(sorted(layers.items())))
    print(f"   carrying a recorded correction: "
          f"{sum(1 for r in rows if r['correction_applied'])}")


if __name__ == "__main__":
    main()
