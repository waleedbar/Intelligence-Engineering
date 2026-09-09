"""The contract that stops the state vector growing.

Sources: v39sEng2.xlsx, '03_STATE_ADMISSION_GATES' and '04_BEHAVIOR_SIDECAR',
'01_IMPORT_MANIFEST' orders 198 and 199 -- the last two registries build
step 2 names.

These sheets exist because adding a state is the natural thing to do when a
quantity matters. Mood matters, so mood becomes a state, the vector becomes
223, and every posterior and checkpoint written before that is a different
shape. Four such requests have already been made and refused; the tests below
pin the refusals and the constants that enforce them.
"""
import json
from pathlib import Path

import pytest

DATA_DIR = Path(__file__).parent.parent / "sahacore" / "data"


@pytest.fixture(scope="module")
def data() -> dict:
    return json.loads((DATA_DIR / "state_admission.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def gates(data) -> dict[str, str]:
    return {r["constant"]: r["value"] for r in data["gate_constants"]}


@pytest.fixture(scope="module")
def sidecar(data) -> dict[str, str]:
    return {r["constant"]: r["value"] for r in data["sidecar_constants"]}


# --- the constants that enforce the shape ----------------------------------

def test_a_third_independent_sheet_says_219(gates):
    """'★ State Vector v33 (219)' gives the block map, '00_ENGINEER_START'
    gives the invariant, and this gives baseline_state_n. Three sheets,
    imported separately, agreeing."""
    assert gates["baseline_state_n"] == "219"
    assert gates["baseline_nonlinear_n"] == "55"
    assert gates["baseline_sigma_branches"] == "111"
    assert gates["lifestyle_state_slots"] == "24"


def test_the_covariance_size_is_the_square_of_the_state_count(gates):
    """47961 = 219^2. The sheet writes both numbers by hand, so checking the
    identity is cheaper than trusting either."""
    assert int(gates["baseline_cov_cells"]) == int(gates["baseline_state_n"]) ** 2
    assert gates["baseline_cov_cells"] == "47961"


def test_the_sidecar_promises_to_change_nothing(sidecar):
    """The two constants that ARE the contract: "Sidecar never changes x_t"
    and "No new sigma branches"."""
    assert sidecar["state_delta"] == "0"
    assert sidecar["nonlinear_delta"] == "0"


def test_the_lifestyle_block_has_no_spare_slots(data):
    """24 slots at indices 187-210, "already fully allocated". A new
    behavioural state cannot quietly take an unused one, because there is
    none."""
    row = next(r for r in data["gate_constants"]
               if r["constant"] == "lifestyle_state_slots")
    assert row["formula_or_source"] == "187:210"
    assert "no spare" in row["engineering_meaning"].lower()


# --- the refusals ----------------------------------------------------------

def test_the_four_refused_candidates_are_named(data):
    """Pinned individually. If one of these ever changes verdict, the state
    vector changes shape, and that must be a deliberate act rather than a
    count moving."""
    refused = {c["candidate"] for c in data["candidates"]
               if c["target_representation"] == "STATE_CANDIDATE"}
    assert refused == {
        "50 activity IDs as states",
        "Extra sleep regularity state",
        "Four stress states",
        "Four mood states",
    }


def test_every_refused_candidate_was_refused_because_the_sidecar_suffices(data):
    """The refusals are not arbitrary: each says the sidecar route is
    adequate, which is what makes the alternative real rather than a
    brush-off."""
    for c in data["candidates"]:
        if c["target_representation"] == "STATE_CANDIDATE":
            assert c["sidecar_adequate"] == "Yes", c["candidate"]


def test_every_candidate_has_a_route_even_when_refused(data):
    """Ten candidates, five verdicts. A refusal with no alternative would
    leave the information with nowhere to go, and someone would add a state
    anyway."""
    verdicts: dict[str, int] = {}
    for c in data["candidates"]:
        verdicts[c["target_representation"]] = verdicts.get(c["target_representation"], 0) + 1
    assert verdicts == {"STATE_CANDIDATE": 4, "DERIVED_FEATURE": 2,
                        "EXISTING_STATE": 2, "CORE_INPUT": 1, "SIDECAR_SHADOW": 1}


def test_the_admission_rules_currently_all_hold(data):
    """The sheet's own current_result column. Three PASS, and three stated
    positions."""
    rules = {r["rule"]: r["current_result"] for r in data["admission_rules"]}
    assert rules["No state expansion admitted"] == "PASS"
    assert rules["No nonlinear branch expansion admitted"] == "PASS"
    assert rules["All state-candidate expansions rejected"] == "PASS"
    assert rules["Accepted behavioral information path"] == "KEEP 219"
    assert rules["Latent-state promotion rule"] == "BLOCKED UNTIL EVIDENCE"


# --- where behavioural information actually goes ---------------------------

def test_every_behavioural_domain_routes_into_an_existing_state(data):
    """Six domains -- activity, sleep, stress, mood, activity timing,
    autonomic response -- each naming the existing states it reaches."""
    assert len(data["routing"]) == 6
    domains = {r["domain"] for r in data["routing"]}
    assert {"Physical activity", "Sleep", "Stress", "Mood"} <= domains
    for r in data["routing"]:
        assert r["existing_core_states"], r["domain"]
        assert r["routing"], r["domain"]


def test_the_sidecar_features_assert_their_own_neutrality(data):
    """Two of the sixteen derived features exist only to check the contract
    at runtime: both must stay zero."""
    features = {f["feature"]: f["value"] for f in data["derived_features"]}
    assert features["state_delta_from_sidecar"] == "0"
    assert features["nonlinear_delta_from_sidecar"] == "0"


def test_the_example_events_are_not_loaded(data):
    """Rows 14-19 of the sidecar sheet are sample events -- ex_sleep, ex_sed,
    ex_hiit. They illustrate the shape and are documentation. Loading them
    would put six fictional activity events in a table beside real ones."""
    everything = json.dumps(data)
    for sample in ("ex_sleep", "ex_sed", "ex_lpa", "ex_walk", "ex_res", "ex_hiit"):
        assert sample not in everything


# --- the extractor refuses bad data ----------------------------------------

def test_the_builder_refuses_a_non_zero_state_delta(data):
    """The single most important line in either sheet."""
    from sahacore.data.build_state_admission import check

    broken = json.loads(json.dumps(data))
    next(r for r in broken["sidecar_constants"]
         if r["constant"] == "state_delta")["value"] = "4"
    with pytest.raises(SystemExit, match="state_delta"):
        check(broken)


def test_the_builder_refuses_a_covariance_size_that_is_not_n_squared(data):
    from sahacore.data.build_state_admission import check

    broken = json.loads(json.dumps(data))
    next(r for r in broken["gate_constants"]
         if r["constant"] == "baseline_cov_cells")["value"] = "48000"
    with pytest.raises(SystemExit, match="baseline_cov_cells"):
        check(broken)
