"""The engine's canonical invariants, and the gates this build can execute.

Source: v39sEng2.xlsx, sheet '00_ENGINEER_START' -- the workbook's stated
"Current engineer source of truth". 23 invariants, 18 with a gate name.

Six of those gates can be run against what this repo contains today, and they
are run below, one test each, named after the gate so a failure names the
position that broke. The other twelve wait on layers that do not exist; they
are recorded, listed by engine_internal.unenforced_gates, and asserted here
to be exactly the ones we know are waiting -- so a gate cannot quietly move
from "enforced" to "recorded" as the build changes.
"""
import json
from pathlib import Path

import pytest

DATA_DIR = Path(__file__).parent.parent / "sahacore" / "data"


def _load(name: str):
    return json.loads((DATA_DIR / name).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def invariants() -> list[dict]:
    return _load("runtime_invariants.json")


@pytest.fixture(scope="module")
def by_gate(invariants) -> dict[str, dict]:
    return {r["gate"]: r for r in invariants if r["gate"]}


# --- extraction fidelity ---------------------------------------------------

def test_all_23_invariants_with_18_gates(invariants, by_gate):
    assert len(invariants) == 23
    assert len(by_gate) == 18


def test_the_five_ungated_rows_keep_a_null_gate_rather_than_an_invented_one(invariants):
    """The behavioural sidecar rules carry no gate name in the sheet. Giving
    them one would make an unenforceable rule look enforced."""
    ungated = [r for r in invariants if not r["gate"]]
    assert len(ungated) == 5
    assert [r["value"] for r in ungated] == [
        "State remains 219",
        "Ten hard gates",
        "Derived core feature",
        "No direct physiology coefficient",
        "Events not states",
    ]
    for r in ungated:
        assert r["enforced_by"] is None


# --- the six gates this build executes -------------------------------------

def test_gate_schema_state_count_219(by_gate):
    """"Serialization, replay and stored posterior must use the ordered
    219-state contract"."""
    assert by_gate["schema_state_count_219"]["value"] == "219"
    assert len(_load("state_vector_219.json")) == 219


def test_gate_rb_partition_164_55(by_gate):
    """"RB-SR-UKF uses 111 sigma branches over the nonlinear block." The 164/55
    split is in the state vector and is checked; the 111 branch count is a
    property of an estimator this build has not written, so it is read off the
    gate's own text rather than asserted against code that does not exist."""
    gate = by_gate["rb_partition_164_55_111"]
    assert gate["value"] == "164 / 55"
    assert "111 sigma branches" in gate["engineering_meaning"]

    states = _load("state_vector_219.json")
    nonlinear = [s for s in states if s["is_nonlinear"]]
    assert len(states) - len(nonlinear) == 164
    assert len(nonlinear) == 55


def test_gate_nutrient_core_81(by_gate):
    """"Nitrate is registered as #81"."""
    assert by_gate["nutrient_core_81"]["value"] == "81"
    nutrients = _load("nutrients_81.json")
    assert len(nutrients) == 81
    nitrate = [n for n in nutrients if n["is_nitrate"]]
    assert len(nitrate) == 1
    assert nitrate[0]["num"] == 81


def test_gate_action_127_fail_closed(by_gate):
    """"127 registered / 126 activatable ... Do not force 127 active arms."

    The action space was loaded before this gate was, from a different sheet,
    and independently arrived at exactly this: 127 arms with one carrying an
    activation_hold. Two sources agreeing is the point of checking."""
    gate = by_gate["action_127_fail_closed"]
    assert gate["value"] == "127 registered / 126 activatable"
    assert "Do not force 127 active arms" in gate["engineering_meaning"]

    actions = _load("action_space_127.json")["actions"]
    held = [a for a in actions if a["activation_hold"]]
    assert len(actions) == 127
    assert len(actions) - len(held) == 126
    assert held[0]["action_id"] == 127


def test_gate_veto_339(by_gate):
    """339 canonical rules: "all subset IDs must resolve into the 339-rule
    library. VETO runs before ranking"."""
    gate = by_gate["veto_339_fk_coverage"]
    assert gate["value"] == "339 canonical rules"
    assert "VETO runs before ranking" in gate["engineering_meaning"]

    veto = _load("veto_drug_nutrient_339.json")
    assert len(veto) == 339
    assert len({r["rule_id"] for r in veto}) == 339


def test_gate_eta_net_zero(by_gate):
    """"OFF (ETA=0) ... Numeric Gamma edges remain hypotheses; any non-zero
    gain requires held-out incremental value and full-Jacobian stability."

    The parameter registry says the same thing from its own sheet: #138
    eta_net's stated default is "0 production; any non-zero value is
    shadow/data-derived". A layer C implementation that switches on cascade
    coupling has to contradict both."""
    gate = by_gate["eta_net_zero"]
    assert gate["value"] == "OFF (ETA=0)"

    params = _load("parameter_registry_192.json")
    eta_net = next(p for p in params if p["symbol"] == "eta_net")
    assert eta_net["param_no"] == 138
    assert eta_net["default_or_range"].startswith("0 production")


# --- the gates nothing yet checks ------------------------------------------

def test_the_unenforced_gates_are_exactly_these_twelve(invariants):
    """Pinned so a gate cannot drift from enforced to recorded unnoticed, and
    so the list to consult before writing a layer is a list.

    Each waits on something unwritten: Layer T, the wearable adapter, the
    organ-weight mapping, the presentation API, the Layer M formula export,
    the population BHM, the regime model, the HRV pipeline, the control
    research track and the state-admission process.
    """
    unenforced = {r["gate"] for r in invariants if r["gate"] and not r["enforced_by"]}
    assert unenforced == {
        "d14_d15_fail_closed",
        "layer_t_off",
        "parameter_provenance_gate",
        "server_only_inference",
        "layer_m_formula_26",
        "layer_m_code_export",
        "no_v37_2_sheet",
        "bhm_shadow",
        "regime_shadow",
        "rr_capability_gate",
        "control_shadow",
        "state_admission_v39v",
    }


def test_every_enforced_by_names_a_test_that_exists(invariants):
    """An enforcement claim pointing at a test nobody wrote is worse than no
    claim: it reads as covered."""
    here = Path(__file__)
    own_source = here.read_text(encoding="utf-8")
    for r in invariants:
        if not r["enforced_by"]:
            continue
        filename, _, test_name = r["enforced_by"].partition("::")
        assert filename == here.name, f"{r['gate']} points outside this file"
        assert f"def {test_name}(" in own_source, (
            f"{r['gate']} claims {test_name}, which does not exist")


def test_the_fail_closed_positions_are_recorded_verbatim(by_gate):
    """The wording matters more than the flag: "no invented organ weights",
    "no audio/raw mic persistence". A future reader needs the reason, not
    just the OFF."""
    assert "No invented organ weights" in by_gate["d14_d15_fail_closed"]["engineering_meaning"]
    assert "No audio/raw mic persistence" in by_gate["parameter_provenance_gate"]["engineering_meaning"]
    assert by_gate["layer_t_off"]["value"] == "OFF"
    assert by_gate["bhm_shadow"]["value"] == "OFFLINE_SHADOW"


# --- the extractor refuses bad data ----------------------------------------

def test_the_builder_refuses_an_enforcement_claim_for_an_unknown_gate():
    from sahacore.data.build_runtime_invariants import check

    rows = _load("runtime_invariants.json")
    import sahacore.data.build_runtime_invariants as mod
    original = mod.ENFORCED_BY
    mod.ENFORCED_BY = {**original, "gate_that_does_not_exist": "x::y"}
    try:
        with pytest.raises(SystemExit, match="does not have"):
            check(rows)
    finally:
        mod.ENFORCED_BY = original
