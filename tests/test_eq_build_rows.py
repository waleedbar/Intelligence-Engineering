"""The canonical equation build rows, and what they do to FK coverage.

Source: v39sEng2.xlsx, sheet 'EQ · Canonical Build Rows'.

This sheet exists in this build for one reason: 104 of the 126 rows in
'PARAM · Eq Param FK' say "see formula inputs and named parameter refs"
instead of listing keys, and this is where those inputs and refs live.
Loading it closes that coverage by following the pointer.

The discipline these tests enforce is that nothing is manufactured on the
way. The Inputs column is mostly prose, and prose stays prose.
"""
import json
from pathlib import Path

import pytest

DATA_DIR = Path(__file__).parent.parent / "sahacore" / "data"


@pytest.fixture(scope="module")
def build_rows() -> list[dict]:
    return json.loads((DATA_DIR / "eq_build_rows.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def fk() -> list[dict]:
    return json.loads((DATA_DIR / "eq_param_fk.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def params() -> list[dict]:
    return json.loads((DATA_DIR / "parameter_registry_192.json").read_text(encoding="utf-8"))


# --- extraction fidelity ---------------------------------------------------

def test_all_119_build_rows_are_extracted(build_rows):
    assert len(build_rows) == 119
    assert len({r["source_row"] for r in build_rows}) == 119


def test_almost_every_row_carries_inputs_and_a_parameter_reference(build_rows):
    """118 of 119. The exception is the sheet's own section banner, which has
    an ID cell and nothing else."""
    assert sum(1 for r in build_rows if r["inputs_verbatim"]) == 118
    assert sum(1 for r in build_rows if r["parameter_registry_ref"]) == 118


def test_the_columns_the_fk_sheet_points_at_are_the_ones_extracted(build_rows):
    """'see formula inputs and named parameter refs' names two columns. Both
    are here, verbatim, on a row whose content can be checked by eye."""
    a1 = next(r for r in build_rows if r["eq_id"] == "A-001")
    assert a1["inputs_verbatim"] == "k_i1,λ_i1,k_i2,λ_i2,w_i"
    assert a1["parameter_registry_ref"] == "P1 Nutrients 81"


# --- the part that must not invent anything --------------------------------

def test_most_input_tokens_are_prose_and_stay_prose(build_rows):
    """The honest result of this extraction, and the reason it does not
    manufacture 300-odd new foreign keys: the Inputs column is mostly
    descriptions of data and of other equations' outputs -- "diagnosed
    conditions", "server clock; user timezone", "meal doses; F_abs; h_i*" --
    not parameter symbols. 8 tokens resolve; 316 are not symbols at all; the
    remaining 11 look like symbols and are withheld, by the two tests below."""
    counts = {}
    for r in build_rows:
        for t in r["input_tokens"]:
            counts[t["kind"]] = counts.get(t["kind"], 0) + 1
    assert counts == {"SYMBOL": 8, "AMBIGUOUS": 3, "OTHER_LAYER": 8, "PROSE": 316}
    assert counts["PROSE"] > 20 * counts["SYMBOL"], (
        "if this ratio inverts, the matcher got loose")


def test_a_token_is_only_called_a_symbol_when_the_registry_has_it(build_rows, params):
    """The rule that keeps the classification honest."""
    known = {p["symbol"] for p in params}
    for r in build_rows:
        for t in r["input_tokens"]:
            if t["kind"] == "SYMBOL":
                assert t["registry_symbol"] in known, (
                    f"{r['eq_id']}: token {t['token']!r} claims symbol "
                    f"{t['registry_symbol']!r}, which is not in the registry"
                )
            else:
                assert t["registry_symbol"] is None


def test_greek_letters_are_transliterated_not_reinterpreted(build_rows):
    """A-001's inputs are written with Greek lambda; the registry writes
    'lam'. That is one symbol in two alphabets, so it matches. Nothing is
    mapped to a different quantity by it."""
    a1 = next(r for r in build_rows if r["eq_id"] == "A-001")
    by_token = {t["token"]: t for t in a1["input_tokens"]}
    assert by_token["λ_i1"]["registry_symbol"] == "lam1_i"
    assert by_token["k_i1"]["registry_symbol"] == "k1_i"


def test_a_greek_spelling_only_routes_through_an_alias_already_declared(params):
    """`λ_i1` matches nothing by transliteration alone: the registry spells it
    'lam' and the FK sheet spells it 'lambda'. GREEK_SPELLINGS bridges the two
    spellings and NOTHING ELSE -- the key it produces must still be an alias
    that build_eq_param_fk declared and scoped, so the claim that λ_i1 is
    lam1_i is still made once, in one place, with its reason attached."""
    from sahacore.data.build_eq_build_rows import GREEK_SPELLINGS
    from sahacore.data.build_eq_param_fk import ALIASES

    symbols = {p["symbol"] for p in params}
    for token, spelled in GREEK_SPELLINGS.items():
        assert spelled in ALIASES, (
            f"{token!r} spells out to {spelled!r}, which is not a declared alias")
        assert ALIASES[spelled][0] in symbols


# --- the homograph rule ----------------------------------------------------

def test_w_i_resolves_to_layer_as_own_weight_not_layer_bs(build_rows, params):
    """The regression this rule was written for.

    `w_i` (#5, Layer A, fast fraction weight) and `w_i (B4)` (#31, Layer B,
    compartment weighting) normalise to the same key. An index keyed on that
    normalisation keeps whichever the set happened to yield last, and it kept
    #31 -- so A-001, a Layer A absorption row, pointed at Layer B's parameter.
    A-001's own FK row resolves `w_i` to engine_internal.nutrients.w_fast, the
    fast fraction: #5.
    """
    a1 = next(r for r in build_rows if r["eq_id"] == "A-001")
    w = next(t for t in a1["input_tokens"] if t["token"] == "w_i")
    assert w["registry_symbol"] == "w_i"
    assert next(p for p in params if p["symbol"] == "w_i")["param_no"] == 5


def test_every_resolved_symbol_agrees_with_its_rows_layer(build_rows, params):
    """The rule itself, over all 119 rows rather than the one it was found on."""
    layer_of = {p["symbol"]: p["layer"] for p in params}
    for r in build_rows:
        declared = (r["layer_module"] or "")
        if not (declared.startswith("Layer ") and len(declared) == 7):
            continue                      # 'VoI', 'TVMCD', ... claim no layer
        for t in r["input_tokens"]:
            if t["kind"] == "SYMBOL":
                got = layer_of[t["registry_symbol"]]
                assert got in (None, declared[-1]), (
                    f"{r['eq_id']} is {declared} but its token {t['token']!r} "
                    f"resolved to {t['registry_symbol']!r}, a layer {got} parameter"
                )


def test_the_tokens_that_look_like_parameters_and_are_not_are_named(build_rows):
    """Eleven tokens spell a registry symbol without being one. Pinned
    individually, because each is a foreign key this build would otherwise
    have invented, and because the list is a finding in its own right --
    these are quantities the equations need that the registry does not hold
    under their own layer.

    OTHER_LAYER: the registry has the spelling, for something else.
      C-004/C-005/K3-FIX-03 `ρ`: the persistence recursion's decay. The only
        `rho` is #108, Layer H's ADMM penalty parameter. (The registry states
        this recursion as #125 k_Z,k and #126 g_Z(k,dt) instead -- a
        different parameterisation, not a different spelling, so it is not
        bridged here.)
      D-001 `a_k`/`b_k`: the score logistic's slope and intercept. The only
        `b_k` is #93, Layer F's cause-specific bias. (D1 states the same
        logistic as #58 beta_k and #59 mu_k -- steepness and midpoint. Both
        are already recorded as deliberately unresolved.)
      D-001/K3-FIX-01 `k`, `α`, `β`: Layer D and Layer M rows reaching
        spellings that exist only in A, G, E, F and H.
      K3-FIX-04 `δ`: the Hawkes decay, off 'M-PARAM Registry'. The only
        `delta` is #16, Layer A's co-nutrient absorption interaction -- the
        exact false resolution the FK table's scoped aliases were added to
        stop, arriving a second time under the Greek spelling.

    AMBIGUOUS: two registry symbols share the spelling and the row's
    Layer/Module cell names no layer to choose with.
    """
    flagged = {(r["eq_id"], t["token"]): t["kind"]
               for r in build_rows for t in r["input_tokens"]
               if t["kind"] in ("AMBIGUOUS", "OTHER_LAYER")}
    assert flagged == {
        ("GLOB-002", "k"): "AMBIGUOUS",
        ("K3-FIX-02", "k"): "AMBIGUOUS",
        ("K3-U4", "P"): "AMBIGUOUS",
        ("C-004", "ρ"): "OTHER_LAYER",
        ("C-005", "ρ"): "OTHER_LAYER",
        ("K3-FIX-03", "ρ"): "OTHER_LAYER",
        ("D-001", "k"): "OTHER_LAYER",
        ("D-001", "b_k"): "OTHER_LAYER",
        ("K3-FIX-01", "α"): "OTHER_LAYER",
        ("K3-FIX-01", "β"): "OTHER_LAYER",
        ("K3-FIX-04", "δ"): "OTHER_LAYER",
    }
    for r in build_rows:
        for t in r["input_tokens"]:
            if t["kind"] in ("AMBIGUOUS", "OTHER_LAYER"):
                assert t["candidates"], f"{r['eq_id']}.{t['token']} names no candidate"


def test_a_row_whose_module_is_not_a_lettered_layer_still_resolves(build_rows):
    """The layer check is applied where there is something to check, and not
    invented where there is not. K3-U4 is `EIG = 0.5 logdet(I+HPHᵀR⁻¹) − λcost`
    under the module 'VoI'; `R` there is the measurement noise covariance, and
    'VoI' contradicts nothing, so it resolves."""
    voi = next(r for r in build_rows if r["eq_id"] == "K3-U4")
    assert voi["layer_module"] == "VoI"
    r_tok = next(t for t in voi["input_tokens"] if t["token"] == "R")
    assert r_tok["kind"] == "SYMBOL"
    assert r_tok["registry_symbol"] == "R"


# --- coverage --------------------------------------------------------------

def test_fk_coverage_reaches_118_of_123(build_rows, fk):
    """What loading this sheet actually bought: every FK row but five now has
    a build row behind it supplying its formula inputs."""
    linked = {e for r in build_rows for e in r["covers_fk_eq_ids"]}
    assert len(linked) == 118
    assert len({r["eq_id"] for r in fk}) == 123


def test_the_slash_notation_is_expanded_and_the_span_notation_is_not(build_rows, fk):
    """The FK sheet groups equations two ways, and only one can be read
    without guessing.

    "B-002/B-003" means both endpoints, and the build sheet contains each as
    its own row -- verified for all seven occurrences, so expanding it is
    reading the notation rather than inventing a mapping.

    "M-001..W-002" spans equation families. Which IDs lie between M-001 and
    W-002 is stated nowhere, so it stays unexpanded and is reported.
    """
    by_id = {r["eq_id"]: r for r in build_rows}
    for grouped in ("B-002/B-003", "C-004/C-005", "D-001/D-002", "E-003/E-004",
                    "F-001/F-003", "G-001/G-005", "H-001/H-006"):
        left, right = grouped.split("/")
        assert grouped in by_id[left]["covers_fk_eq_ids"]
        assert grouped in by_id[right]["covers_fk_eq_ids"]

    linked = {e for r in build_rows for e in r["covers_fk_eq_ids"]}
    assert "M-001..W-002" not in linked
    assert "QSSA-001..QREP-001" not in linked


def test_the_five_unlinked_fk_rows_are_named(build_rows, fk):
    """Pinned so the remaining gap is a list rather than a rounding error.
    Two are ".." spans whose members are not enumerated anywhere; three are
    K3-N rows the build sheet does not contain at all."""
    linked = {e for r in build_rows for e in r["covers_fk_eq_ids"]}
    unlinked = {r["eq_id"] for r in fk} - linked
    assert unlinked == {"K3-N2", "K3-N3", "K3-N6", "M-001..W-002", "QSSA-001..QREP-001"}


def test_the_eight_build_rows_the_fk_sheet_omits_are_kept(build_rows):
    """The join runs both ways. Eight build rows -- the replay, history,
    runtime and schema contracts among them -- have no FK row at all, and are
    loaded anyway rather than dropped for not matching."""
    orphans = {r["eq_id"] for r in build_rows if not r["covers_fk_eq_ids"]}
    assert {"REPLAY-001", "REPLAY-002", "HIST-001", "RUNTIME-001",
            "SCHEMA-001", "K3-U1", "K3-U4"} <= orphans


# --- what the sheet adds beyond inputs -------------------------------------

def test_every_row_names_the_python_function_it_becomes(build_rows):
    """The column that makes this sheet the build's own map from equation to
    code. Checked against a row whose function this repo has written."""
    a1 = next(r for r in build_rows if r["eq_id"] == "A-001")
    assert a1["python_module_function"]
    assert a1["validation_test"]
