"""Extracts '03_STATE_ADMISSION_GATES' and '04_BEHAVIOR_SIDECAR' into
state_admission.json.

Sources: v39sEng2.xlsx. '01_IMPORT_MANIFEST' orders 198 and 199, roles
CONTROL_VALIDATION and FEATURE_STORE_CONTRACT, both import YES, backend Yes.
They are the last two registries build step 2 names.

    python -m sahacore.data.build_state_admission <path-to-workbook>

WHAT THESE TWO SHEETS DO. They stop the state vector growing. Every request
to model a new behavioural quantity -- "make the 50 activity IDs states",
"add a sleep-regularity state", "four mood states" -- is answered here, and
answered NO, with the reason and the alternative. The constants say it
outright:

    state_delta        0    "Sidecar never changes x_t."
    nonlinear_delta    0    "No new sigma branches."
    baseline_state_n   219  "Do not expand x_t for behavioral categories."
    lifestyle_state_slots 24 at 187:210  "Already fully allocated; no spare."

That is a rule an implementer can break by being helpful. Someone adds mood
as a state because mood clearly matters, the vector becomes 223, and every
stored posterior, checkpoint and replay from before that moment is a
different shape. The sheets are loaded before any layer so the answer is in
the database rather than in whoever read them.

THREE INDEPENDENT SHEETS NOW AGREE ON 219. '★ State Vector v33 (219)' gives
the block map, '00_ENGINEER_START' gives the invariant, and this gives
baseline_state_n with baseline_cov_cells = 47961 = 219^2. The extractor
checks that identity rather than trusting either number.

WHAT IS NOT EXTRACTED. '04_BEHAVIOR_SIDECAR' rows 14-19 are six example
events -- ex_sleep, ex_sed, ex_lpa, ex_walk, ex_res, ex_hiit -- illustrating
the event shape with sample values. They are documentation, not registry
data, and loading them would put fictional activity events in a table beside
real ones.
"""
import json
import sys
from pathlib import Path

import openpyxl

GATES_SHEET = "03_STATE_ADMISSION_GATES"
SIDECAR_SHEET = "04_BEHAVIOR_SIDECAR"
OUT = Path(__file__).parent / "state_admission.json"

# (sheet, header row, first data row, last data row, first column, columns)
BLOCKS = {
    "gate_constants": (GATES_SHEET, 4, 5, 10, 1,
                       ["constant", "value", "formula_or_source",
                        "engineering_meaning", "owner"]),
    "candidates": (GATES_SHEET, 12, 13, 22, 1,
                   ["candidate", "target_representation", "necessity",
                    "sidecar_adequate", "identifiable_observable",
                    "init_burden", "replay", "latency", "held_out_evidence"]),
    "admission_rules": (GATES_SHEET, 25, 26, 31, 1,
                        ["rule", "formula_or_implementation", "current_result",
                         "notes"]),
    "sidecar_constants": (SIDECAR_SHEET, 4, 5, 8, 1,
                          ["constant", "value", "formula_or_note", "purpose"]),
    "routing": (SIDECAR_SHEET, 4, 5, 10, 6,
                ["domain", "existing_core_states", "sidecar_raw_feature",
                 "routing"]),
    "derived_features": (SIDECAR_SHEET, 22, 23, 38, 1,
                         ["feature", "value", "formula_text", "routing_meaning"]),
}

EXPECTED = {
    "gate_constants": 6, "candidates": 10, "admission_rules": 6,
    "sidecar_constants": 4, "routing": 6, "derived_features": 16,
}

BASELINE_STATE_N = 219
BASELINE_COV_CELLS = 47961          # 219 * 219


def _cell(ws, row: int, col: int) -> str | None:
    value = ws.cell(row=row, column=col).value
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def extract(workbook_path: str) -> dict:
    wb = openpyxl.load_workbook(workbook_path, data_only=True)
    out = {}
    for key, (sheet, header, first, last, col0, columns) in BLOCKS.items():
        ws = wb[sheet]
        rows = []
        for r in range(first, last + 1):
            values = [_cell(ws, r, c) for c in range(col0, col0 + len(columns))]
            if not any(values):
                continue
            row = {"source_sheet": sheet, "source_row": r}
            row.update(dict(zip(columns, values)))
            rows.append(row)
        out[key] = rows
    return out


def check(data: dict) -> None:
    for key, expected in EXPECTED.items():
        if len(data[key]) != expected:
            raise SystemExit(f"{key}: expected {expected} rows, got {len(data[key])}")

    gates = {r["constant"]: r["value"] for r in data["gate_constants"]}
    if gates.get("baseline_state_n") != str(BASELINE_STATE_N):
        raise SystemExit(f"baseline_state_n is {gates.get('baseline_state_n')!r}")
    # The sheet states the covariance size separately; it must be n^2, and
    # checking is cheaper than trusting two numbers written by hand.
    if gates.get("baseline_cov_cells") != str(BASELINE_COV_CELLS):
        raise SystemExit(
            f"baseline_cov_cells is {gates.get('baseline_cov_cells')!r}, "
            f"not {BASELINE_STATE_N}^2 = {BASELINE_COV_CELLS}")

    sidecar = {r["constant"]: r["value"] for r in data["sidecar_constants"]}
    for zero in ("state_delta", "nonlinear_delta"):
        if sidecar.get(zero) != "0":
            raise SystemExit(
                f"{zero} is {sidecar.get(zero)!r}, not '0'. This constant is "
                "the sidecar contract: a non-zero value means the state "
                "vector is being expanded.")

    # Every candidate must carry a verdict, and every rule a result.
    for c in data["candidates"]:
        if not c["target_representation"]:
            raise SystemExit(f"candidate {c['candidate']!r} has no verdict")
    for r in data["admission_rules"]:
        if not r["current_result"]:
            raise SystemExit(f"rule {r['rule']!r} has no current result")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m sahacore.data.build_state_admission <workbook.xlsx>")

    data = extract(sys.argv[1])
    check(data)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    print(f"wrote the state-admission contract to {OUT.name}")
    for key in BLOCKS:
        print(f"   {len(data[key]):>3}  {key}")
    verdicts: dict[str, int] = {}
    for c in data["candidates"]:
        verdicts[c["target_representation"]] = verdicts.get(c["target_representation"], 0) + 1
    print("   candidate verdicts:", dict(sorted(verdicts.items())))


if __name__ == "__main__":
    main()
