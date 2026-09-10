"""Extracts 'O·O10 Goal Priority Wts' into onboarding_o10.json.

Source: v39sEng2.xlsx, sheet 'O·O10 Goal Priority Wts'.
'01_IMPORT_MANIFEST' order 80, role ONBOARDING, import YES, backend Yes.

    python -m sahacore.data.build_onboarding_o10 <path-to-workbook>

The authority for ONB-010. Onboarding steps 4 and 11, feeding Layers D and F.
Two tables: eight goal areas with their nutrient targets, and the four-rung
weight ladder that turns a user's ranking into pi_k.

THE SECOND SHEET IN THE BUILD THAT CITES ITS SOURCES. Every goal area names
where its nutrient targets come from -- AHA and REDUCE-IT for heart health,
ADA 2024 for metabolism, NOF/IOF for bone, EFSA for immunity, ASRM for
fertility. Only 'O·O6 Family History' does the same. Worth saying, because
most of docs/parameter-gaps.md is about numbers with no provenance.

AND IT AGREES WITH ITSELF. Every goal row says "2.5 (if Primary)" and the
rules table independently gives Primary = 2.5. The ladder is monotone --
2.5 Primary, 2.0 Secondary, 1.5 Tertiary, 1.0 unselected -- so ranking a goal
higher can never weight it lower.

THE FINDING: THE PRIMARY GOAL COMES FROM A QUESTION WHOSE ANSWERS THIS SHEET
CANNOT USE.

The weight rules say the Primary goal -- the one weighted 2.5, the heaviest
rung on the ladder -- is the "Highest priority goal from Step 4/11".

    Step 11 goal_areas[]  Heart Health, Metabolism & Diabetes, Longevity &
                          Anti-Aging, Bone Health, Immunity & Inflammation
                          Control, Gut Health, Fertility & Hormone Health,
                          Stress & Mental Health

    Step 4  primary_goal  Weight Loss, Muscle Gain, Energy Levels, Digestive
                          Health, Chronic Condition, Manage Benefits,
                          Healthy Aging

Step 11's eight line up with this sheet's eight rows -- six exactly, and two
where the sheet truncates the UI's label ("Immunity & Inflammation Control"
-> "Immunity & Inflammation"). That is the cleanest alignment any O-sheet has
had with the interface.

Step 4's seven line up with NOTHING. Not one of them is a goal area here.
"Weight Loss" has no pi_k, no nutrient targets and no Z-pathways.

So either Step 4 does not in fact supply the Primary goal and the rule should
say Step 11 alone, or Step 4's answers need a mapping into these eight that
no sheet provides. Recorded, not resolved.

WHAT THE WEIGHTS FEED IS AN OPEN FOUNDER DECISION. The rules table names its
engine equation: "H1: r_t^pi = SUM(pi_k * r_k)". Layer H is the conservative
bandit, and '★ Scoped Builds — LTMLE Bandit' lists the bandit's reward proxy
as OPEN FOUNDER DECISION 5, with its own note calling it "the single biggest
decision". So this sheet specifies the WEIGHTS of a reward whose TERMS are
undecided -- pi_k is settled and r_k is not.
"""
import json
import re
import sys
from pathlib import Path

import openpyxl

from sahacore.data.sheet_header import check_header

SHEET = "O·O10 Goal Priority Wts"
FIRST_COL = 3
DATA_DIR = Path(__file__).parent
OUT = DATA_DIR / "onboarding_o10.json"

GOAL_HEADER_ROW = 9
GOAL_ROWS = range(10, 18)
GOAL_LABELS = ["Goal Area", "pi_k Weight", "Priority Level",
               "Key Nutrient Targets", "Z-Pathways Boosted", "Source"]

RULE_HEADER_ROW = 22
RULE_ROWS = range(23, 27)
RULE_LABELS = ["Priority Level", "pi_k Value", "Assignment Rule",
               "Engine Equation"]

EXPECTED_GOALS = 8
EXPECTED_RULES = 4

_WEIGHT = re.compile(r"^(\d+(?:\.\d+)?)")
_PATHWAY = re.compile(r"\bZ\d+\b")


def _text(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _cell(ws, row: int, offset: int):
    return ws.cell(row=row, column=FIRST_COL + offset).value


def _ui_options(variable: str) -> list[str]:
    data = json.loads((DATA_DIR / "step_questions.json").read_text(encoding="utf-8"))
    matching = [q for q in data["questions"] if q["variable"] == variable]
    if len(matching) != 1:
        raise SystemExit(
            f"{SHEET}: the UI contract has {len(matching)} {variable!r} "
            "questions, expected exactly one.")
    return matching[0]["answer_options"]


def extract(path: str) -> dict:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb[SHEET]
    check_header(ws, SHEET, GOAL_HEADER_ROW, FIRST_COL, GOAL_LABELS)
    check_header(ws, SHEET, RULE_HEADER_ROW, FIRST_COL, RULE_LABELS)

    goal_areas = _ui_options("goal_areas[]")

    goals = []
    for row in GOAL_ROWS:
        goal = _text(_cell(ws, row, 0))
        if goal is None:
            raise SystemExit(f"{SHEET}: goal row {row} has no name.")
        weight_text = _text(_cell(ws, row, 1)) or ""
        matched = _WEIGHT.match(weight_text)
        pathways_text = _text(_cell(ws, row, 4)) or ""

        # How this row's name stands against what Step 11 offers. Exact, or a
        # PREFIX of a UI label -- the sheet truncates two of them -- or
        # nothing. A prefix is recorded as such rather than treated as a
        # match, because "plainly means" is the inference this build refuses.
        if goal in goal_areas:
            ui_status = "MATCHES_STEP_11_EXACTLY"
        elif any(option.startswith(goal) for option in goal_areas):
            ui_status = "PREFIX_OF_A_STEP_11_OPTION"
        else:
            ui_status = "MATCHES_NO_STEP_11_OPTION"

        goals.append({
            "goal_area": goal,
            "source_row": row,
            "weight_text": weight_text,
            "weight": float(matched.group(1)) if matched else None,
            "priority_level": _text(_cell(ws, row, 2)),
            "key_nutrient_targets": _text(_cell(ws, row, 3)),
            "z_pathways_text": pathways_text,
            "z_pathways": _PATHWAY.findall(pathways_text),
            "source": _text(_cell(ws, row, 5)),
            "ui_status": ui_status,
        })

    rules = []
    for row in RULE_ROWS:
        level = _text(_cell(ws, row, 0))
        if level is None:
            raise SystemExit(f"{SHEET}: rule row {row} has no priority level.")
        value = _text(_cell(ws, row, 1))
        rules.append({
            "priority_level": level,
            "source_row": row,
            "weight": float(value) if value else None,
            "assignment_rule": _text(_cell(ws, row, 2)),
            "engine_equation": _text(_cell(ws, row, 3)),
        })

    wb.close()
    return {"sheet": SHEET, "goals": goals, "rules": rules,
            "step_11_options": goal_areas,
            "step_4_options": _ui_options("primary_goal")}


def check(data: dict) -> None:
    goals, rules = data["goals"], data["rules"]

    if len(goals) != EXPECTED_GOALS:
        raise SystemExit(f"{SHEET}: expected {EXPECTED_GOALS} goal areas, got "
                         f"{len(goals)}.")
    if len(rules) != EXPECTED_RULES:
        raise SystemExit(f"{SHEET}: expected {EXPECTED_RULES} weight rules, "
                         f"got {len(rules)}.")

    # EVERY GOAL CITES A SOURCE. Only O6 does this too.
    for goal in goals:
        for field in ("weight_text", "priority_level", "key_nutrient_targets",
                      "z_pathways_text", "source"):
            if not goal[field]:
                raise SystemExit(
                    f"{SHEET}: {goal['goal_area']!r} has no {field}. The "
                    "source in particular is what makes this one of only two "
                    "sheets whose numbers have provenance.")
        if not goal["z_pathways"]:
            raise SystemExit(
                f"{SHEET}: {goal['goal_area']!r} boosts no Z-pathway: "
                f"{goal['z_pathways_text']!r}")

    # THE LADDER IS MONOTONE. Ranking a goal higher must never weight it lower.
    weights = [rule["weight"] for rule in rules]
    if any(weight is None for weight in weights):
        raise SystemExit(f"{SHEET}: a weight rule has no pi_k value: {rules}")
    if weights != sorted(weights, reverse=True):
        raise SystemExit(
            f"{SHEET}: the pi_k ladder is {weights}, which is not descending. "
            "A higher-ranked goal would be weighted lower.")
    if weights[-1] != 1.0:
        raise SystemExit(
            f"{SHEET}: an unselected goal is now weighted {weights[-1]}, not "
            "1.0. The baseline being exactly 1 is what makes pi_k a "
            "multiplier rather than a rescaling of everything.")

    # AND IT AGREES WITH ITSELF: every goal row states the Primary weight and
    # the rules table gives it independently.
    primary = next((r for r in rules if r["priority_level"].startswith("Primary")),
                   None)
    if primary is None:
        raise SystemExit(f"{SHEET}: there is no Primary rule.")
    for goal in goals:
        if goal["weight"] != primary["weight"]:
            raise SystemExit(
                f"{SHEET}: {goal['goal_area']!r} states pi_k "
                f"{goal['weight']} and the rules table gives Primary "
                f"{primary['weight']}. The two tables disagree.")

    # THE FINDING. Step 11's options line up; Step 4's line up with nothing.
    step_11, step_4 = data["step_11_options"], data["step_4_options"]
    if len(step_11) != EXPECTED_GOALS:
        raise SystemExit(
            f"{SHEET}: Step 11 offers {len(step_11)} goal areas and this "
            f"sheet has {EXPECTED_GOALS} rows.")
    unmatched = [g for g in goals if g["ui_status"] == "MATCHES_NO_STEP_11_OPTION"]
    if unmatched:
        raise SystemExit(
            f"{SHEET}: {[g['goal_area'] for g in unmatched]} match no Step 11 "
            "option at all. This sheet used to line up with Step 11 "
            "completely -- re-read both.")

    named = {g["goal_area"] for g in goals}
    overlap = named & set(step_4)
    if overlap:
        raise SystemExit(
            f"{SHEET}: Step 4's primary_goal now shares {sorted(overlap)} with "
            "this sheet's goal areas. The finding that its seven answers map "
            "to none of them is resolved -- re-read docs/parameter-gaps.md.")
    if "Step 4" not in primary["assignment_rule"]:
        raise SystemExit(
            f"{SHEET}: the Primary rule no longer names Step 4: "
            f"{primary['assignment_rule']!r}. The finding was that it does, "
            "and that Step 4's answers are not goal areas.")

    # WHAT THE WEIGHTS FEED IS STILL AN OPEN FOUNDER DECISION.
    if "r_k" not in (primary["engine_equation"] or ""):
        raise SystemExit(
            f"{SHEET}: the Primary rule's engine equation is now "
            f"{primary['engine_equation']!r} and no longer names r_k, whose "
            "definition is open founder decision 5.")
    decisions = json.loads(
        (DATA_DIR / "scoped_builds.json").read_text(encoding="utf-8"))
    reward = [d for d in decisions["open_decisions"]
              if "reward" in d["decision"].lower()]
    if not reward:
        raise SystemExit(
            f"{SHEET}: the bandit's reward proxy is no longer an open founder "
            "decision, so pi_k's terms may now be defined. Re-read "
            "'★ Scoped Builds — LTMLE Bandit'.")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m sahacore.data.build_onboarding_o10 "
                         "<path-to-workbook>")
    data = extract(sys.argv[1])
    check(data)
    OUT.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")

    goals = data["goals"]
    exact = sum(1 for g in goals if g["ui_status"] == "MATCHES_STEP_11_EXACTLY")
    prefix = sum(1 for g in goals if g["ui_status"] == "PREFIX_OF_A_STEP_11_OPTION")
    print(f"wrote {OUT.name}")
    print(f"  {len(goals)} goal areas, every one citing a source")
    print(f"  {len(data['rules'])} weight rules: "
          + ", ".join(f"{r['priority_level'].split(' ')[0]} {r['weight']}"
                      for r in data["rules"]))
    print(f"  against Step 11: {exact} exact, {prefix} a truncation of the "
          "UI's label, 0 unmatched")
    print(f"  against Step 4: 0 of its {len(data['step_4_options'])} answers "
          "is a goal area here, and the Primary rule names Step 4")


if __name__ == "__main__":
    main()
