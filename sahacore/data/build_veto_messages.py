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

ONE TEMPLATE IS CHANGED, AND ONLY BY WRITTEN INSTRUCTION. MSG-CRITICAL-STABLE
named no professional while both rules that render it demand a prescriber.
That was reported, and the sheet's clinical owner decided it rather than this
build. See AUTHORISED_OVERRIDES below: the change is an appended sentence, the
workbook's own text travels beside it in source_body_template, and the row
says who decided it and when.
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

# ---------------------------------------------------------------------------
# AUTHORISED CHANGES TO A RENDERED MESSAGE.
#
# This build transcribes the workbook and does not edit it. The one exception
# is a change the workbook's clinical owner has asked for in writing, and an
# exception is only safe if it cannot be mistaken for the source later. So
# each one is declared here with who decided it, when, what they said, and
# what exactly it does -- and it travels into the database as an overridden
# row rather than as an indistinguishable one.
#
# THE DECISION. MSG-CRITICAL-STABLE read, in full: "Safety first — with
# {medication}, keeping your {nutrient} intake steady day to day helps things
# stay consistent — aim for a similar amount rather than big swings." CTA
# "Learn more". It named no prescriber and no pharmacist -- the only CRITICAL
# template that named nobody.
#
# Two rules render it, both CRITICAL, and both are hypoglycaemia risks:
# VETO-DN-0265 (insulin x carbohydrate intake, "Insulin dosing matched to
# carb intake; sudden changes risk hypoglycemia") and VETO-DN-0267
# (sulfonylureas x carbohydrate intake, "Hypoglycemia risk if meal skipped").
# BOTH rules' own action column reads "STABLE PATTERN — discuss with
# prescriber". So the rule mandated a referral and the message that renders
# it dropped one.
#
# Reported to Dr Ali Charanek by email on 2026-09-10; answered 2026-09-11:
#
#     "Use the hardest safety rule that include consulting health provider
#      in the mes[sage]"
#
# WHAT THIS DOES AND DOES NOT DO. It APPENDS one sentence and changes not a
# word of the existing clinical wording. The sentence is not newly written
# either -- it is MSG-CRITICAL-AVOID's own closing sentence, so the referral
# arrives in language this library already uses, and it still gives no
# dosing guidance, which is the constraint the whole VETO library respects.
DECIDED_BY = "Dr Ali Charanek"
DECIDED_ON = "2026-09-11"
DECISION_QUOTE = ("Use the hardest safety rule that include consulting "
                  "health provider in the message")

AUTHORISED_OVERRIDES: dict[str, dict[str, str]] = {
    "MSG-CRITICAL-STABLE": {
        "field": "body_template",
        "append": " Your prescriber can advise on what's right for you.",
        "because": (
            "Both rules that render it (VETO-DN-0265 insulin x carbohydrate, "
            "VETO-DN-0267 sulfonylureas x carbohydrate) carry the action "
            "'STABLE PATTERN — discuss with prescriber' and are hypoglycaemia "
            "risks; the template named no professional at all."
        ),
        # Borrowed from MSG-CRITICAL-AVOID's own closing sentence rather than
        # composed here. The only edit is the capital Y: there it follows an
        # em dash, here it begins a sentence.
        "wording_from": "MSG-CRITICAL-AVOID",
    },
}

# Still silent, and deliberately NOT overridden: MSG-MODERATE-STABLE names no
# professional either, but its single rule -- VETO-DN-0107, diuretic + ACE
# inhibitor x potassium -- has the action "BALANCE" and demands no referral.
# The decision above applies where a rule mandates one, and this is the case
# where none does, so it stays as written and stays reported. See
# docs/parameter-gaps.md.
STILL_WITHOUT_REFERRAL = {"MSG-MODERATE-STABLE"}


def apply_authorised_overrides(rows: list[dict]) -> list[dict]:
    """Apply the declared changes, marking every row they touch.

    A row this touches carries `overridden_field`, `overridden_by`,
    `overridden_on` and `override_reason`, and keeps the workbook's own text
    in `source_body_template`. Nothing downstream has to take the changed
    row on trust: it says so itself, and the original is beside it.
    """
    by_id = {row["message_id"]: row for row in rows}
    for message_id, override in AUTHORISED_OVERRIDES.items():
        if message_id not in by_id:
            raise SystemExit(
                f"an override is declared for {message_id} and the sheet no "
                "longer has that template. Re-read the decision before "
                "dropping it.")
        row = by_id[message_id]
        field = override["field"]
        original = row[field]
        if override["append"] in original:
            raise SystemExit(
                f"{message_id} already contains the sentence the override "
                "appends. The sheet has been corrected at source, so this "
                "override is now a no-op and should be retired rather than "
                "applied twice.")
        row[f"source_{field}"] = original
        row[field] = original + override["append"]
        row["overridden_field"] = field
        row["overridden_by"] = DECIDED_BY
        row["overridden_on"] = DECIDED_ON
        row["override_reason"] = override["because"]

    for row in rows:
        row.setdefault("source_body_template", None)
        row.setdefault("overridden_field", None)
        row.setdefault("overridden_by", None)
        row.setdefault("overridden_on", None)
        row.setdefault("override_reason", None)
    return rows


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

    # THE POST-OVERRIDE STATE, which is the one that ships. Every CRITICAL
    # template must send the person to a qualified human: that is the
    # library's whole posture -- flag and defer, never advise -- and it is
    # what Dr Ali's decision asks for. Six templates arrive that way from the
    # sheet and the seventh is the override above.
    silent = set()
    for r in rows:
        text = f"{r['body_template']} {r['cta'] or ''}".lower()
        if not any(who in text for who in REFERS_TO):
            silent.add(r["message_id"])

    silent_critical = {
        r["message_id"] for r in rows
        if r["severity"] == "CRITICAL" and r["message_id"] in silent}
    if silent_critical:
        raise SystemExit(
            f"CRITICAL templates naming no professional: {sorted(silent_critical)}. "
            "A CRITICAL rule's action says 'discuss with prescriber'; a "
            "message rendering it that names nobody drops the referral the "
            "rule mandates. If the sheet has a new one, it needs a decision "
            "from the clinical owner, not an override written here.")

    if silent != STILL_WITHOUT_REFERRAL:
        raise SystemExit(
            f"templates naming no professional are {sorted(silent)}, not "
            f"{sorted(STILL_WITHOUT_REFERRAL)}. The set is pinned because "
            "each member is a reported finding; a change means the sheet "
            "moved and the report is stale.")

    # And the overrides are only safe while they are visible. A row this
    # build changed must say so, say who decided it, and keep the workbook's
    # own text beside the changed one.
    by_id = {r["message_id"]: r for r in rows}
    for message_id, override in AUTHORISED_OVERRIDES.items():
        row = by_id[message_id]
        field = override["field"]
        if not row[field].endswith(override["append"]):
            raise SystemExit(
                f"{message_id} did not receive its authorised override. "
                "check() runs on the rows that get written, so this means "
                "apply_authorised_overrides was not called.")
        if row.get("overridden_field") != field:
            raise SystemExit(f"{message_id} was changed without being marked as overridden")
        if row.get("overridden_by") != DECIDED_BY or row.get("overridden_on") != DECIDED_ON:
            raise SystemExit(f"{message_id} carries no attribution for its override")
        if row.get(f"source_{field}") != row[field][:-len(override["append"])]:
            raise SystemExit(
                f"{message_id} does not carry the workbook's own {field} in "
                f"source_{field}, so the change cannot be undone or audited")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m sahacore.data.build_veto_messages <workbook.xlsx>")

    rows = extract(sys.argv[1])
    # In this order on purpose: check() runs on the rows that are written,
    # not on an earlier version of them, so what it verifies is what ships.
    rows = apply_authorised_overrides(rows)
    check(rows)
    OUT.write_text(json.dumps(rows, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    sev: dict[str, int] = {}
    for r in rows:
        sev[r["severity"]] = sev.get(r["severity"], 0) + 1
    print(f"wrote {len(rows)} message templates to {OUT.name}")
    print("   by severity:", dict(sorted(sev.items())))
    print("   actions:", sorted({r["action"] for r in rows}))
    for message_id in AUTHORISED_OVERRIDES:
        print(f"   overridden: {message_id} -- {DECIDED_BY}, {DECIDED_ON}")
    print("   still naming no professional:", sorted(STILL_WITHOUT_REFERRAL))


if __name__ == "__main__":
    main()
