"""The workbook's six worked examples, re-derived here.

Source: 'Live Verification Lab' -- manifest order 5.

The sheet calls itself "the load-bearing numbers, re-derived by live formulas
in front of you". These tests take it at its word: each lab's inputs are read
from the import, the quantity is recomputed in Python, and the result is
compared against what the workbook published. That is the whole point of
importing a verification lab -- a number the engine can be held to that this
build did not choose.

Where a lab states its own gate, the gate is used as written. LAB 1 passes at
|integral - 1| < 1e-2 and LAB 3 at |rho - 0.8663| < 1e-3; neither is tightened
here, because a tolerance this build invents is not the one the workbook
committed to.
"""
import json
import math
from pathlib import Path

import pytest

DATA_DIR = Path(__file__).parent.parent / "sahacore" / "data"


@pytest.fixture(scope="module")
def labs() -> dict:
    return json.loads((DATA_DIR / "verification_labs.json").read_text(encoding="utf-8"))


def _pane(labs: dict, lab_id: str) -> dict:
    lab = next(l for l in labs["labs"] if l["lab_id"] == lab_id)
    return {q["name"]: q for q in lab["quantities"]}


def _num(pane: dict, name: str) -> float:
    return pane[name]["value_num"]


# --- shape ------------------------------------------------------------------

def test_six_labs(labs):
    assert [l["lab_id"] for l in labs["labs"]] == [f"LAB {n}" for n in range(1, 7)]


def test_every_derived_quantity_carries_its_source_formula(labs):
    """An imported result without the formula that produced it is a number
    with no provenance -- exactly what this sheet exists to avoid."""
    for lab in labs["labs"]:
        for q in lab["quantities"]:
            if q["role"] == "INPUT":
                assert q["formula"] is None
            else:
                assert q["formula"] and q["formula"].startswith("=")


def test_no_lab_publishes_a_failing_verdict(labs):
    verdicts = [q for lab in labs["labs"] for q in lab["quantities"]
                if q["role"] == "VERDICT"]
    assert len(verdicts) == 7
    for q in verdicts:
        assert q["value_text"] not in ("FALSE",)
        assert not q["value_text"].startswith("FAIL")


# --- LAB 1 · the gamma absorption kernel integrates to 1 --------------------

def test_gamma_kernel_integrates_to_one(labs):
    """h(t) is a two-component gamma mixture; the lab integrates it by
    trapezoid over the same grid it declares and asks for |integral - 1| < 1e-2.

    The residual is NOT zero and the sheet says why: 'cached demo residual =
    0.0051962079 from 720-min truncation + quadrature'. So this reproduces the
    residual rather than asserting the integral is 1 -- a truncated grid that
    integrated to exactly 1 would mean the quadrature was wrong.
    """
    p = _pane(labs, "LAB 1")
    k1, l1 = _num(p, "k1 fast shape"), _num(p, "λ1 fast rate (1/min)")
    k2, l2 = _num(p, "k2 slow shape"), _num(p, "λ2 slow rate (1/min)")
    w = _num(p, "w fast fraction")
    dt, end = _num(p, "grid step dt (min)"), _num(p, "grid end T (min)")

    def gamma_pdf(t: float, shape: float, rate: float) -> float:
        if t <= 0:
            return 0.0
        return rate ** shape * t ** (shape - 1) * math.exp(-rate * t) / math.gamma(shape)

    grid = [i * dt for i in range(int(end / dt) + 1)]
    h = [w * gamma_pdf(t, k1, l1) + (1 - w) * gamma_pdf(t, k2, l2) for t in grid]
    area = sum((h[i] + h[i + 1]) / 2 * dt for i in range(len(h) - 1))

    published = _num(p, "∫h·dt  (trapezoid sum)")
    assert area == pytest.approx(published, rel=1e-12)
    assert abs(published - 1) < 1e-2       # the sheet's own gate


# --- LAB 2 · zero-order-hold gain vs Euler ---------------------------------

def test_zero_order_hold_gain_matches_the_published_grid(labs):
    """The exact gain is (1 - e^(-k*dt))/k. Euler uses dt, and the error the
    sheet is warning about grows with the step: 0.6% at a quarter day, 13% at
    five days."""
    k = _num(_pane(labs, "LAB 2"), "damage rate k (1/day)")
    for row in labs["zoh_grid"]:
        dt = row["dt_days"]
        analytic = (1 - math.exp(-k * dt)) / k
        assert analytic == pytest.approx(row["analytic_gain"], rel=1e-12)
        assert row["euler_gain"] == dt
        assert abs(dt - analytic) / analytic == pytest.approx(
            row["relative_error"], rel=1e-12)

    by_dt = {r["dt_days"]: r["relative_error"] for r in labs["zoh_grid"]}
    assert by_dt[0.25] < by_dt[1] < by_dt[5]


# --- LAB 3 · cascade stability ---------------------------------------------

def test_spectral_radius_of_gamma_reproduces_the_published_value(labs):
    """The lab runs power iteration twenty times and averages the last four
    norms. Run to convergence instead and the answer is 0.86631229, against
    the lab's 0.86630573 -- a difference of 6.6e-6, well inside the lab's own
    |rho - 0.8663| < 1e-3 gate, which both values pass.

    The looser check is deliberate. Holding a twenty-iteration estimate to
    machine precision would be testing the iteration count, not the claim.
    """
    matrix = labs["gamma_matrix"]
    order = {c: i for i, c in enumerate(matrix["clusters"])}
    n = len(order)
    rows = sorted(matrix["rows"], key=lambda r: order[r["driver"]])
    gamma = [r["weights"] for r in rows]

    u = [1.0] * n
    norm = 0.0
    for _ in range(500):
        v = [sum(gamma[i][j] * u[j] for j in range(n)) for i in range(n)]
        norm = math.sqrt(sum(x * x for x in v))
        if norm == 0:
            break
        u = [x / norm for x in v]

    p = _pane(labs, "LAB 3")
    published = _num(p, "ρ̂(Γ) — power iteration ×20, mean of last 4 ‖u‖ "
                        "(damps oscillation from complex subdominant eigenvalues)")
    claimed = _num(p, "claimed value in ★ Cluster Coupling Network")

    assert abs(norm - published) < 1e-3
    assert abs(published - claimed) < 1e-3     # the sheet's own gate
    assert abs(norm - published) < 1e-5, (
        "the converged radius has drifted away from the lab's estimate")


def test_this_build_keeps_eta_net_at_zero(labs):
    """THE FINDING. LAB 3 labels row 100 'eta_net (operating gain)' and holds
    it at 0.05, then derives a 'stability bound 1/rho' and a 'margin x0.5
    (recommended ceiling)' of 0.577.

    Three places say otherwise:

      00_ENGINEER_START row 27  'Cluster coupling | OFF (ETA=0)', gate
                                eta_net_zero.
      Parameter #138 eta_net    'production value is exactly 0'.
      Parameter #141 rho_Gamma  'matrix diagnostic; do not derive an eta
                                 ceiling from 1/rho alone' -- which is the
                                 derivation rows 118-119 perform.

    The lab's arithmetic is sound and its verdict is true; the disagreement is
    about what the number means. This build follows the invariant and the
    registry, and the test pins both sides so neither can move quietly.
    """
    p = _pane(labs, "LAB 3")
    lab_value = _num(p, "η_net (operating gain)")
    assert lab_value == 0.05
    assert p["η_net (operating gain)"]["role"] == "INPUT"

    invariants = json.loads(
        (DATA_DIR / "runtime_invariants.json").read_text(encoding="utf-8"))
    gate = next(r for r in invariants if r["gate"] == "eta_net_zero")
    assert gate["value"] == "OFF (ETA=0)"

    parameters = json.loads(
        (DATA_DIR / "parameter_registry_192.json").read_text(encoding="utf-8"))
    eta = next(r for r in parameters if r["symbol"] == "eta_net")
    assert eta["param_no"] == 138
    assert eta["default_or_range"].startswith("0 production")

    rho = next(r for r in parameters if r["symbol"] == "rho_Gamma")
    assert "do not derive an eta ceiling from 1/rho alone" in rho["default_or_range"]

    assert lab_value != 0, (
        "if the lab is ever corrected to 0 this finding is closed -- delete "
        "the test and the entry in docs/parameter-gaps.md rather than "
        "loosening it")


def test_gamma_is_a_sparse_hypothesis_not_a_dense_matrix(labs):
    """Runtime invariant row 27: 'Numeric Gamma edges remain hypotheses.'

    Nineteen of the 144 cells are non-zero. Two clusters drive nothing at all
    (C10 Bone, C12 Cardio) and five are never driven (C3, C4, C7, C8, C11), so
    the matrix is a sketch of a few proposed pathways rather than a coupling
    model of the twelve. That is a further reason the spectral radius of it is
    a diagnostic and not a stability governor -- parameter #141's point.
    """
    matrix = labs["gamma_matrix"]
    weights = [w for row in matrix["rows"] for w in row["weights"]]
    assert len(weights) == 144
    assert sum(1 for w in weights if w != 0) == 19
    assert all(0 <= w <= 0.8 for w in weights)

    silent = [r["driver"] for r in matrix["rows"] if not any(r["weights"])]
    assert silent == ["C10 Bone", "C12 Cardio"]

    driven = {c for row in matrix["rows"]
              for c, w in zip(matrix["clusters"], row["weights"]) if w}
    assert sorted(set(matrix["clusters"]) - driven) == [
        "C11 Thy/Adr", "C3 Prot", "C4 Elec", "C7 Methyl", "C8 Gut"]


# --- LAB 4 and LAB 6 · the Layer-M scar update -----------------------------

def test_layer_m_scar_update_reproduces_every_published_quantity(labs):
    """LAB 6 states the production equation as 'dS/dt = alpha*o*(1-S) -
    beta*S' and its exact update as 'S_next = S_inf + (S - S_inf)*exp[-(alpha*o
    + beta)*dt]'. Both labs run it at the same eight inputs."""
    d = labs["layer_m_demo_point"]
    overshoot = max(0.0, (d["z_t"] - d["theta_elastic"]) / d["theta_elastic"])
    a = d["alpha_scar_per_day"] * overshoot
    q = a + d["beta_autophagy_per_day"]
    s_inf = a / q
    s_next = s_inf + (d["s_t"] - s_inf) * math.exp(-q * d["dt_days"])

    p4 = _pane(labs, "LAB 4")
    assert overshoot == pytest.approx(_num(p4, "overshoot o = MAX(0,(Z−θ)/θ)"))
    assert a == pytest.approx(_num(p4, "a = α·o"))
    assert s_inf == pytest.approx(_num(p4, "S∞ = a/(a+β)"))
    assert s_next == pytest.approx(
        _num(p4, "S_next = S∞+(S−S∞)·e^(−(a+β)Δt)"), rel=1e-12)

    # LM-P03: the half-life is set by beta alone, not by the forcing.
    assert 1 / d["beta_autophagy_per_day"] == pytest.approx(_num(p4, "τ = 1/β (days)"))
    assert math.log(2) / d["beta_autophagy_per_day"] == pytest.approx(
        _num(p4, "t½ = LN(2)/β (days)  [LM-P03]"), rel=1e-12)

    v_eff = d["vmax_base"] * math.exp(-d["gamma_scar"] * s_next)
    assert v_eff == pytest.approx(
        _num(p4, "Vmax_eff = Vmax_base·e^(−γ·S_next)"), rel=1e-12)

    # LAB 6 recomputes the same quantities in its own pane.
    p6 = _pane(labs, "LAB 6")
    assert _num(p6, "S_next") == pytest.approx(
        _num(p4, "S_next = S∞+(S−S∞)·e^(−(a+β)Δt)"), rel=1e-12)
    assert _num(p6, "q = a+beta") == pytest.approx(q)


def test_lm_p01_bounds_hold(labs):
    p4 = _pane(labs, "LAB 4")
    s_next = _num(p4, "S_next = S∞+(S−S∞)·e^(−(a+β)Δt)")
    assert 0 <= s_next <= 1
    assert p4["LM-P01 bounds verdict (0 ≤ S_next ≤ 1)"]["value_text"] == "PASS"


def test_lm_p02_two_half_steps_equal_one_full_step(labs):
    """The exact update is a fixed point of its own step size. Euler is not,
    which is LAB 2's point restated in Layer M."""
    d = labs["layer_m_demo_point"]
    overshoot = max(0.0, (d["z_t"] - d["theta_elastic"]) / d["theta_elastic"])
    q = d["alpha_scar_per_day"] * overshoot + d["beta_autophagy_per_day"]
    s_inf = (d["alpha_scar_per_day"] * overshoot) / q

    def step(s: float, dt: float) -> float:
        return s_inf + (s - s_inf) * math.exp(-q * dt)

    full = step(d["s_t"], d["dt_days"])
    halves = step(step(d["s_t"], d["dt_days"] / 2), d["dt_days"] / 2)
    assert halves == pytest.approx(full, rel=1e-15)


def test_layer_m_rules_are_transcribed(labs):
    rules = {r["name"]: r["statement"] for r in labs["layer_m_rules"]}
    assert rules["Production equation"] == "dS/dt = alpha·o·(1−S) − beta·S"
    assert rules["Exact update"].startswith("S_next = S_inf")
    assert rules["Replay rule"].startswith("Start from stored S_k/P_S checkpoint")


def test_the_parameter_rules_row_says_nothing_about_gamma_times_r(labs):
    """Why the demo point can sit outside the admitted region and still pass:
    LAB 6 lists the bounds it checks, and the bistability group is not among
    them. See tests/test_bistability_guard.py for the finding itself."""
    rules = {r["name"]: r["statement"] for r in labs["layer_m_rules"]}
    parameter_rules = rules["Parameter rules"]
    for bounded in ("S∈[0,1]", "theta>0", "alpha>=0", "beta>0", "gamma>=0"):
        assert bounded in parameter_rules
    assert "gamma*r" not in parameter_rules
    assert "cap" not in parameter_rules


# --- LAB 5 · the Layer-T anomaly score -------------------------------------

def test_topology_anomaly_score(labs):
    """A_topo = ||tau(t) - tau(t-30d)|| / (1 + ||tau(t-30d)||)."""
    vectors = labs["topology_vectors"]
    delta = math.sqrt(sum((v["tau_now"] - v["tau_reference"]) ** 2 for v in vectors))
    reference = math.sqrt(sum(v["tau_reference"] ** 2 for v in vectors))

    p = _pane(labs, "LAB 5")
    assert delta == pytest.approx(_num(p, "‖Δτ‖₂ = SQRT(SUMXMY2)"), rel=1e-12)
    assert reference == pytest.approx(_num(p, "‖τ(t−30d)‖₂"), rel=1e-12)
    assert delta / (1 + reference) == pytest.approx(
        _num(p, "A_topo = ‖Δτ‖/(1+‖τ_ref‖)"), rel=1e-12)


def test_the_topology_flag_is_context_only(labs):
    """It fires here, and firing must stay inert: 'the flag is a NEUTRAL
    context surface only -- it never changes a score, a level or a ranking'."""
    p = _pane(labs, "LAB 5")
    score = _num(p, "A_topo = ‖Δτ‖/(1+‖τ_ref‖)")
    threshold = _num(p, "θ_topo")
    assert score > threshold
    assert _num(p, "consecutive nights over θ (hysteresis = 3)") == 3
    verdict = p["flag verdict (A_topo > θ AND 3 nights)"]["value_text"]
    assert verdict == "FIRE (context only)"
