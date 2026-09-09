"""Extracts '★ Scarring Bistability Guard' into bistability_guard.json.

Source: v39sEng2.xlsx, sheet '★ Scarring Bistability Guard'.
'01_IMPORT_MANIFEST' order 17, role MEMORY_WARNING, import YES, backend Yes.

    python -m sahacore.data.build_bistability_guard <path-to-workbook>

WHAT THE SHEET GUARDS, in its own words:

    "The scarring loop is positive feedback: damage raises scarring and
     scarring suppresses repair."

and why a single number will not do:

    "READ THE LAST COLUMN, NOT A SINGLE NUMBER.  A blanket cap of gamma*r <=
     0.75 would be 5x too tight for C6 and still too loose for C7."

THE CONDITION, transcribed verbatim from section 1:

    S*(Z) = r*over/(1 + r*over),   r = alpha_scar/beta_autophagy,
                                   over = max(0, (Z-theta)/theta)
    F(Z)  = k*Z + V_max*exp(-gamma*S*(Z))*Z/(K_m + Z)      total removal

    F'(Z) = k + V_max*e^(-gamma*S*)*[ K_m/(K_m+Z)^2
                                      - gamma*r/(1+r*over)^2 * Z/(K_m+Z)/theta ]

    "The destabilising term scales with the group gamma*r. When it wins, F
     folds back and the damage level admits three equilibria: stable --
     unstable -- stable."

WHY THIS IS FOUNDATION WORK RATHER THAN LAYER-M WORK. Parameter #190
(kappa_bist) in 'P1 Parameters 134+' says the bound is to be asserted "at
build time -- see ★ Scarring Bistability Guard". A build-time assert needs
the caps to exist as data before any equation module is written, which is
why the table is imported in Phase 1 alongside the other registries rather
than when Layer M is built.

TWO INDEPENDENT COPIES OF THE SAME TWELVE CAPS. Section 3 states them, and
section 8 -- "INDEPENDENT VERIFICATION RECEIPT" -- restates gamma_scar, the
cap and max alpha/beta after an external audit reproduced them. Both are
extracted and `check()` requires them to agree, because a sheet that carries
its own second opinion should not be reduced to one copy on import: if they
ever diverge, that is the finding.

NOTHING HERE IS RE-DERIVED. Two relationships the sheet states are checked
arithmetically -- cap = gamma_scar * max(alpha/beta), and V = 1.443 *
tau_dam/tau_heal -- because both are stated as identities and either failing
would mean a transcription error. The caps themselves are NOT re-derived
from the tangency condition F'min = 0; the sheet records that an external
audit did that, and reproducing it here would be inventing a derivation the
workbook did not ask for.

THE FOUR PROBABILISTIC GUARDS (section 6) are extracted as specifications,
not implemented. Only PG-1 is placed on "this sheet"; PG-2 lives in
'★ Validation Test Battery' test C17 and PG-3 in 'M-W LayerW Equations',
neither of which is imported yet. They are recorded so that the placement
is visible when those sheets arrive.
"""
import json
import sys
from pathlib import Path

import openpyxl

SHEET = "★ Scarring Bistability Guard"
FIRST_COL = 2
OUT = Path(__file__).parent / "bistability_guard.json"

# Section 3 -- 'PER-CLUSTER BOUNDS (assert these at build time)'.
CAPS_HEADER_ROW = 23
CAPS_ROWS = range(24, 36)
CAPS_LABELS = ["Cluster", "τ_dam (d)", "τ_heal (d)", "V", "bound on γ·r",
               "γ_scar", "MAX α_scar/β_autophagy"]

# Section 8 -- 'INDEPENDENT VERIFICATION RECEIPT'.
RECEIPT_HEADER_ROW = 72
RECEIPT_ROWS = range(73, 85)
RECEIPT_LABELS = ["Cluster", "γ_scar", "cap on γ·r", "max α/β",
                  "F′min at cap", "Agrees"]

# Section 6 -- the probabilistic guards.
GUARD_HEADER_ROW = 54
GUARD_ROWS = range(55, 59)
GUARD_LABELS = ["ID", "Name", "Specification", "Placement"]

# Section 5 -- the founder decision, recorded.
DECISION_HEADER_ROW = 47
DECISION_ROWS = range(48, 50)

# Section 4 -- what the unconstrained ranges permitted.
PERMITTED_HEADER_ROW = 40
PERMITTED_ROWS = range(41, 45)

# V_k = 1.443 * tau_dam,k / tau_heal,k, from section 2 'Which gives'. The
# constant is 1/ln(2) to four figures; the sheet writes 1.443, so 1.443 is
# what is checked against -- not log(2), which would silently hold the sheet
# to a precision it did not claim.
V_CONSTANT = 1.443

# Every numeric cell in the two tables is rounded to two decimals in the
# source, and each column is rounded from its own unrounded value rather than
# recomputed from the displayed neighbours. So the identities below hold to
# the source's precision, not exactly: C3 shows cap 1.92 while 0.6 * 3.19 =
# 1.914, because the true max ratio is nearer 3.194. One unit in the last
# displayed place is the tightest tolerance the sheet's own precision
# supports; the largest deviation across all twelve clusters is 0.0068, so a
# real transcription slip of 0.01 or more would still fail this.
ROUNDING = 2
IDENTITY_TOLERANCE = 0.01

EXPECTED_CLUSTERS = 12


def _cell(ws, row: int, offset: int):
    return ws.cell(row=row, column=FIRST_COL + offset).value


def _text(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _check_header(ws, row: int, labels: list[str]) -> None:
    """A column shift is the failure mode this file exists to make loud."""
    for offset, expected in enumerate(labels):
        found = _text(_cell(ws, row, offset))
        if found != expected:
            raise SystemExit(
                f"{SHEET}: header row {row} column {FIRST_COL + offset} reads "
                f"{found!r}, expected {expected!r}. The sheet moved; fix the "
                "offsets rather than the expectation."
            )


def extract(path: str) -> dict:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb[SHEET]

    _check_header(ws, CAPS_HEADER_ROW, CAPS_LABELS)
    _check_header(ws, RECEIPT_HEADER_ROW, RECEIPT_LABELS)
    _check_header(ws, GUARD_HEADER_ROW, GUARD_LABELS)

    caps = []
    for row in CAPS_ROWS:
        name = _text(_cell(ws, row, 0))
        if name is None:
            raise SystemExit(f"{SHEET}: row {row} has no cluster name.")
        # 'C5 Inflammatory Response' -> 'C5' + 'Inflammatory Response'.
        cluster_id, _, cluster_name = name.partition(" ")
        caps.append({
            "cluster_id": cluster_id,
            "cluster_name": cluster_name.strip(),
            "source_row": row,
            "tau_dam_days": _cell(ws, row, 1),
            "tau_heal_days": _cell(ws, row, 2),
            "v_repair": _cell(ws, row, 3),
            "cap_gamma_r": _cell(ws, row, 4),
            "gamma_scar": _cell(ws, row, 5),
            "max_alpha_beta_ratio": _cell(ws, row, 6),
        })

    receipt = []
    for row in RECEIPT_ROWS:
        receipt.append({
            "cluster_id": _text(_cell(ws, row, 0)),
            "source_row": row,
            "gamma_scar": _cell(ws, row, 1),
            "cap_gamma_r": _cell(ws, row, 2),
            "max_alpha_beta_ratio": _cell(ws, row, 3),
            "f_prime_min_at_cap": _text(_cell(ws, row, 4)),
            "agrees": _text(_cell(ws, row, 5)),
        })

    guards = [{
        "guard_id": _text(_cell(ws, row, 0)),
        "source_row": row,
        "name": _text(_cell(ws, row, 1)),
        "specification": _text(_cell(ws, row, 2)),
        "placement": _text(_cell(ws, row, 3)),
    } for row in GUARD_ROWS]

    decisions = [{
        "option": _text(_cell(ws, row, 0)),
        "source_row": row,
        "meaning": _text(_cell(ws, row, 1)),
        "status": _text(_cell(ws, row, 2)),
    } for row in DECISION_ROWS]

    permitted = [{
        "quantity": _text(_cell(ws, row, 0)),
        "source_row": row,
        "value": _text(_cell(ws, row, 1)),
        "consequence": _text(_cell(ws, row, 2)),
    } for row in PERMITTED_ROWS]

    wb.close()
    return {
        "caps": caps,
        "receipt": receipt,
        "probabilistic_guards": guards,
        "founder_decision": decisions,
        "unconstrained_ranges": permitted,
    }


def check(data: dict) -> None:
    caps, receipt = data["caps"], data["receipt"]

    if len(caps) != EXPECTED_CLUSTERS or len(receipt) != EXPECTED_CLUSTERS:
        raise SystemExit(
            f"{SHEET}: expected {EXPECTED_CLUSTERS} clusters in both tables, "
            f"got {len(caps)} caps and {len(receipt)} receipt rows.")

    by_id = {row["cluster_id"]: row for row in receipt}
    for cap in caps:
        got = by_id.get(cap["cluster_id"])
        if got is None:
            raise SystemExit(
                f"{SHEET}: {cap['cluster_id']} is in the caps table but not in "
                "the verification receipt.")

        # Section 3 and section 8 are two independent statements of the same
        # three numbers. They must agree exactly -- they are both rounded to
        # the same two decimals in the source.
        for field in ("gamma_scar", "cap_gamma_r", "max_alpha_beta_ratio"):
            if cap[field] != got[field]:
                raise SystemExit(
                    f"{SHEET}: {cap['cluster_id']} {field} is {cap[field]!r} in "
                    f"section 3 but {got[field]!r} in the section 8 receipt. "
                    "The sheet disagrees with itself; do not pick one.")

        if got["agrees"] != "YES":
            raise SystemExit(
                f"{SHEET}: the verification receipt does not confirm "
                f"{cap['cluster_id']} (Agrees = {got['agrees']!r}).")

        # 'MAX alpha_scar/beta_autophagy' is the cap divided through by
        # gamma_scar -- the sheet states both, so the identity is checkable.
        product = cap["gamma_scar"] * cap["max_alpha_beta_ratio"]
        if abs(product - cap["cap_gamma_r"]) > IDENTITY_TOLERANCE:
            raise SystemExit(
                f"{SHEET}: {cap['cluster_id']} has cap {cap['cap_gamma_r']} but "
                f"gamma_scar * max(alpha/beta) = {product:.4f}.")

        # Section 2: 'V_k = V_max/(k*theta) = 1.443 * tau_dam,k / tau_heal,k'.
        v = V_CONSTANT * cap["tau_dam_days"] / cap["tau_heal_days"]
        if abs(v - cap["v_repair"]) > IDENTITY_TOLERANCE:
            raise SystemExit(
                f"{SHEET}: {cap['cluster_id']} states V = {cap['v_repair']} but "
                f"{V_CONSTANT} * tau_dam/tau_heal = {v:.4f}.")

    guards = data["probabilistic_guards"]
    ids = [g["guard_id"] for g in guards]
    if ids != ["PG-1", "PG-2", "PG-3", "PG-4"]:
        raise SystemExit(f"{SHEET}: expected PG-1..PG-4, got {ids}.")
    for guard in guards:
        if not guard["specification"] or not guard["placement"]:
            raise SystemExit(
                f"{SHEET}: {guard['guard_id']} is missing a specification or a "
                "placement.")

    # Section 5 records a founder decision that is already made. If the
    # adopted option ever changes, the caps stop being build-time asserts and
    # become one end of a declared band -- a different engine.
    adopted = [d for d in data["founder_decision"] if d["status"] == "ADOPTED"]
    if len(adopted) != 1 or not adopted[0]["option"].startswith("NO"):
        raise SystemExit(
            f"{SHEET}: expected exactly one ADOPTED option, 'NO -- enforce "
            f"monotonicity'. Got {[(d['option'], d['status']) for d in adopted]}.")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m sahacore.data.build_bistability_guard "
                         "<path-to-workbook>")
    data = extract(sys.argv[1])
    check(data)
    OUT.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8")

    tightest = min(data["caps"], key=lambda c: c["cap_gamma_r"])
    loosest = max(data["caps"], key=lambda c: c["cap_gamma_r"])
    print(f"wrote {OUT.name}")
    print(f"  {len(data['caps'])} per-cluster caps, each confirmed by the "
          "section 8 receipt")
    print(f"  tightest cap  gamma*r <= {tightest['cap_gamma_r']}  "
          f"({tightest['cluster_id']} {tightest['cluster_name']})")
    print(f"  loosest cap   gamma*r <= {loosest['cap_gamma_r']}  "
          f"({loosest['cluster_id']} {loosest['cluster_name']})")
    print(f"  {len(data['probabilistic_guards'])} probabilistic guards "
          "(PG-1..PG-4), specifications only")


if __name__ == "__main__":
    main()
