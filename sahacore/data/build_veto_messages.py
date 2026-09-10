"""Extracts 'MERGE·VETO FDA Messages' into veto_messages.json.

Source: v39sEng2.xlsx, sheet 'MERGE·VETO FDA Messages' -- "03 · FDA Messages
— 24 templates. Upload to veto_messages." '01_IMPORT_MANIFEST' order 175,
role REGISTRY, import YES, backend Yes.

    python -m sahacore.data.build_veto_messages <path-to-workbook>

WHAT IT CLOSES. engine_internal.veto_drug_nutrient has carried a message_id
on all 339 rules since it was loaded, pointing at nothing. These are the 24
templates it points at, and the correspondence is exact: 24 templates, 24
distinct ids used by the rules, none used without a template and none
written without a user. So the column becomes a real foreign key rather than
a string that looks like one.

WHY THE WORDING IS THE POINT. These are what a person actually reads when a
drug-nutrient interaction fires, and the sheet's own framing -- the FDA
messages -- is regulatory. The body of MSG-CRITICAL-AVOID begins "Safety
first — we've left ... out for now", and every critical template ends in
"Discuss with your prescriber". None of them gives dosing guidance, which is
the constraint the whole VETO library is built to respect. Transcribed
verbatim; nothing here is paraphrased or shortened.
"""
import json
import sys
from pathlib import Path

import openpyxl

from sahacore.data.sheet_header import check_header

SHEET = "MERGE·VETO FDA Messages"
HEADER_ROW = 5
OUT = Path(__file__).parent / "veto_messages.json"

COLUMNS = ["message_id", "severity", "action", "title", "body_template", "cta"]
LABELS = ["message_id", "severity", "action", "title", "body_template", "cta"]

EXPECTED_ROWS = 24

# The professionals the CRITICAL templates hand off to. Read off the sheet
# rather than assumed: MSG-CRITICAL-SEPARATE says "Your pharmacist can..."
# and names no prescriber, which a narrower list wrongly flagged.
REFERS_TO = {"prescriber", "pharmacist", "clinician", "doctor"}

# One CRITICAL template refers the reader to nobody, and it is a finding
# rather than a defect in the check above.
#
# MSG-CRITICAL-STABLE reads in full: "Safety first — with {medication},
# keeping your {nutrient} intake steady day to day helps things stay
# consistent — aim for a similar amount rather than big swings." Its CTA is
# "Learn more". No prescriber, no pharmacist.
#
# Two rules render it, both CRITICAL: VETO-DN-0265 (insulin x carbohydrate
# intake) and VETO-DN-0267 (sulfonylureas x carbohydrate intake). Both rules'
# OWN action column reads "STABLE PATTERN — discuss with prescriber". So the
# rule mandates a referral and the template that renders it drops one, on the
# two interactions where a carbohydrate swing is a hypoglycaemia risk.
#
# The build does not fix this -- rewriting a regulated message is not an
# engineering decision -- and does not hide it. It is pinned here so a NEW
# referral-less CRITICAL template fails the load, and reported in
# docs/parameter-gaps.md for the workbook's author.
CRITICAL_WITHOUT_REFERRAL = {"MSG-CRITICAL-STABLE"}


def _cell(ws, row: int, col: int) -> str | None:
    value = ws.cell(row=row, column=col).value
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def extract(workbook_path: str) -> list[dict]:
    ws = openpyxl.load_workbook(workbook_path, data_only=True)[SHEET]

    check_header(ws, SHEET, HEADER_ROW, 1, LABELS)

    rows = []
    for r in range(HEADER_ROW + 1, ws.max_row + 1):
        message_id = _cell(ws, r, 1)
        if not message_id or not message_id.startswith("MSG-"):
            continue
        row = {"source_row": r}
        for i, col in enumerate(COLUMNS, start=1):
            row[col] = _cell(ws, r, i)
        rows.append(row)
    return rows


def check(rows: list[dict]) -> None:
    if len(rows) != EXPECTED_ROWS:
        raise SystemExit(f"expected {EXPECTED_ROWS} templates, got {len(rows)}")

    ids = [r["message_id"] for r in rows]
    if len(set(ids)) != len(ids):
        raise SystemExit("message_id is not unique")

    for r in rows:
        for required in ("severity", "action", "title", "body_template"):
            if not r[required]:
                raise SystemExit(f"{r['message_id']} has no {required}")

    # The correspondence with the VETO library must be exact in both
    # directions: a rule pointing at a template nobody wrote would show the
    # user nothing, and a template no rule uses is either dead or a rule is
    # missing.
    veto = json.loads(
        (Path(__file__).parent / "veto_drug_nutrient_339.json").read_text(encoding="utf-8"))
    used = {v["message_id"] for v in veto}
    orphan_rules = used - set(ids)
    if orphan_rules:
        raise SystemExit(f"VETO rules reference templates that do not exist: {sorted(orphan_rules)}")
    unused = set(ids) - used
    if unused:
        raise SystemExit(f"templates no VETO rule uses: {sorted(unused)}")

    # Every CRITICAL template must send the person to a qualified human. That
    # is the library's whole posture -- flag and defer, never advise -- and
    # the sheet keeps it: all seven CRITICAL bodies name a prescriber or a
    # pharmacist, and none gives a dose.
    silent = set()
    for r in rows:
        if r["severity"] == "CRITICAL":
            text = f"{r['body_template']} {r['cta'] or ''}".lower()
            if not any(who in text for who in REFERS_TO):
                silent.add(r["message_id"])
    if silent != CRITICAL_WITHOUT_REFERRAL:
        raise SystemExit(
            f"CRITICAL templates naming no professional are {sorted(silent)}, "
            f"not {sorted(CRITICAL_WITHOUT_REFERRAL)}. Each one is a rule "
            "whose action says 'discuss with prescriber' rendering a message "
            "that does not.")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m sahacore.data.build_veto_messages <workbook.xlsx>")

    rows = extract(sys.argv[1])
    check(rows)
    OUT.write_text(json.dumps(rows, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    sev: dict[str, int] = {}
    for r in rows:
        sev[r["severity"]] = sev.get(r["severity"], 0) + 1
    print(f"wrote {len(rows)} message templates to {OUT.name}")
    print("   by severity:", dict(sorted(sev.items())))
    print("   actions:", sorted({r["action"] for r in rows}))


if __name__ == "__main__":
    main()
