"""The drug-nutrient VETO library, and release gate VETO-01.

Source: v39sEng2.xlsx, sheet 'MERGE·VETO Drug-Nutrient 339'.

'Replay Contract' section F lists twelve RELEASE_BLOCKING tests. Eleven of
them need layers this build has not written yet. This is the twelfth, and the
only one that was ever blocked on nothing but loading a table:

    VETO-01 | Load VETO table | 339 rows and 339 unique canonical IDs;
             source IDs retained | Primary-key collision | RELEASE_BLOCKING

This file is that gate. It also pins the two invariants the schema enforces,
because this is the table that decides whether a recommendation reaches
someone taking warfarin, and a constraint nobody tests is a comment.
"""
import json
from pathlib import Path

import pytest

DATA_DIR = Path(__file__).parent.parent / "sahacore" / "data"


@pytest.fixture(scope="module")
def veto() -> list[dict]:
    return json.loads((DATA_DIR / "veto_drug_nutrient_339.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def nutrients() -> list[dict]:
    return json.loads((DATA_DIR / "nutrients_81.json").read_text(encoding="utf-8"))


# --- VETO-01, the release gate ---------------------------------------------

def test_veto_01_339_rows_and_339_unique_canonical_ids(veto):
    """The gate's pass condition, in its own words: "339 rows and 339 unique
    canonical IDs; source IDs retained". Its failure meaning is "Primary-key
    collision", which is exactly what the workbook had before the repair."""
    assert len(veto) == 339
    assert len({r["rule_id"] for r in veto}) == 339
    assert sorted(r["rule_id"] for r in veto) == [f"VETO-DN-{n:04d}" for n in range(1, 340)]


def test_veto_01_the_duplicate_source_ids_are_retained_not_deduplicated(veto):
    """The other half of the same pass condition, and the reason the canonical
    key exists. 'Replay Contract' section E: "339 rows contained only 319
    unique rule IDs." Both numbers must still be readable off the table --
    deduplicating to 319 rows would lose 20 real rules, and dropping the
    source column would erase the evidence that the repair happened."""
    sources = [r["source_rule_id"] for r in veto]
    assert len(sources) == 339
    assert len(set(sources)) == 319


def test_the_reference_only_sheet_is_not_the_one_loaded():
    """'VETO Canonical 339' matches the name in the build guide and is the
    wrong sheet. Its own third row: "REFERENCE ONLY -- ... Production/build
    loaders MUST use MERGE·VETO Drug-Nutrient 339". It holds 266 rows, so
    loading it would silently ship a truncated safety table."""
    from sahacore.data.build_veto_registry import SHEET, REFERENCE_ONLY_SHEET

    assert SHEET == "MERGE·VETO Drug-Nutrient 339"
    assert REFERENCE_ONLY_SHEET == "VETO Canonical 339"
    assert SHEET != REFERENCE_ONLY_SHEET


# --- the safety invariants -------------------------------------------------

def test_severity_determines_the_bandit_action_with_no_exceptions(veto):
    """The invariant that matters most. A CRITICAL rule removes the arm; it is
    never downgraded to a note. Checked over all 339 rows rather than by
    trusting the mapping table, so an edit to one column without the other
    fails here as well as in the database."""
    from sahacore.data.build_veto_registry import SEVERITY_TO_BANDIT_ACTION

    for r in veto:
        assert r["bandit_action"] == SEVERITY_TO_BANDIT_ACTION[r["severity"]], (
            f"{r['rule_id']}: {r['severity']} carries {r['bandit_action']!r}")
    assert SEVERITY_TO_BANDIT_ACTION["CRITICAL"] == "HARD_VETO (remove arm)"


def test_the_severity_distribution_matches_the_sheets_own_header(veto):
    """The sheet states its own arithmetic: "94 CRITICAL, 111 HIGH, 110
    MODERATE, 23 LOW and 1 CONTROVERSIAL rule = 339 total". Checking the
    extraction against the source's claim rather than against itself is what
    makes the count evidence instead of a tautology."""
    from sahacore.data.build_veto_registry import DECLARED_SEVERITY_COUNTS

    counts: dict[str, int] = {}
    for r in veto:
        counts[r["severity"]] = counts.get(r["severity"], 0) + 1
    assert counts == DECLARED_SEVERITY_COUNTS
    assert sum(DECLARED_SEVERITY_COUNTS.values()) == 339


def test_a_nutrient_key_appears_exactly_when_the_rule_is_about_an_engine_state(veto):
    """250 rules act on a modelled nutrient state and carry its id. The other
    89 name a supplement the model does not carry, a whole food, another drug,
    or a nutrient class -- an id filled in for those would be a foreign key to
    a nutrient the rule is not about."""
    with_id = [r for r in veto if r["engine_nutrient_id"]]
    assert len(with_id) == 250
    for r in veto:
        assert bool(r["engine_nutrient_id"]) == (r["link_type"] == "engine_state"), (
            f"{r['rule_id']}: link_type {r['link_type']!r} with "
            f"engine_nutrient_id {r['engine_nutrient_id']!r}")


def test_every_nutrient_key_resolves_into_the_81_nutrient_registry(veto, nutrients):
    """The foreign key is real, so the schema declares it as one. All 31
    distinct ids resolve; none is a spelling the registry does not have."""
    known = {n["id"] for n in nutrients}
    used = {r["engine_nutrient_id"] for r in veto if r["engine_nutrient_id"]}
    assert used <= known
    assert len(used) == 31


def test_the_hard_vetoes_are_the_94_critical_rules(veto):
    """What engine_internal.veto_hard selects, asserted on the data behind it.
    Layer H's H2 rule -- "Action a is selected only if a in A_safe" -- reads
    this set."""
    hard = [r for r in veto if r["bandit_action"] == "HARD_VETO (remove arm)"]
    assert len(hard) == 94
    assert {r["severity"] for r in hard} == {"CRITICAL"}


def test_the_warfarin_vitamin_k_rule_is_intact(veto):
    """One rule read end to end, so the transcription is checkable by eye
    rather than only by count. VETO-DN-0001 is the canonical example the
    sheet leads with."""
    r = next(x for x in veto if x["rule_id"] == "VETO-DN-0001")
    assert r["drug_or_class"] == "Warfarin"
    assert r["nutrient_or_food"] == "Vitamin K"
    assert r["severity"] == "CRITICAL"
    assert r["bandit_action"] == "HARD_VETO (remove arm)"
    assert r["link_type"] == "engine_state"
    assert r["engine_nutrient_id"] == "vit_k_ug"
    assert "INR" in r["clinical_rationale"]


# --- the extractor refuses bad data ----------------------------------------

def test_the_builders_own_checks_reject_a_downgraded_critical_rule(veto):
    """The guard, proven rather than assumed: a CRITICAL rule edited to merely
    warn must not survive extraction. Same defect the database CHECK catches,
    caught one step earlier."""
    from sahacore.data.build_veto_registry import check

    rows = [dict(r) for r in veto]
    victim = next(r for r in rows if r["severity"] == "CRITICAL")
    victim["bandit_action"] = "WARNING (show note)"
    with pytest.raises(SystemExit, match="bandit_action"):
        check(rows)


def test_the_builders_own_checks_reject_a_dropped_rule(veto):
    """Losing a safety rule must be loud."""
    from sahacore.data.build_veto_registry import check

    with pytest.raises(SystemExit, match="339"):
        check([dict(r) for r in veto][:-1])
