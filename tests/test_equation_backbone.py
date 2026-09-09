"""The engine's wiring map, and the three "missing parameters" it settled.

Source: v39sEng2.xlsx, sheet '★ Equation Backbone',
'01_IMPORT_MANIFEST' order 124.

58 equations with their formulas, inputs, outputs and cadence. The tests
below do two jobs: pin the extraction, and pin the three corrections this
sheet forced on docs/parameter-gaps.md -- because a correction that only
lives in prose is one edit away from being lost.
"""
import json
from pathlib import Path

import pytest

DATA_DIR = Path(__file__).parent.parent / "sahacore" / "data"


@pytest.fixture(scope="module")
def backbone() -> list[dict]:
    return json.loads((DATA_DIR / "equation_backbone.json").read_text(encoding="utf-8"))


def _by_id(backbone, eq_id, layer_prefix=None):
    rows = [r for r in backbone if r["eq_id"] == eq_id]
    if layer_prefix:
        rows = [r for r in rows if r["layer"].startswith(layer_prefix)]
    assert len(rows) == 1, f"{eq_id} matched {len(rows)} rows"
    return rows[0]


# --- extraction fidelity ---------------------------------------------------

def test_all_58_equations_are_extracted(backbone):
    assert len(backbone) == 58
    assert len({r["source_row"] for r in backbone}) == 58


def test_every_equation_carries_a_formula(backbone):
    for r in backbone:
        assert r["formula"], f"{r['eq_id']} has no formula"
        assert r["layer"] and r["name"]


def test_eq_id_is_not_the_identity_because_c2_names_two_equations(backbone):
    """Third sheet in this build where the obvious key is not unique, after
    'PARAM · Eq Param FK' (A-001, A-002, B-001) and the VETO library's source
    ids. C2 is Layer C's exact excess-damage integration and, separately, the
    Cost-Benefit net-value re-rank."""
    ids = [r["eq_id"] for r in backbone]
    repeated = {i for i in ids if ids.count(i) > 1}
    assert repeated == {"C2"}

    damage = _by_id(backbone, "C2", "C Damage")
    cost = _by_id(backbone, "C2", "C2 Cost-Benefit")
    assert "Z_hi" in damage["formula"]
    assert "Net_Value" in cost["formula"]


def test_the_layers_present_are_the_engines_own(backbone):
    """A spot check that the sheet was read as the whole engine and not a
    fragment: onboarding at one end, the Rao-Blackwellised factorisation at
    the other."""
    layers = {r["layer"] for r in backbone}
    assert "Onboarding" in layers
    assert "A Absorption" in layers
    assert "E SR-UKF" in layers
    assert "M Memory" in layers
    assert "Rao-Black." in layers


# --- the three corrections this sheet forced -------------------------------

def test_CL_is_a_sum_not_a_parameter(backbone):
    """CL was reported MISSING_FK on B-002/B-003 -- "the registry defines
    CL_int,i and Q_liver, different quantities; there is no symbol for this
    one". B4 shows why there is no symbol: it is not a parameter. It is the
    sum of two clearances that B5 and B6 each compute."""
    b4 = _by_id(backbone, "B4")
    assert b4["formula"] == "CL = CL_renal + CL_hepatic"

    b5 = _by_id(backbone, "B5")
    b6 = _by_id(backbone, "B6")
    assert "GFR" in b5["formula"]
    assert "Q_H" in b6["formula"]


def test_rho_and_g_are_computed_from_the_decay_constant(backbone):
    """docs/parameter-gaps.md listed C-004/C-005's rho and g as quantities
    the registry does not hold, hypothesised that they derive from #125
    k_Z,k, and deliberately did NOT encode that -- "a reparameterisation
    rather than a spelling", pending confirmation. C2 confirms it in the
    workbook's own notation."""
    c2 = _by_id(backbone, "C2", "C Damage")
    assert "rho=exp(-k*dt)" in c2["formula"]
    assert "g=-expm1(-k*dt)/k" in c2["formula"]


def test_the_scarring_equation_names_the_parameters_the_extension_supplies(backbone):
    """M1 consumes alpha_scar,k, beta_autophagy,k and theta_elastic,k. All
    three are now loaded -- the first two from '★ Param Registry +20', the
    third from M-PARAM Registry -- which is why K3-FIX-01 no longer reports a
    missing FK."""
    m1 = _by_id(backbone, "M1")
    assert "alpha_scar,k" in m1["formula"]
    assert "beta_autophagy,k" in m1["formula"]
    assert "theta_elastic,k" in m1["formula"]


# --- what the onboarding rows say ------------------------------------------

def test_the_onboarding_warm_start_formula_is_recorded(backbone):
    """Build Guide step 3 is sahacore.onboarding and nothing of it is written
    yet. Its warm-start prior is here, and the inputs cell names the
    onboarding modules it reads: O6 family history, O8 conditions, O11 damage
    init, O13 covariance, plus Step-12 labs."""
    onb = _by_id(backbone, "ONB")
    assert onb["layer"] == "Onboarding"
    assert "S_k(t0)" in onb["formula"]
    assert "clip(" in onb["formula"]
    for module in ("O6", "O8", "O11", "O13"):
        assert module in onb["inputs"]


def test_the_onboarding_rows_feed_the_219_state_init(backbone):
    """The dependency this build has been calling the missing link: Layer 0
    produces the initial state that Layer E and Layer M start from."""
    onb = _by_id(backbone, "ONB")
    assert "219" in onb["outputs"]
    assert onb["cadence"].lower().startswith("init")


# --- the extractor refuses bad data ----------------------------------------

def test_the_builder_refuses_a_new_id_collision(backbone):
    """C2 is a known, verified duplicate. A NEW one means either a sheet edit
    or a misread column, and either deserves a look before it is absorbed."""
    from sahacore.data.build_equation_backbone import check

    rows = [dict(r) for r in backbone]
    rows[0]["eq_id"] = rows[1]["eq_id"]
    with pytest.raises(SystemExit, match="repeated ids"):
        check(rows)


def test_the_builder_refuses_an_equation_with_no_formula(backbone):
    from sahacore.data.build_equation_backbone import check

    rows = [dict(r) for r in backbone]
    rows[0]["formula"] = None
    with pytest.raises(SystemExit, match="missing layer, name or formula"):
        check(rows)
