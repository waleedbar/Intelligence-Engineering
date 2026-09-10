"""Extracts '★ Scoped Builds — LTMLE Bandit' into scoped_builds.json.

Source: v39sEng2.xlsx, sheet '★ Scoped Builds — LTMLE Bandit'.
'01_IMPORT_MANIFEST' order 6, role BUILD_CONTRACT, import YES, backend Yes.

    python -m sahacore.data.build_scoped_builds <path-to-workbook>

WHAT THE SHEET IS, in its own words:

    "★ SCOPED BUILDS — LTMLE (Layer G) & Conservative Bandit (Layer H)"
    "The two hardest, highest-stakes builds in the engine."
    "These two are NOT per-tick drop-ins like Layers A-F. LTMLE is an OFFLINE
     BATCH job fitted..."

Layers G and H are build-flow phases 7 and 8. Nothing here can be built for a
long time. It is imported now for one reason, and the reason is the whole
point of importing a contract early:

    SHARED PREREQUISITE 1 · Historical outcome log
    "Both learn from a per-user longitudinal record the ONLINE engine must
     already be writing"

    OPEN FOUNDER DECISION 8 · BOTH
    "confirm the historical outcome log is being written"
    "Prerequisite -- nothing offline can start without it"

"Already writing" is a claim about today, not about phase 7. If the log is
not designed into the ledger while the ledger is young, Layers G and H start
from zero history whenever they are finally built, and no amount of
engineering later recovers the months that were not recorded. That makes this
a Phase-1 concern that happens to be written on a Phase-7 sheet.

WHAT THIS BUILD ACTUALLY HAS is recorded per prerequisite in PREREQUISITE_
STATUS below, in the same spirit as validation_test.coverage: a claim has to
name the thing that satisfies it. One of the three is in place.

EIGHT OPEN FOUNDER DECISIONS are extracted verbatim. The sheet marks them
"required BEFORE code starts", and decision 5 -- the bandit's reward proxy --
carries its own note calling it "the single biggest decision". None of them
is answered here; answering one would be inventing product policy.
"""
import json
import sys
from pathlib import Path

import openpyxl

from sahacore.data.sheet_header import check_header

SHEET = "★ Scoped Builds — LTMLE Bandit"
FIRST_COL = 2
OUT = Path(__file__).parent / "scoped_builds.json"

WARNING_ROW = 5
PREREQUISITE_ROWS = range(8, 11)

# item id -> (title row, attribute rows). The attribute pane is two columns:
# the name in B and the text in C. A row with B and no C inside an item block
# is a note the sheet interleaves, not an attribute.
ITEM_BLOCKS: dict[str, tuple[int, range]] = {
    "ITEM 1": (12, range(13, 21)),
    "ITEM 2": (22, range(23, 31)),
}

DECISION_HEADER_ROW = 33
DECISION_ROWS = range(34, 42)
DECISION_LABELS = ["#", "Item · decision needed"]

EXTERNAL_SPEC_ROW = 43

# Every scoped item must carry these. A contract missing its I/O or its
# acceptance criteria is not buildable, and silently importing one that is
# would hide that.
REQUIRED_ATTRIBUTES = (
    "Execution plane / cadence",
    "What & why",
    "Algorithm (buildable)",
    "I/O contract — INPUTS",
    "I/O contract — OUTPUTS",
    "Acceptance criteria",
    "Effort / risk",
)

EXPECTED_DECISIONS = 8

# ---------------------------------------------------------------------------
# What this repo has against each shared prerequisite. Keyed by the row's
# leading number so a reworded title does not silently keep its status.
PREREQUISITE_STATUS: dict[str, tuple[str, str | None, str]] = {
    "1": (
        "MISSING", None,
        "The ledger writes raw_events, event_quality, controls_u, "
        "measurements_y, checkpoints and replay keys -- exactly what "
        "'★ Build Guide Python' step 1 specifies, and nothing more. There is "
        "no per-user outcome panel and no served-event log. The battery's "
        "I12 (BLOCKING) names served_action_event and served_warning_event, "
        "so those tables are specified somewhere; step 1 does not list them "
        "and nothing in this repo writes them.",
    ),
    "2": (
        "IN_PLACE", "tests/test_firewall.py",
        "The T-1 firewall exists: engine_internal and client_render, the "
        "app_consumer and engine_writer roles, RLS on every client-facing "
        "table, and a suite that attempts the reads this prerequisite "
        "forbids.",
    ),
    "3": (
        "NOT_APPLICABLE_YET", None,
        "Shadow mode governs serving, and nothing is served: there is no "
        "API, no service and no deployment. It becomes live the moment "
        "either layer computes something a user could see.",
    ),
}


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

    check_header(ws, SHEET, DECISION_HEADER_ROW, FIRST_COL, DECISION_LABELS)
    prerequisites = []
    for row in PREREQUISITE_ROWS:
        title = _text(_cell(ws, row, 0))
        detail = _text(_cell(ws, row, 1))
        if not title or not detail:
            raise SystemExit(f"{SHEET}: prerequisite row {row} is incomplete.")
        # '1 · Historical outcome log' -> '1' + 'Historical outcome log'
        number, _, name = title.partition("·")
        number = number.strip()
        status, satisfied_by, note = PREREQUISITE_STATUS.get(
            number, (None, None, None))
        if status is None:
            raise SystemExit(
                f"{SHEET}: prerequisite {number!r} at row {row} has no "
                "recorded status. A new shared prerequisite must be assessed, "
                "not defaulted.")
        prerequisites.append({
            "number": number,
            "name": name.strip(),
            "source_row": row,
            "detail": detail,
            "status": status,
            "satisfied_by": satisfied_by,
            "status_note": note,
        })

    items = []
    for item_id, (title_row, pane) in ITEM_BLOCKS.items():
        title = _text(_cell(ws, title_row, 0))
        if not title or not title.startswith(item_id):
            raise SystemExit(
                f"{SHEET}: row {title_row} reads {title!r}, expected it to "
                f"start with {item_id!r}.")
        attributes, notes = [], []
        for row in pane:
            name = _text(_cell(ws, row, 0))
            value = _text(_cell(ws, row, 1))
            if name is None:
                continue
            if value is None:
                notes.append({"source_row": row, "text": name})
            else:
                attributes.append({"source_row": row, "name": name, "value": value})
        items.append({
            "item_id": item_id,
            "source_row": title_row,
            "title": title,
            "attributes": attributes,
            "notes": notes,
        })

    decisions = []
    for row in DECISION_ROWS:
        number = _text(_cell(ws, row, 0))
        item = _text(_cell(ws, row, 1))
        why = _text(_cell(ws, row, 2))
        if not number or not item or not why:
            raise SystemExit(
                f"{SHEET}: founder decision at row {row} is incomplete "
                f"({number!r}, {item!r}, {why!r}). A decision without a "
                "reason cannot be put to anyone.")
        decisions.append({
            "number": int(number),
            "source_row": row,
            "decision": item,
            "why_it_matters": why,
        })

    warning = _text(_cell(ws, WARNING_ROW, 0))
    external_spec = _text(_cell(ws, EXTERNAL_SPEC_ROW, 0))
    wb.close()

    return {
        "sheet": SHEET,
        "warning": warning,
        "prerequisites": prerequisites,
        "items": items,
        "open_decisions": decisions,
        "external_spec": external_spec,
    }


def check(data: dict) -> None:
    if len(data["prerequisites"]) != 3:
        raise SystemExit(f"{SHEET}: expected 3 shared prerequisites, got "
                         f"{len(data['prerequisites'])}.")

    # The one that is a claim about today rather than about phase 7.
    log = next((p for p in data["prerequisites"] if p["number"] == "1"), None)
    if log is None or "already be writing" not in log["detail"]:
        raise SystemExit(
            f"{SHEET}: prerequisite 1 no longer says the online engine must "
            "ALREADY be writing the outcome log. That wording is the whole "
            "reason this sheet is imported in Phase 1 -- re-read it before "
            "changing this check.")

    for item in data["items"]:
        names = {a["name"] for a in item["attributes"]}
        missing = [r for r in REQUIRED_ATTRIBUTES if r not in names]
        if missing:
            raise SystemExit(
                f"{SHEET}: {item['item_id']} is missing {missing}. A scoped "
                "build without an I/O contract or acceptance criteria is not "
                "buildable.")

    decisions = data["open_decisions"]
    if [d["number"] for d in decisions] != list(range(1, EXPECTED_DECISIONS + 1)):
        raise SystemExit(
            f"{SHEET}: founder decisions are not 1..{EXPECTED_DECISIONS}: "
            f"{[d['number'] for d in decisions]}.")

    eighth = decisions[-1]
    if "outcome log" not in eighth["decision"]:
        raise SystemExit(
            f"{SHEET}: decision 8 used to be the confirmation that the "
            f"historical outcome log is being written; it now reads "
            f"{eighth['decision']!r}.")

    for prerequisite in data["prerequisites"]:
        if prerequisite["status"] == "IN_PLACE" and not prerequisite["satisfied_by"]:
            raise SystemExit(
                f"{SHEET}: prerequisite {prerequisite['number']} claims to be "
                "in place without naming what satisfies it.")
        if not prerequisite["status_note"]:
            raise SystemExit(
                f"{SHEET}: prerequisite {prerequisite['number']} has no note.")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m sahacore.data.build_scoped_builds "
                         "<path-to-workbook>")
    data = extract(sys.argv[1])
    check(data)
    OUT.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")

    statuses = {p["number"]: p["status"] for p in data["prerequisites"]}
    print(f"wrote {OUT.name}")
    print(f"  {len(data['items'])} scoped builds, "
          f"{sum(len(i['attributes']) for i in data['items'])} contract rows")
    print(f"  {len(data['open_decisions'])} open founder decisions, "
          "required before code starts")
    print("  shared prerequisites: "
          + ", ".join(f"{n} {s}" for n, s in sorted(statuses.items())))


if __name__ == "__main__":
    main()
