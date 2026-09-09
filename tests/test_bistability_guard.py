"""The per-cluster ceiling on the scarring feedback loop.

Source: '★ Scarring Bistability Guard' -- manifest order 17.

The sheet derives, per cluster, the largest gamma_scar * (alpha_scar /
beta_autophagy) at which the damage-removal curve still rises monotonically.
Above it the curve folds and the cluster admits three equilibria, so a user
who crosses the fold cannot return by undoing what they did.

These tests do three things: check the sheet against itself, check it against
'M-PARAM Registry' which restates the same twelve rows, and pin the one place
where another sheet's published worked example lands outside the region these
caps admit.
"""
import json
from pathlib import Path

import pytest

DATA_DIR = Path(__file__).parent.parent / "sahacore" / "data"

# The sheet rounds every number to two decimals, and each column is rounded
# from its own unrounded value. One unit in the last displayed place is the
# tightest tolerance available; the worst real deviation is 0.0068.
TOLERANCE = 0.01


@pytest.fixture(scope="module")
def guard() -> dict:
    return json.loads((DATA_DIR / "bistability_guard.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def m_param() -> list[dict]:
    return json.loads(
        (DATA_DIR / "layer_m_scarring_params_12.json").read_text(encoding="utf-8"))


# --- the sheet against itself ----------------------------------------------

def test_twelve_clusters_with_caps(guard):
    assert [c["cluster_id"] for c in guard["caps"]] == [f"C{n}" for n in range(1, 13)]


def test_section_8_receipt_confirms_every_cap(guard):
    """The sheet carries its own second opinion -- an external audit that
    reproduced all twelve caps. Both copies are imported, so if they ever
    diverge that is visible rather than resolved by whichever was read first."""
    receipt = {r["cluster_id"]: r for r in guard["receipt"]}
    assert len(receipt) == 12
    for cap in guard["caps"]:
        got = receipt[cap["cluster_id"]]
        assert got["agrees"] == "YES"
        assert got["gamma_scar"] == cap["gamma_scar"]
        assert got["cap_gamma_r"] == cap["cap_gamma_r"]
        assert got["max_alpha_beta_ratio"] == cap["max_alpha_beta_ratio"]


def test_cap_is_gamma_times_the_max_ratio(guard):
    """The two columns state the same bound divided differently, so the
    identity is checkable rather than assumed."""
    for cap in guard["caps"]:
        product = cap["gamma_scar"] * cap["max_alpha_beta_ratio"]
        assert abs(product - cap["cap_gamma_r"]) <= TOLERANCE, cap["cluster_id"]


def test_v_repair_follows_the_stated_formula(guard):
    """Section 2: 'V_k = V_max/(k*theta) = 1.443 * tau_dam,k / tau_heal,k'."""
    for cap in guard["caps"]:
        v = 1.443 * cap["tau_dam_days"] / cap["tau_heal_days"]
        assert abs(v - cap["v_repair"]) <= TOLERANCE, cap["cluster_id"]


def test_gamma_scar_takes_only_two_values(guard):
    """Not a coincidence to widen later. A third value means the source
    changed and the caps have to be re-derived, not extended."""
    assert {c["gamma_scar"] for c in guard["caps"]} == {0.6, 1.2}


def test_no_single_number_would_serve(guard):
    """The sheet's own warning, in capitals: 'READ THE LAST COLUMN, NOT A
    SINGLE NUMBER. A blanket cap of gamma*r <= 0.75 would be 5x too tight for
    C6 and still too loose for C7.'"""
    caps = {c["cluster_id"]: c["cap_gamma_r"] for c in guard["caps"]}
    assert caps["C6"] == 4.86
    assert caps["C7"] == 0.87
    assert caps["C6"] / caps["C7"] > 5


def test_monotonicity_is_the_adopted_option(guard):
    """Section 5 records a founder decision. The caps are build-time asserts
    only while it stands: under the alternative they become one edge of a
    declared hysteresis band, which is a different engine."""
    adopted = [d for d in guard["founder_decision"] if d["status"] == "ADOPTED"]
    assert len(adopted) == 1
    assert adopted[0]["option"].startswith("NO")


def test_four_probabilistic_guards_are_recorded_with_their_placements(guard):
    """Section 6 says the point check is not enough, because the three
    parameters are uncertain priors until the Phase-2 cohort fit. The guards
    are stored as specifications; only PG-1 is placed on this sheet, and the
    sheets holding PG-2 and PG-3 are not imported yet."""
    guards = {g["guard_id"]: g for g in guard["probabilistic_guards"]}
    assert sorted(guards) == ["PG-1", "PG-2", "PG-3", "PG-4"]
    assert guards["PG-1"]["placement"] == "this sheet"
    assert "Validation Test Battery" in guards["PG-2"]["placement"]
    assert "LayerW" in guards["PG-3"]["placement"]
    for spec in guards.values():
        assert spec["specification"]


def test_the_unconstrained_ranges_are_recorded_as_the_reason(guard):
    """Why the table exists: before the caps, the declared ranges permitted
    gamma*(alpha/beta) up to 26.7 -- and a 34.8% hysteresis width that, in the
    sheet's words, nobody chose."""
    quantities = {r["quantity"]: r for r in guard["unconstrained_ranges"]}
    assert len(quantities) == 4
    worst = next(r for q, r in quantities.items() if "worst corner" in q)
    assert worst["value"] == "26.7"
    chooser = next(r for q, r in quantities.items() if "chose" in q)
    assert chooser["value"] == "nobody"


# --- the sheet against 'M-PARAM Registry' ----------------------------------

def test_m_param_registry_restates_the_same_twelve_rows(guard, m_param):
    """Two sheets carry these numbers. Neither is derived from the other on
    import, so agreement here is real corroboration -- and a disagreement
    would be a finding rather than a merge conflict."""
    by_id = {r["cluster_id"]: r for r in m_param}
    assert len(by_id) == 12
    for cap in guard["caps"]:
        got = by_id[cap["cluster_id"]]
        assert got["gamma_scar"] == cap["gamma_scar"], cap["cluster_id"]
        assert got["bound_gamma_r"] == cap["cap_gamma_r"], cap["cluster_id"]
        assert got["max_alpha_beta_ratio"] == cap["max_alpha_beta_ratio"], cap["cluster_id"]
        assert got["tau_dam_days"] == cap["tau_dam_days"], cap["cluster_id"]
        assert got["tau_heal_days"] == cap["tau_heal_days"], cap["cluster_id"]
        assert got["v_ratio"] == cap["v_repair"], cap["cluster_id"]


def test_each_cluster_sits_exactly_on_its_own_cap(guard):
    """PG-1's margin B_k = cap_k / (gamma_k * r_k) is 1 when r_k is the
    cluster's own MAX alpha/beta -- which is what makes that column the
    largest admissible ratio rather than a suggestion."""
    for cap in guard["caps"]:
        margin = cap["cap_gamma_r"] / (cap["gamma_scar"] * cap["max_alpha_beta_ratio"])
        assert margin == pytest.approx(1.0, abs=TOLERANCE), cap["cluster_id"]


# --- the finding -----------------------------------------------------------

def test_the_verification_labs_demo_point_is_outside_the_admitted_region(guard):
    """'Live Verification Lab' LAB 4 and LAB 6 run the Layer-M update at
    gamma_scar = 0.69 and alpha/beta = 4, so gamma*r = 2.76. Only C6 admits
    that; the other eleven caps are below it, and C7's is 0.87.

    Both labs return PASS and both are right: LM-P01 asks only whether
    0 <= S_next <= 1. Neither evaluates PG-1 -- LAB 6's own 'Parameter rules'
    row bounds S, theta, alpha, beta, gamma, dt and Vmax_base and says nothing
    about the group gamma*r.

    Pinned, not corrected. Amending a published worked example is the
    workbook owner's call. Reported in docs/parameter-gaps.md.
    """
    labs = json.loads((DATA_DIR / "verification_labs.json").read_text(encoding="utf-8"))
    demo = labs["layer_m_demo_point"]
    gamma_r = demo["gamma_scar"] * (
        demo["alpha_scar_per_day"] / demo["beta_autophagy_per_day"])
    assert gamma_r == pytest.approx(2.76)

    refused = [c["cluster_id"] for c in guard["caps"] if c["cap_gamma_r"] < gamma_r]
    admitted = [c["cluster_id"] for c in guard["caps"] if c["cap_gamma_r"] >= gamma_r]
    assert admitted == ["C6"]
    assert len(refused) == 11


def test_the_demo_points_gamma_scar_belongs_to_no_cluster(guard):
    """0.69 is not one of the two values the registry assigns. The lab's
    theta_elastic of 50 is C5's, whose cap is 1.08 -- the second tightest."""
    labs = json.loads((DATA_DIR / "verification_labs.json").read_text(encoding="utf-8"))
    demo = labs["layer_m_demo_point"]
    assert demo["gamma_scar"] not in {c["gamma_scar"] for c in guard["caps"]}

    m_param_rows = json.loads(
        (DATA_DIR / "layer_m_scarring_params_12.json").read_text(encoding="utf-8"))
    at_fifty = [r["cluster_id"] for r in m_param_rows
                if r["theta_elastic_au"] == demo["theta_elastic"]]
    assert at_fifty == ["C5"]
