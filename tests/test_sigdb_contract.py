"""SIG-DB-v1.1 — what may leave the engine, and what this build owes it.

Source: SahaPlusAI_MASTER_..._v39sEng2SIGDB.xlsx, 27 sheets, contract
SIG-DB-v1.1 as of 2026-08-27. The five governance sheets are loaded here;
the signal catalogue and API allowlist are a second, larger import.

This file has two jobs. Most of it checks the contract was transcribed
whole. The last section is different: it checks that things this build
ALREADY DID still agree with decisions the contract marks
LOCKED_FOR_THIS_CONTRACT -- which is the only reason to keep a contract in a
database rather than a folder.
"""
import json
from pathlib import Path

import pytest

DATA_DIR = Path(__file__).parent.parent / "sahacore" / "data"


def _load(name):
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def sigdb():
    return _load("sigdb_contract.json")


@pytest.fixture(scope="module")
def decisions(sigdb):
    return {d["decision_id"]: d for d in sigdb["decisions"]}


# --- the contract itself --------------------------------------------------

def test_the_contract_states_its_own_identity(sigdb):
    contract = sigdb["contract"]
    assert contract["Contract version"] == "SIG-DB-v1.1"
    assert contract["As of"] == "2026-08-27"
    assert "default deny" in contract["API posture"].lower()
    assert contract["Server state"] == "219 hidden states"
    # The line that keeps this a wellness engine.
    assert "not clinically validated" in contract["Clinical status"].lower()


def test_every_table_arrived_whole(sigdb):
    assert len(sigdb["state_blocks"]) == 10
    assert len(sigdb["firewall_controls"]) == 17
    assert len(sigdb["gaps"]) == 68
    assert len(sigdb["qa_gates"]) == 34
    assert len(sigdb["decisions"]) == 16


# --- the 219-state partition ----------------------------------------------

def test_the_ten_blocks_tile_the_219_states_exactly_once(sigdb):
    blocks = sorted(sigdb["state_blocks"], key=lambda b: b["start_index"])
    assert blocks[0]["start_index"] == 1
    assert blocks[-1]["end_index"] == 219

    covered = []
    for block in blocks:
        covered.extend(range(block["start_index"], block["end_index"] + 1))
    assert covered == list(range(1, 220))
    assert sum(b["state_count"] for b in blocks) == 219


def test_no_state_block_is_exposed_to_the_client(sigdb):
    """FW05. The whole point of a hidden engine: the posterior, its
    covariance and the raw nutrient pools never cross the boundary."""
    assert {b["api_exposure"] for b in sigdb["state_blocks"]} == {"HIDDEN"}


def test_the_partition_agrees_with_the_state_vector_this_build_loads(sigdb):
    """Two sources, written separately, for the same 219 slots. SB01 is
    1..81 fast nutrients and our state vector's first 81 are the C_fast
    block; SB05 is 187..210 lifestyle and ours are too."""
    states = {s["idx"]: s for s in _load("state_vector_219.json")}
    assert len(states) == 219

    by_id = {b["block_id"]: b for b in sigdb["state_blocks"]}
    fast = by_id["SB01"]
    assert (fast["start_index"], fast["end_index"]) == (1, 81)
    assert all(states[i]["block"] == "C_fast" for i in range(1, 82))

    lifestyle = by_id["SB05"]
    assert (lifestyle["start_index"], lifestyle["end_index"]) == (187, 210)
    assert all(states[i]["block"] == "lifestyle" for i in range(187, 211))


# --- the firewall ---------------------------------------------------------

def test_every_firewall_control_names_the_test_that_proves_it(sigdb):
    """A control with no test is a wish. All 17 name one."""
    for control in sigdb["firewall_controls"]:
        assert control["test"], control["control_id"]
        assert control["rule"], control["control_id"]
        assert control["severity"] in {"BLOCKER", "HIGH"}


def test_three_blocker_controls_carry_no_owner_and_no_status(sigdb):
    """A FINDING, pinned rather than tidied.

    FW15 ENGINE_COMPUTE_ONLY, FW16 SERIALIZER_ONLY_API and FW17
    NO_DEVICE_MODEL_ARTIFACT are all BLOCKER, all sourced to the "v39w
    thin-client ruling", and all three leave implementation_owner and status
    empty where FW01-FW14 fill both. They were appended and the last two
    columns were not carried down.

    They are also the three that bear most directly on this service: FW16 is
    a rule about what a presentation API may do, and this build is writing
    one. A BLOCKER nobody has signed for is worth a question, not a default.
    """
    unowned = {c["control_id"] for c in sigdb["firewall_controls"]
               if c["status"] is None}
    assert unowned == {"FW15", "FW16", "FW17"}

    for control in sigdb["firewall_controls"]:
        if control["control_id"] in unowned:
            assert control["severity"] == "BLOCKER"
            assert control["implementation_owner"] is None
            # All three arrive with v39w. Two cite the thin-client ruling
            # directly; FW17 cites "OWASP MASVS resilience + v39w", which is
            # the same batch under a different justification.
            assert "v39w" in control["source"]
        else:
            assert control["status"] == "REQUIRED"
            assert control["implementation_owner"]


# --- the gates this build can already answer ------------------------------

@pytest.mark.parametrize("qa_id,filename,key,expected", [
    ("QA004", "state_vector_219.json", None, 219),
    ("QA005", "nutrients_81.json", None, 81),
    ("QA010", "action_space_127.json", "actions", 127),
])
def test_a_release_gate_agrees_with_the_registry_it_counts(
        sigdb, qa_id, filename, key, expected):
    """THE REASON THE CONTRACT IS IN THE DATABASE. These gates are not
    documentation -- they are countable, and they count things this build
    already holds. Three ways: the gate's written expectation, the value the
    workbook computed for it, and the rows actually loaded."""
    gate = next(g for g in sigdb["qa_gates"] if g["qa_id"] == qa_id)
    assert gate["expected"] == str(expected)
    assert gate["actual_or_formula"] == expected

    loaded = _load(filename)
    rows = loaded[key] if key else loaded
    assert len(rows) == expected


def test_qa011_the_activation_hold_is_the_difference(sigdb):
    """127 registered, 126 activatable. The one held back is action 127's
    own safety hold, which this build stores and CI already asserts."""
    gate = next(g for g in sigdb["qa_gates"] if g["qa_id"] == "QA011")
    assert gate["expected"] == "126"

    actions = _load("action_space_127.json")["actions"]
    held = [a for a in actions if a.get("activation_hold")]
    assert len(actions) == 127
    assert len(held) == 1
    assert len(actions) - len(held) == 126


# --- decisions this build has already implemented -------------------------

def test_dec11_is_the_firewall_this_build_already_has(decisions):
    """'Use two schemas. engine_internal is inaccessible to mobile.'

    sql/010_firewall.sql was written before this contract was read, and they
    agree. Asserted against the migration rather than remembered.
    """
    decision = decisions["DEC11"]
    assert decision["topic"] == "Database boundary"
    assert "engine_internal" in decision["canonical_decision"]
    assert decision["status"] == "LOCKED_FOR_THIS_CONTRACT"

    firewall = (Path(__file__).parent.parent / "sql" / "010_firewall.sql"
                ).read_text(encoding="utf-8")
    assert "engine_internal" in firewall
    assert "client_render" in firewall
    assert "ROW LEVEL SECURITY" in firewall.upper()


def test_dec05_and_dec06_match_the_loaded_state_vector(decisions):
    """DEC05 locks 219 states. DEC06 rejects the stale 195/196 mapping and
    fixes 195 = meal timing, 196 = meal frequency -- which is what this
    build's state vector already says, from a different sheet.

    DEC05 does not repeat the number in its decision cell -- it writes the
    breakdown, "81 fast + 81 slow + 12 high damage + ...". So this adds it
    up, which is a better check than looking for the string anyway: it fails
    if a block is ever resized without the total being restated.
    """
    import re

    assert decisions["DEC05"]["finding"] == "Lock 219 states."
    parts = [int(n) for n in re.findall(r"\b(\d+)\b",
                                        decisions["DEC05"]["canonical_decision"])]
    assert sum(parts) == 219, parts
    assert parts[:2] == [81, 81]        # fast and slow nutrient blocks

    states = {s["idx"]: s for s in _load("state_vector_219.json")}
    assert states[195]["symbol"] == "meal_timing_reg"
    assert states[196]["symbol"] == "meal_freq_smooth"
    assert "195" in decisions["DEC06"]["canonical_decision"]
    assert "meal timing" in decisions["DEC06"]["canonical_decision"].lower()


def test_dec08_matches_the_action_space(decisions):
    decision = decisions["DEC08"]
    assert "127" in decision["canonical_decision"]
    assert "126" in decision["canonical_decision"]

    actions = _load("action_space_127.json")["actions"]
    assert len(actions) == 127
    assert sum(1 for a in actions if a.get("activation_hold")) == 1


# --- what the contract says is still open ---------------------------------

def test_the_release_blockers_are_counted_not_summarised(sigdb):
    """43 of the 68 gaps hold a release. Kept as a number this build can be
    held to rather than a phrase like 'some remain'."""
    blocking = [g for g in sigdb["gaps"]
                if g["release_gate"] == "BLOCKS_AFFECTED_FEATURE"
                and not (g["status"] or "").startswith("RESOLVED")]
    assert len(blocking) == 43

    severities = {g["severity"] for g in blocking}
    assert "BLOCKER" in severities


def test_two_gaps_describe_findings_this_build_made_independently(sigdb):
    """GAP068 and GAP059 are the state-index errors found here this week --
    the sitting_hrs slot-185-vs-188 mistake and the lifestyle-block layout
    trap. Pinned because independent agreement is evidence, and because if
    the auditor ever withdraws them this build should notice."""
    gaps = {g["finding_id"]: g for g in sigdb["gaps"]}

    assert "variable IDs" in gaps["GAP068"]["finding"]
    assert "never infer" in gaps["GAP068"]["decision"].lower()

    assert gaps["GAP059"]["severity"] == "BLOCKER"
    assert "195" in gaps["GAP059"]["finding"]
