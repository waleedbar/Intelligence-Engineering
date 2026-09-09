"""Extracts 'P1 DataMap' sections A and B into datamap.json.

Source: v39sEng2.xlsx, sheet 'P1 DataMap'.
'01_IMPORT_MANIFEST' order 25, role CORE_ENGINE, import YES, backend Yes.

    python -m sahacore.data.build_datamap <path-to-workbook>

The sheet holds five sections with five different column layouts. Two are
extracted here and three are deliberately not:

  A  engine variables    r7-r102. Variable, layer, equations, description,
                         physiological meaning, units, typical range, and --
                         the column that earns the import -- Data Source.
  B  onboarding fields   r107-r169. Each onboarding screen field mapped to the
                         engine variable it sets, the layer and equations it
                         feeds, the mapping logic, the default when the user
                         skips it, and a P0/P1 priority.

  C  data-source categories, D  the 127 actions, E  layer interconnections.
     Not extracted. D restates engine_internal.action_space, which is loaded
     from 'Action_Space' itself; E restates the inputs and outputs columns of
     '★ Equation Backbone', already loaded. Importing a second copy of either
     would create two records that can disagree. C is integration metadata
     (APIs, measurement CV%) with no consumer in this build yet.

WHY THE DATA SOURCE COLUMN MATTERS. It separates 'Parameter' and 'Parameter
Table' from 'Computed', 'Input', 'Diet Logging' and 'Onboarding'. This build
spent effort reporting `CL` as a missing parameter when it is computed, and
this column is where that distinction is written down for every variable at
once. It is the antidote to the same mistake elsewhere.

THE BANNERS OVERSTATE THE ROW COUNTS. Section A's banner reads "158+ ENGINE
VARIABLES" over 96 rows; section B's reads "105 ONBOARDING FIELDS" over 63;
the sheet title says "227 items" over 212 data rows in all five sections.
Some rows do name two variables at once ("k₁, λ₁"), which accounts for part
of it, but not all. The extractor records both numbers -- what the banner
claims and what is there -- rather than picking one. See
docs/parameter-gaps.md.
"""
import json
import sys
from pathlib import Path

import openpyxl

SHEET = "P1 DataMap"
FIRST_COL = 2
OUT = Path(__file__).parent / "datamap.json"

VARIABLE_HEADER_ROW = 6
VARIABLE_FIRST, VARIABLE_LAST = 7, 102
VARIABLE_COLUMNS = ["variable", "layer", "equations", "full_description",
                    "physiological_meaning", "units", "typical_range",
                    "data_source", "specific_source", "update_frequency"]
VARIABLE_LABELS = ["Variable", "Layer", "Equation(s)", "Full Description",
                   "Physiological Meaning", "Units", "Typical Range",
                   "Data Source", "Specific Source", "Update Freq"]

ONBOARDING_HEADER_ROW = 105
ONBOARDING_FIRST, ONBOARDING_LAST = 107, 169
ONBOARDING_COLUMNS = ["step", "screen", "field_name", "input_type",
                      "engine_variable", "target_layer", "equations",
                      "mapping_logic", "default_if_missing", "priority"]
ONBOARDING_LABELS = ["Step", "Screen", "Field Name", "Input Type",
                     "Engine Variable", "Target Layer", "Equation(s)",
                     "Mapping Logic", "Default if Missing", "Priority"]

# What the sheet's own banners claim, against what it holds. Both are kept.
CLAIMED_VARIABLES = "158+ ENGINE VARIABLES"
CLAIMED_ONBOARDING = "105 ONBOARDING FIELDS"
ACTUAL_VARIABLES = 96

# The single section-A row whose Variable cell is empty.
UNNAMED_VARIABLE_ROW = 8
ACTUAL_ONBOARDING = 63


def _cell(ws, row: int, col: int) -> str | None:
    value = ws.cell(row=row, column=col).value
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _check_header(ws, row: int, labels: list[str], what: str) -> None:
    got = [_cell(ws, row, c) for c in range(FIRST_COL, FIRST_COL + len(labels))]
    if got != labels:
        raise SystemExit(f"{SHEET} {what} header changed: expected {labels}, got {got}")


def _section(ws, first: int, last: int, columns: list[str],
             key_column: str) -> list[dict]:
    rows = []
    for r in range(first, last + 1):
        values = [_cell(ws, r, c) for c in range(FIRST_COL, FIRST_COL + len(columns))]
        if not any(values):
            continue
        row = {"source_row": r}
        row.update(dict(zip(columns, values)))
        # A repeated header inside the block would otherwise load as data.
        if row[key_column] and row[key_column] in (columns[0], "Variable", "Step"):
            continue
        rows.append(row)
    return rows


def extract(workbook_path: str) -> dict:
    ws = openpyxl.load_workbook(workbook_path, data_only=True)[SHEET]
    _check_header(ws, VARIABLE_HEADER_ROW, VARIABLE_LABELS, "variable")
    _check_header(ws, ONBOARDING_HEADER_ROW, ONBOARDING_LABELS, "onboarding")
    return {
        "variables": _section(ws, VARIABLE_FIRST, VARIABLE_LAST,
                              VARIABLE_COLUMNS, "variable"),
        "onboarding_fields": _section(ws, ONBOARDING_FIRST, ONBOARDING_LAST,
                                      ONBOARDING_COLUMNS, "step"),
    }


def check(data: dict) -> None:
    variables, fields = data["variables"], data["onboarding_fields"]

    if len(variables) != ACTUAL_VARIABLES:
        raise SystemExit(f"expected {ACTUAL_VARIABLES} variables, got {len(variables)}")
    if len(fields) != ACTUAL_ONBOARDING:
        raise SystemExit(f"expected {ACTUAL_ONBOARDING} onboarding fields, got {len(fields)}")

    for v in variables:
        if not v["layer"]:
            raise SystemExit(f"row {v['source_row']} has no layer")

    # One row carries a description and no symbol: r8, "Gamma shape
    # parameter", Layer A, equation A1. The symbol is almost certainly `k`,
    # which the next rows use -- and "almost certainly" is why it is not
    # filled in. It is kept with a null variable and reported, exactly as the
    # supplement registry's unfinished Betaine row is.
    unnamed = [v["source_row"] for v in variables if not v["variable"]]
    if unnamed != [UNNAMED_VARIABLE_ROW]:
        raise SystemExit(
            f"rows with no variable symbol are {unnamed}, not "
            f"[{UNNAMED_VARIABLE_ROW}]. A new one is a gap in the source that "
            "must be reported rather than absorbed.")
    for f in fields:
        if not f["field_name"] or not f["engine_variable"]:
            raise SystemExit(
                f"row {f['source_row']} has no field name or engine variable")

    # Every onboarding field must say what happens when the user skips it.
    # A blank there is a silent default chosen by whoever writes Layer 0.
    missing_default = [f["field_name"] for f in fields if not f["default_if_missing"]]
    if missing_default:
        raise SystemExit(
            f"onboarding fields with no stated default if missing: {missing_default}")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m sahacore.data.build_datamap <workbook.xlsx>")

    data = extract(sys.argv[1])
    check(data)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    sources: dict[str, int] = {}
    for v in data["variables"]:
        sources[v["data_source"] or "(blank)"] = sources.get(v["data_source"] or "(blank)", 0) + 1
    priorities: dict[str, int] = {}
    for f in data["onboarding_fields"]:
        priorities[f["priority"] or "(blank)"] = priorities.get(f["priority"] or "(blank)", 0) + 1

    print(f"wrote {len(data['variables'])} engine variables and "
          f"{len(data['onboarding_fields'])} onboarding fields to {OUT.name}")
    print(f"   section A banner claims {CLAIMED_VARIABLES}, holds "
          f"{len(data['variables'])} rows")
    print(f"   section B banner claims {CLAIMED_ONBOARDING}, holds "
          f"{len(data['onboarding_fields'])} rows")
    print("   Data Source:", dict(sorted(sources.items(), key=lambda kv: -kv[1])[:8]))
    print("   onboarding priority:", dict(sorted(priorities.items())))


if __name__ == "__main__":
    main()
