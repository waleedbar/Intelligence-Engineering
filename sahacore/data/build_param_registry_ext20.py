"""Extracts the 20-parameter registry extension into param_registry_ext20.json.

Source: v39sEng2.xlsx, sheet '★ Param Registry +20' -- "★ Parameter Registry
— 20 new". Header at row 3, parameters at rows 4-23. Columns: Parameter |
Symbol | Unit | Default | Calibration source.

    python -m sahacore.data.build_param_registry_ext20 <path-to-workbook>

WHY IT IS A SECOND TABLE RATHER THAN 20 MORE ROWS IN parameter_registry. The
192-row registry from 'P1 Parameters 134+' is keyed on the sheet's own
parameter number. This sheet has no number column. Merging would mean issuing
20 numbers that the workbook never assigned, and this build does not invent
identifiers -- so the extension keeps its own table and its own source row as
the key, and engine_internal.parameter_all unions the two for anyone who just
wants "every parameter the engine knows".

WHAT IT CLOSES. Six of these were reported by this build as absent, on the
strength of having read 'P1 Parameters 134+', 'M-PARAM Registry' and the FK
sheet and not found them:

    alpha_scar        MISSING_FK on K3-FIX-01   here as alpha_scar,k, 0.001-0.01 /day
    beta_autophagy    MISSING_FK on K3-FIX-01   here as beta_autophagy,k, 1e-4-1e-3 /day
    delta (Hawkes)    OTHER_LAYER on K3-FIX-04  here as delta_i, 0.3/event
    mu_base           reported as owed          here, 0.05
    nu_D              reported as owed          here, 0.15
    kappa_D           reported as owed          here, 0.1

They were never missing from the workbook. They were missing from what this
build had imported, which is a different statement and the one that should
have been made. '01_IMPORT_MANIFEST' lists this sheet at order 21 with import
status YES; it simply had not been reached. docs/parameter-gaps.md records
the correction.

FIVE ROWS HAVE NO SYMBOL. The sheet writes an em-dash for the warning
cool-down, the maximum warnings per week, the F1 suppression threshold and
the Levy window -- they are policy constants named in prose rather than
symbols. They are kept with a null symbol rather than given one.
"""
import json
import sys
from pathlib import Path

import openpyxl

from sahacore.data.sheet_header import check_header

SHEET = "★ Param Registry +20"
HEADER_ROW = 3
OUT = Path(__file__).parent / "param_registry_ext20.json"

COLUMNS = ["parameter", "symbol", "unit", "default_or_range", "calibration_source"]
HEADER_LABELS = ["Parameter", "Symbol", "Unit", "Default", "Calibration source"]

# The sheet's own title says twenty.
EXPECTED_ROWS = 20

# The em-dash the sheet uses where a row has no symbol of its own.
NO_SYMBOL = "—"


def _cell(ws, row: int, col: int) -> str | None:
    value = ws.cell(row=row, column=col).value
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def extract(workbook_path: str) -> list[dict]:
    ws = openpyxl.load_workbook(workbook_path, data_only=True)[SHEET]

    check_header(ws, SHEET, HEADER_ROW, 1, HEADER_LABELS)

    rows = []
    for r in range(HEADER_ROW + 1, ws.max_row + 1):
        if _cell(ws, r, 1) is None:
            continue
        row = {"source_row": r}
        for i, name in enumerate(COLUMNS, start=1):
            row[name] = _cell(ws, r, i)
        if row["symbol"] == NO_SYMBOL:
            row["symbol"] = None          # a policy constant, not a symbol
        rows.append(row)
    return rows


def check(rows: list[dict]) -> None:
    if len(rows) != EXPECTED_ROWS:
        raise SystemExit(
            f"the sheet is titled '20 new' but {len(rows)} rows were extracted")
    for r in rows:
        if not r["parameter"] or not r["default_or_range"]:
            raise SystemExit(f"row {r['source_row']} has no parameter name or default")
    symbols = [r["symbol"] for r in rows if r["symbol"]]
    if len(set(symbols)) != len(symbols):
        raise SystemExit("symbols are not unique among the rows that have one")

    # These are the six this build had reported absent. If a rename ever
    # removes one, the claim in docs/parameter-gaps.md stops being true and
    # this says so rather than letting the correction rot.
    closes = {"α_scar,k", "β_autophagy,k", "δ_i", "μ_base", "ν_D", "κ_D"}
    absent = closes - set(symbols)
    if absent:
        raise SystemExit(
            f"these were recorded as closed by this sheet and are no longer in it: "
            f"{sorted(absent)}")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(
            "usage: python -m sahacore.data.build_param_registry_ext20 <workbook.xlsx>")

    rows = extract(sys.argv[1])
    check(rows)
    OUT.write_text(json.dumps(rows, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    print(f"wrote {len(rows)} extension parameters to {OUT.name}")
    print(f"   with a symbol            : {sum(1 for r in rows if r['symbol'])}")
    print(f"   policy constants, no symbol: {sum(1 for r in rows if not r['symbol'])}")
    for r in rows:
        print(f"   {str(r['symbol'] or '(policy)'):<16}{str(r['default_or_range']):<16}"
              f"{r['parameter']}")


if __name__ == "__main__":
    main()
