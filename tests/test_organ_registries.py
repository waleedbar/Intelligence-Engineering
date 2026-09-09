"""Organ systems, organ-pathway weights, and daily targets.

Sources: '★ SYS Registry (organs)', 'REG · Organ×Pathway Long',
'★ Target Registry (versioned)' -- manifest orders 172, 112 and 114.

Three namespaces meet in these sheets and two of them disagree. The tests
below pin the disagreement rather than resolving it, and pin the one place
where a gate and its data corroborate each other.
"""
import json
from pathlib import Path

import pytest

DATA_DIR = Path(__file__).parent.parent / "sahacore" / "data"


@pytest.fixture(scope="module")
def data() -> dict:
    return json.loads((DATA_DIR / "organ_registries.json").read_text(encoding="utf-8"))


# --- the SYS namespace -----------------------------------------------------

def test_twelve_organ_systems(data):
    assert [r["sys_code"] for r in data["sys_registry"]] == [f"SYS{n}" for n in range(1, 13)]


def test_sys_numbers_do_not_mirror_cluster_numbers(data):
    """The mistake the table invites. SYS1 Cardiovascular holds C1 Membrane
    Integrity; SYS7 Neurological holds C7 Methylation. Same number, different
    thing -- so a SYS code must never be read as a cluster code."""
    by_code = {r["sys_code"]: r for r in data["sys_registry"]}
    assert by_code["SYS1"]["organ_system"] == "Cardiovascular"
    assert by_code["SYS1"]["process_cluster"].startswith("C1 Membrane")
    assert by_code["SYS7"]["organ_system"] == "Neurological"
    assert by_code["SYS7"]["process_cluster"].startswith("C7 Methylation")


def test_sys11_is_respiratory_and_the_sheet_says_why(data):
    """The sheet's own resolved collision: "naming SYS11 Neurological would
    duplicate SYS7 and drop Respiratory entirely"."""
    sys11 = next(r for r in data["sys_registry"] if r["sys_code"] == "SYS11")
    assert sys11["organ_system"] == "Respiratory"
    assert "duplicate SYS7" in sys11["note"]


# --- the namespace disagreement --------------------------------------------

def test_the_organ_pathway_sheet_uses_the_namespace_sys_registry_forbids(data):
    """'★ SYS Registry' is marked AUTHORITATIVE and says "Why NOT O1-O12: the
    O-namespace is occupied by onboarding", with the binding rule "Any NEW
    organ reference must use a SYS code". 'REG · Organ×Pathway Long' uses
    O1-O12.

    It predates the ruling -- NEW references -- so this is not a violation to
    fix here. But the collision is live: O1 is the cardiovascular organ node
    in one sheet and the anthropometrics module in 'O·O1 Anthropometrics'.
    Pinned so the state of the disagreement is explicit either way."""
    organs = {r["organ_id"] for r in data["organ_pathway"]}
    assert organs == {f"O{n}" for n in range(1, 13)}
    assert not any(o.startswith("SYS") for o in organs)


# --- the gate and the data agree -------------------------------------------

def test_no_organ_weights_exist_for_d14_or_d15(data):
    """48 links over 12 organs and 13 pathways -- D1 to D13. The
    '00_ENGINEER_START' gate d14_d15_fail_closed reads
    GLOBAL_MODIFIER_PENDING, "No invented organ weights. Fail closed until
    evidence-locked mapping is signed off."

    The gate was loaded from one sheet and this table from another. They
    agree, which is the kind of corroboration that makes a fail-closed
    position credible rather than aspirational."""
    pathways = {r["pathway_id"] for r in data["organ_pathway"]}
    assert pathways == {f"D{n}" for n in range(1, 14)}
    assert not pathways & {"D14", "D15"}
    assert len(data["organ_pathway"]) == 48


def test_the_gate_this_corroborates_is_still_recorded():
    """If the gate were ever removed, this test's premise would be gone and
    the D14/D15 absence would look like missing data instead of a decision."""
    invariants = json.loads(
        (DATA_DIR / "runtime_invariants.json").read_text(encoding="utf-8"))
    gate = next(i for i in invariants if i["gate"] == "d14_d15_fail_closed")
    assert gate["value"] == "GLOBAL_MODIFIER_PENDING"
    assert "No invented organ weights" in gate["engineering_meaning"]


def test_the_builder_refuses_organ_weights_appearing_for_d14(data):
    from sahacore.data.build_organ_registries import check

    broken = json.loads(json.dumps(data))
    broken["organ_pathway"][0]["pathway_id"] = "D14"
    with pytest.raises(SystemExit, match="d14_d15_fail_closed"):
        check(broken)


# --- the target registry ---------------------------------------------------

def test_the_targets_that_have_no_official_basis_are_named(data):
    """CoQ10 and betaine have no IOM DRI or UL. The sheet's note is explicit
    about the consequence: "literature-based wellness proxies for adequacy
    display only, NOT clinical dosing... they must render as adequacy %,
    never as a treatment dose"."""
    proxies = {t["variable_key"] for t in data["targets"]
               if t["basis_source"].startswith("NO official")}
    assert proxies == {"coq10_mg", "betaine_mg"}


def test_every_target_states_an_upper_limit_even_when_there_is_none(data):
    """"none established" and "none formal; caution >4000 (LDL↑)" are
    answers. A null would read as "no limit", which is a different claim."""
    for t in data["targets"]:
        assert t["upper_limit"], t["variable_key"]


def test_the_target_keys_that_differ_from_the_nutrient_registry_are_declared(data):
    """Three keys name nutrients the registry spells differently --
    folate_ug/b9_ug, vitamin_b12_ug/b12_ug, vitamin_b6_mg/b6_mg. Declared
    with a reason and their targets checked to exist, rather than matched on
    resemblance."""
    from sahacore.data.build_organ_registries import (
        TARGET_KEY_ALIASES, SUPPLEMENT_ONLY_TARGETS)

    nutrients = {n["id"] for n in json.loads(
        (DATA_DIR / "nutrients_81.json").read_text(encoding="utf-8"))}
    for key, (target, reason) in TARGET_KEY_ALIASES.items():
        assert target in nutrients, f"{key} -> {target} is not a nutrient"
        assert len(reason) > 20

    for t in data["targets"]:
        key = t["variable_key"]
        assert (key in nutrients or key in TARGET_KEY_ALIASES
                or key in SUPPLEMENT_ONLY_TARGETS), key


def test_the_supplement_only_targets_agree_with_the_supplement_registry(data):
    """coq10_mg and betaine_mg have no nutrient counterpart here, and
    '★ Supplement Registry' -- a different sheet -- lists CoQ10 as "NO —
    supplement only" and carries Betaine too. Two sheets agreeing."""
    from sahacore.data.build_organ_registries import SUPPLEMENT_ONLY_TARGETS

    supplements = json.loads(
        (DATA_DIR / "supplement_registry.json").read_text(encoding="utf-8"))
    names = " ".join(s["supplement"] for s in supplements).lower()
    assert "coq10" in names
    assert "betaine" in names
    assert SUPPLEMENT_ONLY_TARGETS == {"coq10_mg", "betaine_mg"}
