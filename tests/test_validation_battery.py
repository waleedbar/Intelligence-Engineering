"""The engine's acceptance criteria, and how much of them this build runs.

Source: '★ Validation Test Battery' -- manifest order 14.

71 named tests, 54 of them BLOCKING. Most test layers that do not exist yet.
What these tests do is keep the register honest: every claim that this repo
enforces a battery criterion has to name the test making the claim, and the
few criteria that ARE executable against loaded registries are executed here
rather than described.
"""
import json
from pathlib import Path

import pytest

DATA_DIR = Path(__file__).parent.parent / "sahacore" / "data"


@pytest.fixture(scope="module")
def battery() -> dict:
    return json.loads(
        (DATA_DIR / "validation_battery.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def tests_by_id(battery) -> dict:
    return {t["test_id"]: t for t in battery["tests"]}


# --- the register ----------------------------------------------------------

def test_seventy_one_tests_over_eleven_sections(battery):
    assert len(battery["tests"]) == 71
    assert len(battery["sections"]) == 11


def test_most_of_the_battery_is_blocking(battery):
    gates = {}
    for test in battery["tests"]:
        gates[test["gate"]] = gates.get(test["gate"], 0) + 1
    assert gates["BLOCKING"] == 54
    assert sum(gates.values()) == 71


def test_every_coverage_claim_names_the_test_that_makes_it(battery):
    """The table can only report a green build by naming something. A claim
    with no test behind it is the failure mode this guards."""
    for test in battery["tests"]:
        if test["coverage"] == "NOT_YET":
            assert test["enforced_by"] is None
            assert test["coverage_note"] is None
        else:
            assert test["enforced_by"], test["test_id"]
            assert test["coverage_note"], test["test_id"]


def test_every_named_enforcing_test_actually_exists(battery):
    """A path in the coverage column that does not resolve is worse than no
    claim at all -- it reads as covered."""
    root = Path(__file__).parent.parent
    for test in battery["tests"]:
        if not test["enforced_by"]:
            continue
        path, _, function = test["enforced_by"].partition("::")
        target = root / path
        assert target.exists(), f"{test['test_id']} names missing {path}"
        if function:
            source = target.read_text(encoding="utf-8")
            assert f"def {function}(" in source, (
                f"{test['test_id']} names {function}, which is not in {path}")


def test_the_coverage_this_build_actually_has(battery):
    """Pinned so it can only move deliberately. 6 enforced and 7 partial out
    of 71 is the honest state of a build still importing its registries."""
    coverage = {}
    for test in battery["tests"]:
        coverage[test["coverage"]] = coverage.get(test["coverage"], 0) + 1
    assert coverage == {"ENFORCED": 6, "PARTIAL": 7, "NOT_YET": 58}


def test_the_dropped_test_is_recorded_not_forgotten(battery):
    """A removed acceptance test is a decision. The sheet explains why it
    dropped a whole-body integrative test, and the note is imported."""
    note = battery["dropped_test_note"]
    assert note and "DROPPED" in note


# --- the criteria this build can already execute ---------------------------

def test_i7_damage_registry_columns_sum_to_100_exactly(tests_by_id):
    """I7, BLOCKING: 'All twelve columns sum to 100.0 exactly.'"""
    assert tests_by_id["I7"]["gate"] == "BLOCKING"
    rows = json.loads(
        (DATA_DIR / "damage_registry_canonical.json").read_text(encoding="utf-8"))
    sums: dict[str, float] = {}
    for row in rows:
        sums[row["cluster_id"]] = sums.get(row["cluster_id"], 0.0) + row["weight_pct"]
    assert len(sums) == 12
    for cluster, total in sums.items():
        assert total == 100.0, f"{cluster}: {total!r}"


def test_i8_nutrient_cluster_columns_sum_to_one(tests_by_id):
    """I8, BLOCKING: 'All twelve columns sum to 1.000000.'"""
    assert tests_by_id["I8"]["gate"] == "BLOCKING"
    rows = json.loads(
        (DATA_DIR / "nutrient_cluster_weights.json").read_text(encoding="utf-8"))
    sums: dict[str, float] = {}
    for row in rows:
        sums[row["cluster_id"]] = sums.get(row["cluster_id"], 0.0) + row["weight"]
    assert len(sums) == 12
    for cluster, total in sums.items():
        assert total == pytest.approx(1.0, abs=1e-9), f"{cluster}: {total!r}"


def test_c16_theta_elastic_is_ratified_per_cluster(tests_by_id):
    """C16, BLOCKING: 'Assert that each cluster loads its ratified
    theta_elastic and that no cluster [is missing one]. All 12 clusters carry
    a ratified value in 42-70 AU; a missing or out-of-[range value fails].'

    The registry's twelve values span 42 to 70 exactly -- both endpoints are
    used, so the declared window is the observed range and not a loose box
    drawn round it.
    """
    assert tests_by_id["C16"]["gate"] == "BLOCKING"
    rows = json.loads(
        (DATA_DIR / "layer_m_scarring_params_12.json").read_text(encoding="utf-8"))
    assert len(rows) == 12
    values = []
    for row in rows:
        theta = row["theta_elastic_au"]
        assert 42 <= theta <= 70, f"{row['cluster_id']}: theta_elastic={theta}"
        values.append(theta)
    assert min(values) == 42 and max(values) == 70


def test_c17_is_only_half_available_and_says_so(tests_by_id):
    """C17, BLOCKING: 'B_k >= 1 AND p_viol,k < 0.01 for all 12 clusters. A
    point estimate passing while p_viol >= 0.01 [is not a pass].'

    The margin is implemented; the posterior is not, because it does not
    exist until the Phase-2 cohort fit. Marked PARTIAL rather than ENFORCED,
    and this test exists so that stays true until the second half is real.
    """
    c17 = tests_by_id["C17"]
    assert c17["coverage"] == "PARTIAL"
    assert "p_viol" in c17["pass_criterion"]
    assert "p_viol" in c17["coverage_note"]


def test_the_battery_and_the_guard_sheet_agree_about_the_bistability_bound(tests_by_id):
    """C14 and C17 in the battery, PG-1 and PG-2 in '★ Scarring Bistability
    Guard'. Two sheets, imported separately, describing the same gate with
    the same formula -- corroboration, not duplication."""
    guard = json.loads(
        (DATA_DIR / "bistability_guard.json").read_text(encoding="utf-8"))
    pg2 = next(g for g in guard["probabilistic_guards"] if g["guard_id"] == "PG-2")
    assert "C17" in pg2["placement"]
    assert "p_viol" in pg2["specification"]
    assert "0.01" in pg2["specification"]
    assert "0.01" in tests_by_id["C17"]["pass_criterion"]

    c14 = tests_by_id["C14"]
    assert "gamma_scar*(alpha_scar/beta_autophagy)" in c14["method"]
    assert "per-cluster cap" in c14["pass_criterion"]


def test_the_battery_confirms_eta_net_stays_zero(tests_by_id):
    """A fourth source on the finding in tests/test_verification_labs.py.

    C8's method opens 'With eta=0 as production baseline', and its criterion
    is that eta stays 0 unless held-out calibration improves AND the full
    Jacobian is stable -- 'max Re eig(J_full)'. S7 says the same from the
    other side: coupling is retained only if held-out calibration IMPROVES.

    Neither mentions 1/rho. That is what makes 'Live Verification Lab' rows
    118-119 -- 'stability bound 1/rho' and a 'recommended ceiling' of 0.577 --
    a disagreement rather than a shorthand: the battery's stability criterion
    is the full Jacobian, exactly as parameter #141 says.
    """
    c8 = tests_by_id["C8"]
    assert c8["gate"] == "BLOCKING"
    assert "η=0 as production baseline" in c8["method"]
    assert "J_full" in c8["pass_criterion"]
    assert "1/rho" not in c8["pass_criterion"] and "1/ρ" not in c8["pass_criterion"]

    s7 = tests_by_id["S7"]
    assert "η_net = 0" in s7["method"]
    assert "IMPROVES" in s7["pass_criterion"]


def test_i16_is_the_veto_gate_this_build_already_runs(tests_by_id):
    """The battery's I16 and the Replay Contract's VETO-01 are the same
    check, arrived at from two sheets."""
    i16 = tests_by_id["I16"]
    assert "339 rows and 339 unique canonical rule IDs" in i16["pass_criterion"]
    assert "source_rule_id retained" in i16["pass_criterion"]

    veto = json.loads(
        (DATA_DIR / "veto_drug_nutrient_339.json").read_text(encoding="utf-8"))
    assert len(veto) == 339
    assert len({r["rule_id"] for r in veto}) == 339
    assert len({r["source_rule_id"] for r in veto}) == 319


# --- what is not yet enforced ----------------------------------------------

def test_the_unenforced_blocking_backlog_is_visible(battery):
    """54 BLOCKING criteria: 6 enforced, 7 partial, 41 that nothing in this
    repo executes. Expected while the layers are unbuilt, and recorded as a
    number rather than left to be discovered at release.

    Every criterion this build touches at all is a BLOCKING one -- the six
    MONITORED tests and the ten BLOCKING_FOR_* ones are all untouched, which
    is the right order to have worked in.
    """
    blocking = [t for t in battery["tests"] if t["gate"] == "BLOCKING"]
    assert len(blocking) == 54
    assert sum(1 for t in blocking if t["coverage"] == "ENFORCED") == 6
    assert sum(1 for t in blocking if t["coverage"] == "PARTIAL") == 7
    assert sum(1 for t in blocking if t["coverage"] == "NOT_YET") == 41

    covered = [t for t in battery["tests"] if t["coverage"] != "NOT_YET"]
    assert all(t["gate"] == "BLOCKING" for t in covered)


def test_c1_is_not_claimed_as_enforced(tests_by_id):
    """C1 asks for |integral - 1| < 1e-6 across all 81 nutrients. This build
    verifies the kernel against the workbook's published integral, but on the
    demo grid, whose residual is 5.2e-3 -- four orders above the criterion.

    The gap is quadrature, not the kernel: the trapezoid rule converges at
    O(dt^k) in the smallest shape parameter, so the demo's k=1.5 component
    caps the rate at O(dt^1.5) rather than the O(dt^2) an engineer would
    assume, and 1e-6 needs dt near 0.01 min. Recorded in
    docs/parameter-gaps.md; PARTIAL until an implementation meets 1e-6.
    """
    c1 = tests_by_id["C1"]
    assert c1["coverage"] == "PARTIAL"
    assert "1e-6" in c1["pass_criterion"]
    assert "81 nutrients" in c1["pass_criterion"]
