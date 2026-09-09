"""The equation-to-parameter FK registry, and build step 2's acceptance test.

Source: v39sEng2.xlsx, sheet 'PARAM · Eq Param FK'. '★ Build Guide Python'
step 2 requires "current parameter/FK registries" with the acceptance test
"no missing FK"; this file is where that test actually runs.

WHAT "NO MISSING FK" MEANS HERE. A key fails only when every registry its own
row declares authoritative has been imported and the key is in none of them.
Two weaker readings were rejected:

  * resolving every key against the parameter registry globally, which would
    equate tokens that mean different things in different rows -- `Q` is the
    inter-compartment flow in B-002/B-003 and the process-noise covariance in
    E-003/E-004;
  * counting a key against an authority nobody has loaded yet, which would
    report unfinished importing as an engine defect.
"""
import json
from pathlib import Path

import pytest

DATA_DIR = Path(__file__).parent.parent / "sahacore" / "data"


@pytest.fixture(scope="module")
def fk() -> list[dict]:
    return json.loads((DATA_DIR / "eq_param_fk.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def params() -> list[dict]:
    return json.loads((DATA_DIR / "parameter_registry_192.json").read_text(encoding="utf-8"))


def _by_status(fk, status):
    return [(r["eq_id"], k) for r in fk
            for k, v in r["key_resolution"].items() if v["status"] == status]


# --- extraction fidelity ---------------------------------------------------

def test_all_126_fk_rows_are_extracted_and_eq_id_is_not_the_identity(fk):
    """126 rows, but only 123 distinct equation IDs: A-001, A-002 and B-001
    each appear twice -- once in the block that lists parameter keys and once
    in the block that maps equations to Python functions, with different
    backend objects. Keying on eq_id would silently drop three rows, so the
    sheet's own row number is the identity."""
    assert len(fk) == 126
    assert len({r["source_row"] for r in fk}) == 126
    assert len({r["eq_id"] for r in fk}) == 123

    twice = {r["eq_id"] for r in fk if [x["eq_id"] for x in fk].count(r["eq_id"]) > 1}
    assert twice == {"A-001", "A-002", "B-001"}
    for eq_id in twice:
        objects = {r["backend_object"] for r in fk if r["eq_id"] == eq_id}
        assert len(objects) == 2, f"{eq_id}'s two rows should carry different backend objects"


def test_the_placeholder_rows_are_kept_not_dropped(fk):
    """104 of the rows say "see formula inputs and named parameter refs"
    instead of listing keys. Dropping them would make the registry look five
    times smaller than it is, and would lose the authority and backend-object
    columns they still carry."""
    explicit = [r for r in fk if r["keys_are_explicit"]]
    placeholder = [r for r in fk if not r["keys_are_explicit"]]
    assert len(explicit) == 22
    assert len(placeholder) == 104
    for r in placeholder:
        assert r["consumes_keys"] == []
        assert r["authoritative_sheets"], f"{r['eq_id']} declares no authority"


def test_every_row_declares_at_least_one_authoritative_registry(fk):
    for r in fk:
        assert r["authoritative_sheets"], f"{r['eq_id']} has no authority"


def test_an_authority_glosss_semicolons_do_not_split_it(fk):
    """The Damage Registry's authority cell is
    '★ Damage Registry — Canonical (108 weighted nutrient×cluster rows; both
    high/low sides on each row; 81-nutrient namespace)'. Splitting on ';'
    before stripping the parenthetical would produce three fake sheet names."""
    row = next(r for r in fk if r["eq_id"] == "C-004/C-005" and r["keys_are_explicit"])
    assert row["authoritative_sheets"] == ["★ Damage Registry — Canonical"]


# --- the acceptance test ---------------------------------------------------

def test_no_missing_fk_is_exactly_these_eight(fk):
    """Build step 2's acceptance test. Pinned by (equation, key) so a change
    says which FK moved, not merely that the count did.

    Every entry is a real hole in the workbook rather than unfinished work
    here, and all are documented in docs/parameter-gaps.md.

    THE COUNT GREW FROM FOUR TO EIGHT WHEN THE SAFETY REGISTRIES LOADED, and
    that is the number becoming more truthful rather than the build
    regressing. H-001/H-006 declares 'VETO Canonical 339' and 'Action_Space'
    authoritative for its keys. While neither was imported, its keys were
    NOT_LOADED -- unfinished importing, not a missing FK, exactly as
    test_a_missing_fk_is_only_claimed_when_every_authority_is_loaded
    requires. Both are now loaded, so the four keys neither table carries are
    reported for what they are.
    """
    assert set(_by_status(fk, "MISSING_FK")) == {
        # Layer B's two-compartment ODE consumes a total clearance and an
        # inter-compartment flow. 'P1 Parameters 134+' defines CL_int,i
        # (intrinsic hepatic clearance) and Q_liver (hepatic blood flow) --
        # different quantities. There is no symbol for either of these.
        ("B-002/B-003", "CL"),
        ("B-002/B-003", "Q"),
        # M1 consumes alpha_scar and beta_autophagy separately. M-PARAM
        # Registry ships max_alpha_beta_ratio and bound_gamma_r -- the RATIO
        # and its guard -- never the two rates on their own.
        ("K3-FIX-01", "alpha_scar"),
        ("K3-FIX-01", "beta_autophagy"),
        # Layer H's conservative-decision objective. Its risk and uncertainty
        # penalties resolve (#132 lambda_r, #131 lambda_u), but the budget
        # penalty, the two bound z-scores and the baseline offset are in
        # neither authority it names, nor in the parameter registry.
        ("H-001/H-006", "lambda_b"),
        ("H-001/H-006", "z_B"),
        ("H-001/H-006", "z_R"),
        ("H-001/H-006", "baseline_delta"),
    }


def test_a_missing_fk_is_only_claimed_when_every_authority_is_loaded(fk):
    """The precision that makes the count above meaningful: a key is never
    called missing against a sheet nobody has opened."""
    for eq_id, key in _by_status(fk, "MISSING_FK"):
        row = next(r for r in fk if r["eq_id"] == eq_id)
        assert row["all_authorities_loaded"], (
            f"{eq_id}.{key} is reported MISSING_FK but {row['authoritative_sheets']} "
            "are not all loaded -- that is unfinished importing, not a missing FK"
        )


def test_the_same_token_in_two_rows_is_not_resolved_to_one_parameter(fk):
    """`Q` appears in B-002/B-003 (inter-compartment flow) and in E-003/E-004
    (process-noise covariance). Per-row resolution is what keeps them apart:
    the first is a missing FK, the second is simply not loaded."""
    b = next(r for r in fk if r["eq_id"] == "B-002/B-003" and r["keys_are_explicit"])
    e = next(r for r in fk if r["eq_id"] == "E-003/E-004" and r["keys_are_explicit"])
    assert b["key_resolution"]["Q"]["status"] == "MISSING_FK"
    assert e["key_resolution"]["Q"]["status"] == "NOT_LOADED"


# --- resolution quality ----------------------------------------------------

def test_every_resolved_key_names_where_it_resolved(fk):
    for r in fk:
        for key, v in r["key_resolution"].items():
            if v["status"] in ("RESOLVED", "RESOLVED_ELSEWHERE"):
                assert v["resolved_in"], f"{r['eq_id']}.{key} resolved to nothing"
            else:
                assert v["resolved_in"] is None


def test_no_alias_points_at_a_symbol_the_registry_does_not_have(params):
    """An alias whose target is not in the registry would resolve nothing
    while reading as a resolution. The builder raises on this; asserted here
    too so it fails in CI without re-running the extractor.

    Every alias must also carry a SCOPE -- the equation rows it applies to.
    An unscoped table produced two false resolutions before this was added,
    and the next test pins both."""
    from sahacore.data.build_eq_param_fk import ALIASES

    symbols = {p["symbol"] for p in params}
    for key, (target, scope, reason) in ALIASES.items():
        assert target in symbols, f"alias {key!r} -> {target!r} is not a registry symbol"
        assert scope, f"alias {key!r} is unscoped -- it would apply in every row"
        assert len(reason) > 8, f"alias {key!r} has no reason recorded"


def test_the_absorption_kernels_two_halves_resolve_to_different_places(fk):
    """A-001 consumes both gamma components. 'P1 Nutrients 81' carries one
    triple, so the fast pair resolves against real columns and the slow pair
    is reported rather than quietly aliased onto the fast one."""
    a1 = next(r for r in fk if r["eq_id"] == "A-001"
              and r["keys_are_explicit"])["key_resolution"]
    assert a1["k_i1"]["resolved_in"] == "engine_internal.nutrients.gamma_k_shape"
    assert a1["lambda_i1"]["resolved_in"] == "engine_internal.nutrients.lambda_per_min"
    # The slow pair still RESOLVES -- k2_i and lam2_i are parameters #2 and
    # #4 in the registry -- but resolves ELSEWHERE, against the parameter
    # registry rather than the nutrient table this row names. That is the
    # honest reading: the parameter is defined, it simply has no per-nutrient
    # value, which is parameter_gaps' problem and not missing_fk's. The two
    # views stay orthogonal.
    assert a1["k_i2"]["status"] == "RESOLVED_ELSEWHERE"
    assert a1["k_i2"]["resolved_in"] == "parameter_registry:k2_i"
    assert a1["lambda_i2"]["resolved_in"] == "parameter_registry:lam2_i"


def test_the_two_false_resolutions_a_global_alias_table_produced_stay_fixed(fk):
    """Aliases are scoped because an unscoped table resolved two keys to
    unrelated parameters:

      delta_i in K3-FIX-04 (backend object hawkes_params, sitting beside
      lambda_max / mu_base / nu_D) resolved to #16 delta_ij, the Layer A
      co-nutrient absorption interaction coefficient.

      Km in the QSSA row resolved to #15 K_m,i, the absorption Michaelis
      constant in mg. QSSA's Km is an enzyme constant in micromolar.

    Both must now report NOT_LOADED -- their real authorities (K3 Fixes,
    QSSA · Internal Canonical) have not been imported.
    """
    hawkes = next(r for r in fk if r["eq_id"] == "K3-FIX-04")
    assert hawkes["backend_object"] == "hawkes_params"
    assert hawkes["key_resolution"]["delta_i"]["status"] == "NOT_LOADED"

    qssa = next(r for r in fk if r["eq_id"].startswith("QSSA-001"))
    assert qssa["key_resolution"]["Km"]["status"] == "NOT_LOADED"


def test_ids_and_model_references_are_classified_not_reported_as_missing(fk):
    """`veto_rule_id`, `action_id`, `hazard_model_id` and friends are foreign
    keys to other registries. Counting them as missing parameters would
    inflate the failure list with things that were never parameters."""
    non_params = {k for _, k in _by_status(fk, "NON_PARAMETER")}
    assert {"veto_rule_id", "action_id", "hazard_model_id", "score_version"} <= non_params


def test_the_registries_this_build_still_owes_are_recorded(fk):
    """Everything blocked on an unimported registry, so the remaining work is
    a list rather than a feeling."""
    owed = {sheet
            for r in fk
            if any(v["status"] == "NOT_LOADED" for v in r["key_resolution"].values())
            for sheet in r["authoritative_sheets"]
            if not r["all_authorities_loaded"]}
    assert "P1 Scoring Alerts" in owed
    assert "K3 Fixes" in owed
    assert "QSSA · Internal Canonical" in owed

    # No longer owed: both safety registries are loaded. 'VETO Canonical 339'
    # is the FK sheet's historical name for the active registry, which that
    # sheet itself redirects to MERGE·VETO Drug-Nutrient 339.
    assert "VETO Canonical 339" not in owed
    assert "Action_Space" not in owed


def test_the_veto_authority_name_resolves_to_the_registry_not_the_stub_sheet():
    """The redirect, made explicit. A loader that took 'VETO Canonical 339'
    at face value would import a 266-row REFERENCE ONLY sheet as the safety
    table, so the mapping is stated once, here and in LOADED_REGISTRIES,
    rather than left to whoever reads the authority column next."""
    from sahacore.data.build_eq_param_fk import LOADED_REGISTRIES

    assert LOADED_REGISTRIES["VETO Canonical 339"] == "engine_internal.veto_drug_nutrient"
    assert LOADED_REGISTRIES["Action_Space"] == "engine_internal.action_space"
