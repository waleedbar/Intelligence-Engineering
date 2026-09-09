"""Extracts 'EQ · Canonical Build Rows' into eq_build_rows.json.

Source: v39sEng2.xlsx, sheet 'EQ · Canonical Build Rows'. Columns:
Stable Eq ID | Layer/Module | Formula / rule | Inputs | Outputs | Units |
Cadence | Parameter registry ref | Python module/function | Validation test |
Evidence / provenance | Production status.

    python -m sahacore.data.build_eq_build_rows <path-to-workbook>

WHY THIS SHEET
104 of the 126 rows in 'PARAM · Eq Param FK' do not list their parameter
keys; they say "see formula inputs and named parameter refs". This sheet is
where those two things live: column D is the formula inputs and column H is
the named parameter reference. Extracting it is following the pointer the FK
sheet gives, which is the only way to close that coverage without inventing
keys.

WHAT IS NOT DONE HERE
The Inputs column is a mixture. Some cells are parameter symbols
("k_i1,λ_i1,k_i2,λ_i2,w_i", "T½_fast/T½_slow"); others are prose naming data
or another equation's output ("diagnosed conditions", "server clock; user
timezone", "meal doses; F_abs; h_i*"). Treating every token as a parameter
key would manufacture foreign keys the workbook never declared.

So each token is classified, never converted:

    SYMBOL       it matches exactly one parameter-registry symbol of this
                 row's own layer, after the transliteration declared in GREEK
                 below and the same punctuation normalisation the registry
                 extractor uses.
    AMBIGUOUS    it matches more than one, and neither sheet says which.
                 Candidates recorded, resolution withheld.
    OTHER_LAYER  the registry holds that spelling, but for another layer's
                 quantity. Rejected candidates recorded. This is not the same
                 as PROSE: it says the parameter this row needs is absent from
                 the registry while a homograph of it is present.
    PROSE        it matches none. Recorded verbatim, not guessed at.

A token is only ever called a parameter when the registry actually contains
that symbol, once, in this row's layer.
"""
import json
import re
import sys
import unicodedata
from pathlib import Path

import openpyxl

from sahacore.data.build_eq_param_fk import ALIASES

SHEET = "EQ · Canonical Build Rows"
OUT = Path(__file__).parent / "eq_build_rows.json"

COLUMNS = {
    1: "eq_id",
    2: "layer_module",
    3: "formula_or_rule",
    4: "inputs_verbatim",
    5: "outputs",
    6: "units",
    7: "cadence",
    8: "parameter_registry_ref",
    9: "python_module_function",
    10: "validation_test",
    11: "evidence_provenance",
    12: "production_status",
}

# The equation sheet writes Greek letters; the parameter registry writes their
# Latin names. Transliteration only -- no symbol is renamed, and nothing is
# mapped to a different quantity.
GREEK = {
    "λ": "lam", "γ": "gamma", "κ": "kappa", "τ": "tau", "θ": "theta",
    "α": "alpha", "β": "beta", "μ": "mu", "σ": "sigma", "ρ": "rho",
    "δ": "delta", "ε": "epsilon", "η": "eta", "ω": "omega", "ξ": "xi",
    "φ": "phi", "ψ": "psi", "Γ": "Gamma", "Ω": "Omega", "½": "_half",
}

# The Inputs cell separates tokens with commas, semicolons or slashes.
_SPLIT = re.compile(r"[;,/]| and ")

# The build sheet writes a bare Greek letter where the FK sheet spells the
# name out: `λ_i1` here against `lambda_i1` there. Transliterating λ to "lam"
# (GREEK, above) does not close that gap, because "lam" is the registry's
# spelling and "lambda" is the FK sheet's.
#
# So this table does one thing only: it says which FK-sheet key a Greek-spelled
# build token is the same writing of. It resolves nothing by itself -- the key
# it produces still has to be an alias that build_eq_param_fk already declared
# and scoped to this very equation, and the test asserts exactly that. The
# claim "λ_i1 is lam1_i" is therefore still made in one place, once, with its
# reason attached; this only spells it.
GREEK_SPELLINGS = {
    "λ_i1": "lambda_i1",
    "λ_i2": "lambda_i2",
}

# 'Layer/Module' cell -> the letter the parameter registry's Layer column uses.
# Both sheets carry this; nothing is derived. Cells naming something that is
# not a lettered layer ('Global', 'TVMCD', 'VoI', 'QSSA', ...) yield None, and
# a None layer disambiguates nothing.
_LAYER = re.compile(r"^Layer ([A-Z])$")


def _layer_letter(layer_module: str | None) -> str | None:
    m = _LAYER.match((layer_module or "").strip())
    return m.group(1) if m else None


def _translit(text: str) -> str:
    for greek, latin in GREEK.items():
        text = text.replace(greek, latin)
    return unicodedata.normalize("NFKC", text)


def _normalise(symbol: str) -> str:
    """Same punctuation normalisation the registry uses, so `k_i1` and `k1_i`
    compare equal while `delta_i` and `delta_ij` still do not."""
    s = _translit(symbol).strip().lower()
    s = re.sub(r"\s*\(.*?\)\s*", "", s)
    s = s.replace("_", "").replace(",", "").replace(" ", "")
    # A trailing entity subscript is not part of the symbol's identity.
    s = re.sub(r"(?<=[a-z])(ik|ij|jk)$", "", s)
    return s


def classify_inputs(inputs_verbatim: str | None,
                    registry_rows: list[dict],
                    eq_id: str = "",
                    layer_module: str | None = None) -> list[dict]:
    """Split the Inputs cell and label each token, resolving only what both
    sheets agree on.

    Two ways a token becomes a SYMBOL, and no third:

      it is an alias ALREADY declared and scoped in build_eq_param_fk for
        this very equation -- the same table, reused rather than re-derived,
        so an alias is justified once and applies everywhere; or
      it normalises to exactly one registry symbol whose Layer column does
        not contradict this row's Layer/Module cell.

    WHY THE LAYER IS CHECKED. A short symbol is not unique across a 192-row
    registry, and matching on spelling alone manufactures foreign keys between
    unrelated quantities. Two forms of that appeared here, and both are real:

      Nine normalised keys are shared by two or three registry symbols --
      `w_i` (#5, Layer A fast-fraction weight) against `w_i (B4)` (#31, Layer
      B compartment weighting); `alpha (UKF)` against `alpha (UCB)`; `K_ij`
      against `K (folds)`. A dict keyed on the normalised spelling keeps one
      of each pair and drops the other, by set iteration order. That is how
      A-001's `w_i` came to point at the Layer B parameter.

      A spelling can also be unique in the registry and still belong to
      something else entirely. C-004 is `Z_hi = ρ_hi Z_hi + ...` off the
      "persistence registry"; the only `rho` in the registry is #108, the
      Layer H ADMM penalty parameter. D-001's `b_k` is a scoring intercept
      from 'P1 Scoring Alerts'; the only `b_k` is #93, the Layer F
      cause-specific bias. K3-FIX-04's `δ` is a Hawkes decay from 'M-PARAM
      Registry'; the only `delta` is #16, the Layer A absorption interaction
      coefficient -- the very false resolution the FK table's scoped aliases
      were introduced to stop, arriving a second time by another spelling.

    Both sheets carry the layer, so requiring them to agree reads a column
    rather than inferring anything. It is applied only where there is
    something to check: a Layer/Module cell that names something other than a
    lettered layer ('VoI', 'Global', 'TVMCD') makes no claim to contradict, so
    K3-U4's `R` in `EIG = 0.5 logdet(I + HPHᵀR⁻¹) − λcost` still resolves to
    #80, the measurement noise covariance.

    Everything else stays PROSE with the token kept verbatim. `T½_fast` in
    B-001 is an example: the FK sheet spells the same quantity
    `T_half_fast_days` and that spelling IS aliased, but `T½_fast` is not, so
    it is reported rather than matched on a guess.
    """
    if not inputs_verbatim:
        return []
    index: dict[str, list[dict]] = {}
    for row in registry_rows:
        index.setdefault(_normalise(row["symbol"]), []).append(row)
    scoped_aliases = {k: target for k, (target, scope, _) in ALIASES.items()
                      if eq_id in scope}
    alias_index = {_normalise(k): target for k, target in scoped_aliases.items()}
    layer = _layer_letter(layer_module)

    tokens = []
    for raw in _SPLIT.split(str(inputs_verbatim)):
        token = raw.strip()
        if not token:
            continue
        # A Greek-spelled token stands for an FK-sheet key; that key must then
        # be an alias this equation already declares, or nothing happens.
        alias_key = _normalise(GREEK_SPELLINGS.get(token, token))
        symbol = alias_index.get(alias_key)
        entry = {"token": token, "kind": "SYMBOL", "registry_symbol": symbol}
        if symbol is None:
            candidates = index.get(_normalise(token), [])
            # A candidate with no Layer of its own contradicts nothing.
            allowed = ([c for c in candidates if c["layer"] in (None, layer)]
                       if layer else candidates)
            if len(allowed) == 1:
                entry["registry_symbol"] = allowed[0]["symbol"]
            elif len(allowed) > 1:
                entry["kind"] = "AMBIGUOUS"
                entry["candidates"] = [c["symbol"] for c in allowed]
            elif candidates:
                entry["kind"] = "OTHER_LAYER"
                entry["candidates"] = [f"{c['symbol']} (layer {c['layer']})"
                                       for c in candidates]
            else:
                entry["kind"] = "PROSE"
        tokens.append(entry)
    return tokens


def extract(workbook_path: str, registry_rows: list[dict]) -> list[dict]:
    ws = openpyxl.load_workbook(workbook_path, data_only=True)[SHEET]
    rows = []
    for r in range(2, ws.max_row + 1):
        eq = ws.cell(row=r, column=1).value
        if not eq or str(eq).strip() in ("Stable Eq ID", ""):
            continue
        row = {"source_row": r}
        for col, name in COLUMNS.items():
            value = ws.cell(row=r, column=col).value
            row[name] = str(value).strip() if value is not None else None
        row["eq_id"] = row["eq_id"].strip()
        row["input_tokens"] = classify_inputs(row["inputs_verbatim"], registry_rows,
                                              row["eq_id"], row["layer_module"])
        rows.append(row)
    return rows


def link_to_fk(build_rows: list[dict], fk_rows: list[dict]) -> None:
    """Record, on each build row, which FK rows it supplies inputs for.

    The FK sheet groups equations in two notations, and only one of them can
    be expanded without guessing:

      "B-002/B-003"        both endpoints, and the build sheet contains each
                           of them as its own row. Verified for all seven
                           occurrences before this expansion was written.
      "M-001..W-002"       a span across equation families. Which IDs lie
                           between M-001 and W-002 is not stated anywhere,
                           so these are left unexpanded and reported.
    """
    by_id = {r["eq_id"]: r for r in build_rows}
    for r in build_rows:
        r["covers_fk_eq_ids"] = []

    for fk in fk_rows:
        eq_id = fk["eq_id"]
        if eq_id in by_id:
            targets = [eq_id]
        elif "/" in eq_id and ".." not in eq_id:
            parts = [p.strip() for p in eq_id.split("/")]
            targets = parts if all(p in by_id for p in parts) else []
        else:
            targets = []          # a ".." span, or no build row at all
        for t in targets:
            if eq_id not in by_id[t]["covers_fk_eq_ids"]:
                by_id[t]["covers_fk_eq_ids"].append(eq_id)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m sahacore.data.build_eq_build_rows <workbook.xlsx>")
    here = Path(__file__).parent
    registry = json.loads(
        (here / "parameter_registry_192.json").read_text(encoding="utf-8"))
    for key, spelled in GREEK_SPELLINGS.items():
        if spelled not in ALIASES:
            raise SystemExit(
                f"{key!r} is spelled {spelled!r}, which build_eq_param_fk does "
                "not declare as an alias -- it would resolve to nothing, or "
                "worse, to something undeclared")

    rows = extract(sys.argv[1], registry)
    fk = json.loads((here / "eq_param_fk.json").read_text(encoding="utf-8"))
    link_to_fk(rows, fk)
    OUT.write_text(json.dumps(rows, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    fk_ids = {r["eq_id"] for r in fk}
    build_ids = {r["eq_id"] for r in rows}
    linked = {e for r in rows for e in r["covers_fk_eq_ids"]}
    tokens = [t for r in rows for t in r["input_tokens"]]

    print(f"wrote {len(rows)} build rows to {OUT.name}")
    print(f"   with Inputs                  : {sum(1 for r in rows if r['inputs_verbatim'])}")
    print(f"   with parameter registry ref  : {sum(1 for r in rows if r['parameter_registry_ref'])}")
    print("   input tokens " + " / ".join(
        f"{k} {sum(1 for t in tokens if t['kind'] == k)}"
        for k in ("SYMBOL", "AMBIGUOUS", "OTHER_LAYER", "PROSE")))
    for r in rows:
        for t in r["input_tokens"]:
            if t["kind"] in ("AMBIGUOUS", "OTHER_LAYER"):
                print(f"   {t['kind']:<11} {r['eq_id']:<12} [{r['layer_module']}] "
                      f"{t['token']!r} -> {t['candidates']}")
    print(f"   FK eq_ids linked to a build row: {len(linked)} of {len(fk_ids)}")
    print(f"   FK eq_ids still unlinked       : {sorted(fk_ids - linked)}")
    print(f"   build rows not in the FK sheet: {sorted(build_ids - fk_ids)}")


if __name__ == "__main__":
    main()
