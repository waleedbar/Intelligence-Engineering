"""Extracts 'TVMCD · 15 Pathways Build' into tvmcd_pathways_build.json.

Source: v39sEng2.xlsx, sheet 'TVMCD · 15 Pathways Build'.
'01_IMPORT_MANIFEST' order 131, role CORE_ENGINE, import YES, backend Yes.

    python -m sahacore.data.build_tvmcd_pathways <path-to-workbook>

    "TVMCD · 15 Pathways Build — complete server implementation table"

Fifteen pathways D01-D15, each with its state variable, its complete ODE, its
inputs, its parameters, the clusters it feeds, its integration cadence,
numerical method, bounds, and how it is initialised.

WHY THIS SHEET WAS IMPORTED OUT OF ORDER, AND WHAT IT CORRECTS.

An earlier commit reported that the "canonical 15->12 bridge" -- named as a
required step by five sheets and needed by ONB-011 and ONB-012 -- was not in
the workbook. That was wrong, and the way it was wrong is worth recording.

The search that established the absence looked for a sheet carrying both
cluster ids and pathway ids, matching `C1..C12` and `D1..D15`, and required
ten or more distinct ids of each. This sheet writes them ZERO-PADDED --
`C02`, `D01` -- so most did not match.

Not all of them: C10, C11, C12 and D10..D15 need no padding. The sheet scored
3 cluster ids and 6 pathway ids, which is why it was passed over -- under the
threshold rather than absent from the results. A pattern that had scored it
zero would have been easier to distrust than one that scored it low.

Re-run with padding allowed, it is the only sheet in all 205 that carries ten
or more of each. The conclusion "there is exactly one candidate" was right;
the identification was not.

WHAT THE CLUSTER-OUTPUTS COLUMN GIVES, AND WHAT IT DOES NOT.

It gives MEMBERSHIP: which clusters each pathway feeds, two or three each,
for all fifteen. It does not give:

  * WEIGHTS. C12 is fed by eight pathways and C11 by one. Turning fifteen
    pathway warm-start values into twelve cluster values needs a combination
    rule -- mean, max, weighted sum -- and the sheet states none.
  * C01. No pathway lists C01 Membrane Integrity as an output at all, so a
    warm-start driven by this map leaves one of the twelve clusters with
    nothing.
  * THE HI/LO SPLIT. ONB-012 fills twenty-four slots, xi_hi[163:174] and
    xi_lo[175:186], from fifteen values. Nothing here says how.

So ONB-011 and ONB-012 stay blocked -- but for these three specific reasons
rather than for a missing artefact, which is a different and much more
answerable question. See docs/parameter-gaps.md.

THE INITIALIZATION COLUMN POINTS THE OTHER WAY, and is worth reading
carefully: "from O·O11 warm-start or zero with prior covariance for D03".
Each pathway carries its OWN state (logZ_inflam, logZ_AGE, ...) warm-started
from O11. So the cluster-outputs column may describe a runtime aggregation of
pathway states rather than a warm-start remapping. Both readings are
consistent with what is written; the sheet does not settle it.
"""
import json
import re
import sys
from pathlib import Path

import openpyxl

SHEET = "TVMCD · 15 Pathways Build"
FIRST_COL = 1
OUT = Path(__file__).parent / "tvmcd_pathways_build.json"

HEADER_ROW = 2
DATA_ROWS = range(3, 18)
LABELS = ["Pathway ID", "Biological meaning", "State variables",
          "Complete ODE / algebraic equation",
          "Inputs from nutrients / QSSA / activity / labs",
          "Parameters & units", "Cluster outputs", "Integration cadence",
          "Numerical method", "Bounds", "Initialization"]

EXPECTED_PATHWAYS = 15
CLUSTER_ID = re.compile(r"C\d+")

# D14 and D15 are declared GLOBAL_MODIFIER_PENDING elsewhere in the build, and
# 'REG · Organ×Pathway Long' carries no organ weights for them -- which gate
# d14_d15_fail_closed already agrees with. They DO appear here with cluster
# outputs, so the two statements are about different things and both are kept.
PENDING_PATHWAYS = {"D14", "D15"}


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

    for offset, expected in enumerate(LABELS):
        found = _text(_cell(ws, HEADER_ROW, offset))
        if found != expected:
            raise SystemExit(
                f"{SHEET}: header row {HEADER_ROW} column {FIRST_COL + offset} "
                f"reads {found!r}, expected {expected!r}.")

    pathways = []
    for row in DATA_ROWS:
        pathway_id = _text(_cell(ws, row, 0))
        if pathway_id is None:
            continue
        outputs = _text(_cell(ws, row, 6))
        pathways.append({
            "pathway_id": pathway_id,
            "source_row": row,
            "biological_meaning": _text(_cell(ws, row, 1)),
            "state_variable": _text(_cell(ws, row, 2)),
            "ode": _text(_cell(ws, row, 3)),
            "inputs": _text(_cell(ws, row, 4)),
            "parameters": _text(_cell(ws, row, 5)),
            "cluster_outputs": CLUSTER_ID.findall(outputs or ""),
            "cluster_outputs_verbatim": outputs,
            "integration_cadence": _text(_cell(ws, row, 7)),
            "numerical_method": _text(_cell(ws, row, 8)),
            "bounds": _text(_cell(ws, row, 9)),
            "initialization": _text(_cell(ws, row, 10)),
        })

    wb.close()

    # The inverse map, which is what a warm-start would read: cluster -> the
    # pathways that feed it, in the order the sheet lists them.
    fed_by: dict[str, list[str]] = {f"C{n:02d}": [] for n in range(1, 13)}
    for pathway in pathways:
        for cluster in pathway["cluster_outputs"]:
            fed_by.setdefault(cluster, []).append(pathway["pathway_id"])

    return {
        "sheet": SHEET,
        "pathways": pathways,
        "cluster_fed_by": fed_by,
        "clusters_with_no_pathway": sorted(c for c, p in fed_by.items() if not p),
        "weights_given": False,
        "hi_lo_split_given": False,
    }


def check(data: dict) -> None:
    pathways = data["pathways"]
    if len(pathways) != EXPECTED_PATHWAYS:
        raise SystemExit(f"{SHEET}: expected {EXPECTED_PATHWAYS} pathways, "
                         f"got {len(pathways)}.")
    expected = [f"D{n:02d}" for n in range(1, EXPECTED_PATHWAYS + 1)]
    if [p["pathway_id"] for p in pathways] != expected:
        raise SystemExit(f"{SHEET}: pathways are not D01..D15: "
                         f"{[p['pathway_id'] for p in pathways]}")

    for pathway in pathways:
        for field in ("state_variable", "ode", "cluster_outputs_verbatim",
                      "integration_cadence", "numerical_method", "bounds",
                      "initialization"):
            if not pathway[field]:
                raise SystemExit(
                    f"{SHEET}: {pathway['pathway_id']} has no {field}. This is "
                    "the complete implementation table; an empty column means "
                    "it is not complete.")
        if not pathway["cluster_outputs"]:
            raise SystemExit(
                f"{SHEET}: {pathway['pathway_id']} lists no cluster outputs.")
        for cluster in pathway["cluster_outputs"]:
            if not re.fullmatch(r"C0[1-9]|C1[0-2]", cluster):
                raise SystemExit(
                    f"{SHEET}: {pathway['pathway_id']} outputs to {cluster!r}, "
                    "which is not a zero-padded C01..C12.")

    # The gap that keeps ONB-011 blocked, asserted so it cannot be forgotten
    # if the sheet is re-read casually.
    orphaned = data["clusters_with_no_pathway"]
    if orphaned != ["C01"]:
        raise SystemExit(
            f"{SHEET}: clusters with no contributing pathway are {orphaned}, "
            "expected exactly ['C01']. If this changed, the warm-start's "
            "coverage changed with it.")

    # No column carries a numeric weight per (pathway, cluster). If one
    # appears, the combination rule may have been supplied.
    for pathway in pathways:
        if re.search(r"C\d+\s*[:=]\s*[0-9.]", pathway["cluster_outputs_verbatim"]):
            raise SystemExit(
                f"{SHEET}: {pathway['pathway_id']}'s cluster outputs now look "
                "weighted: {pathway['cluster_outputs_verbatim']!r}. Re-read "
                "the sheet -- weights_given may no longer be False.")

    # Every pathway is warm-started from O11, which is what ties this sheet to
    # ONB-011 at all.
    warm_started = [p for p in pathways if "O·O11" in (p["initialization"] or "")]
    if len(warm_started) != EXPECTED_PATHWAYS:
        raise SystemExit(
            f"{SHEET}: only {len(warm_started)} of {EXPECTED_PATHWAYS} "
            "pathways name O·O11 as their warm start.")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m sahacore.data.build_tvmcd_pathways "
                         "<path-to-workbook>")
    data = extract(sys.argv[1])
    check(data)
    OUT.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")

    counts = {c: len(p) for c, p in data["cluster_fed_by"].items()}
    busiest = max(counts, key=counts.get)
    print(f"wrote {OUT.name}")
    print(f"  {len(data['pathways'])} pathways D01..D15, each with an ODE, "
          "bounds and a warm start from O·O11")
    print(f"  pathway -> cluster membership for all 15; "
          f"{busiest} is fed by {counts[busiest]}, C11 by {counts['C11']}")
    print(f"  clusters with no contributing pathway: "
          f"{data['clusters_with_no_pathway']}")
    print("  weights: not given.  hi/lo split: not given.")


if __name__ == "__main__":
    main()
