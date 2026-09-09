"""Extracts the three organ/target registries into organ_registries.json.

Sources: v39sEng2.xlsx, sheets '★ SYS Registry (organs)' (manifest 172),
'REG · Organ×Pathway Long' (112) and '★ Target Registry (versioned)' (114).
All three REGISTRY role, import YES, backend Yes.

    python -m sahacore.data.build_organ_registries <path-to-workbook>

THREE FINDINGS, each recorded rather than smoothed over.

1. TWO SHEETS DISAGREE ABOUT THE ORGAN NAMESPACE. '★ SYS Registry' is marked
   AUTHORITATIVE and says: "Why NOT O1-O12: the O-namespace is occupied by
   onboarding" and "Any NEW organ reference must use a SYS code".
   'REG · Organ×Pathway Long' uses O1-O12 anyway. It predates the ruling --
   the SYS sheet says NEW references -- but the collision is live: `O1` is
   the cardiovascular organ node here and the anthropometrics module in
   'O·O1 Anthropometrics'. Both are loaded as written, and the extractor
   asserts the disagreement still exists, so it cannot be silently resolved
   by an edit in either direction.

2. SYS-n AND C-n ARE NOT THE SAME THING despite sharing numbers. SYS1
   Cardiovascular holds C1 Membrane Integrity; SYS7 Neurological holds C7
   Methylation. Reading the SYS number as a cluster number is a mistake the
   table invites, and the sheet carries its own resolved instance of it:
   SYS11 is Respiratory, because "naming SYS11 Neurological would duplicate
   SYS7 and drop Respiratory entirely".

3. THE ORGAN-PATHWAY MAP STOPS AT D13. 48 links over 12 organs and 13
   pathways -- not 15. D14 and D15 have no organ weights, which is exactly
   what '00_ENGINEER_START' gate `d14_d15_fail_closed` states:
   GLOBAL_MODIFIER_PENDING, "No invented organ weights. Fail closed until
   evidence-locked mapping is signed off." The gate and the data agree, and
   the extractor checks they still do.

THE TARGET REGISTRY USES ITS OWN NUTRIENT NAMES. Six rows; one key
(choline_mg) matches the 81-nutrient registry. coq10_mg and betaine_mg are
supplements with no counterpart there, which '★ Supplement Registry'
independently confirms. The other three -- folate_ug, vitamin_b12_ug,
vitamin_b6_mg -- are the same nutrients the registry calls b9_ug, b12_ug and
b6_mg. Those three are declared as scoped aliases below with their units
checked, in the same style as build_eq_param_fk.ALIASES; nothing is matched
by resemblance.
"""
import json
import sys
from pathlib import Path

import openpyxl

OUT = Path(__file__).parent / "organ_registries.json"

SYS_SHEET, SYS_HEADER, SYS_FIRST, SYS_LAST, SYS_COL = "★ SYS Registry (organs)", 4, 5, 16, 1
SYS_COLUMNS = ["sys_code", "organ_system", "process_cluster", "note"]
SYS_LABELS = ["SYS code", "Organ system", "Process cluster holding C-code", "Note"]

OP_SHEET, OP_HEADER, OP_FIRST, OP_COL = "REG · Organ×Pathway Long", 6, 7, 2
OP_COLUMNS = ["organ_id", "organ_node", "pathway_id", "weight"]
OP_LABELS = ["organ_id", "organ_node", "pathway_id", "weight"]

TR_SHEET, TR_HEADER, TR_FIRST, TR_LAST, TR_COL = "★ Target Registry (versioned)", 5, 6, 11, 2
TR_COLUMNS = ["variable_key", "display_name", "unit", "daily_target",
              "upper_limit", "basis_source", "version"]
TR_LABELS = ["variable_key", "display name", "unit", "daily target",
             "upper limit (UL)", "basis / source", "version"]

EXPECTED = {"sys_registry": 12, "organ_pathway": 48, "targets": 6}

# The organ-pathway map's own namespace, which the SYS registry forbids for
# new references. Kept as a constant so the disagreement is asserted, not
# discovered again.
ORGAN_PATHWAY_NAMESPACE = "O"
SYS_NAMESPACE = "SYS"

# Pathways with no organ weights. The d14_d15_fail_closed gate is why.
PATHWAYS_WITHOUT_ORGAN_WEIGHTS = {"D14", "D15"}

# Target-registry key -> the 81-nutrient registry's key, with the reason.
# Units are checked against the nutrient registry, so a wrong pairing shows
# up as a unit mismatch rather than passing on plausibility.
TARGET_KEY_ALIASES = {
    "folate_ug": ("b9_ug", "the registry names it by vitamin number, "
                           "'Vitamin B9 (Folate)'; this sheet by common name"),
    "vitamin_b12_ug": ("b12_ug", "same nutrient, 'vitamin_' prefix dropped "
                                 "in the registry"),
    "vitamin_b6_mg": ("b6_mg", "same nutrient, 'vitamin_' prefix dropped"),
}
# Keys with no counterpart in the 81, confirmed by '★ Supplement Registry'.
SUPPLEMENT_ONLY_TARGETS = {"coq10_mg", "betaine_mg"}


def _cell(ws, row, col):
    value = ws.cell(row=row, column=col).value
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _table(ws, header_row, first, last, col0, columns, labels, what):
    got = [_cell(ws, header_row, c) for c in range(col0, col0 + len(labels))]
    if got != labels:
        raise SystemExit(f"{what} header changed: expected {labels}, got {got}")
    rows = []
    end = last if last is not None else ws.max_row
    for r in range(first, end + 1):
        values = [_cell(ws, r, c) for c in range(col0, col0 + len(columns))]
        if not values[0]:
            continue
        row = {"source_row": r}
        row.update(dict(zip(columns, values)))
        rows.append(row)
    return rows


def extract(workbook_path):
    wb = openpyxl.load_workbook(workbook_path, data_only=True)
    return {
        "sys_registry": _table(wb[SYS_SHEET], SYS_HEADER, SYS_FIRST, SYS_LAST,
                               SYS_COL, SYS_COLUMNS, SYS_LABELS, SYS_SHEET),
        "organ_pathway": _table(wb[OP_SHEET], OP_HEADER, OP_FIRST, None,
                                OP_COL, OP_COLUMNS, OP_LABELS, OP_SHEET),
        "targets": _table(wb[TR_SHEET], TR_HEADER, TR_FIRST, TR_LAST,
                          TR_COL, TR_COLUMNS, TR_LABELS, TR_SHEET),
    }


def check(data):
    for key, expected in EXPECTED.items():
        if len(data[key]) != expected:
            raise SystemExit(f"{key}: expected {expected} rows, got {len(data[key])}")

    sys_codes = [r["sys_code"] for r in data["sys_registry"]]
    if sys_codes != [f"SYS{n}" for n in range(1, 13)]:
        raise SystemExit(f"SYS codes are not SYS1..SYS12: {sys_codes}")

    # Finding 1: the two sheets still disagree about the namespace.
    organs = {r["organ_id"] for r in data["organ_pathway"]}
    if not all(o.startswith(ORGAN_PATHWAY_NAMESPACE) and not o.startswith(SYS_NAMESPACE)
               for o in organs):
        raise SystemExit(
            "'REG · Organ×Pathway Long' no longer uses the O namespace. If it "
            "moved to SYS codes the disagreement with '★ SYS Registry' is "
            "resolved and this check, and the docs, should say so.")

    # Finding 3: no organ weights for D14/D15, matching the fail-closed gate.
    pathways = {r["pathway_id"] for r in data["organ_pathway"]}
    leaked = pathways & PATHWAYS_WITHOUT_ORGAN_WEIGHTS
    if leaked:
        raise SystemExit(
            f"organ weights appeared for {sorted(leaked)}, which "
            "'00_ENGINEER_START' gate d14_d15_fail_closed holds pending: "
            "'No invented organ weights. Fail closed until evidence-locked "
            "mapping is signed off.'")

    for r in data["organ_pathway"]:
        if r["weight"] is None:
            raise SystemExit(f"organ-pathway row {r['source_row']} has no weight")

    # The target registry's keys resolve, are declared aliases, or are
    # supplement-only.
    nutrients = {n["id"]: n["unit"] for n in json.loads(
        (Path(__file__).parent / "nutrients_81.json").read_text(encoding="utf-8"))}
    for t in data["targets"]:
        key = t["variable_key"]
        if key in nutrients or key in SUPPLEMENT_ONLY_TARGETS:
            continue
        if key not in TARGET_KEY_ALIASES:
            raise SystemExit(
                f"target key {key!r} is neither a nutrient, a declared alias, "
                "nor a known supplement-only entry")
        target = TARGET_KEY_ALIASES[key][0]
        if target not in nutrients:
            raise SystemExit(f"alias {key!r} -> {target!r} is not a nutrient")

    for t in data["targets"]:
        if not t["upper_limit"] or not t["basis_source"]:
            raise SystemExit(f"{t['variable_key']} states no upper limit or basis")


def main():
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m sahacore.data.build_organ_registries <workbook.xlsx>")
    data = extract(sys.argv[1])
    check(data)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    pathways = sorted({r["pathway_id"] for r in data["organ_pathway"]},
                      key=lambda p: int(p[1:]))
    print(f"wrote three organ/target registries to {OUT.name}")
    print(f"   {len(data['sys_registry']):>3}  organ systems SYS1..SYS12")
    print(f"   {len(data['organ_pathway']):>3}  organ-pathway links, "
          f"{len({r['organ_id'] for r in data['organ_pathway']})} organs x "
          f"{len(pathways)} pathways ({pathways[0]}..{pathways[-1]})")
    print(f"   {len(data['targets']):>3}  daily targets with upper limits")
    print(f"   D14/D15 organ weights: none, per d14_d15_fail_closed")


if __name__ == "__main__":
    main()
