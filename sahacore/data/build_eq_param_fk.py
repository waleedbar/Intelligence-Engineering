"""Extracts the equation-to-parameter foreign-key registry into
eq_param_fk.json.

Source: v39sEng2.xlsx, sheet 'PARAM · Eq Param FK' -- "equation-to-parameter
foreign keys for Python backend". Columns: Eq ID / pattern | Consumes
parameter keys | Authoritative registry sheet | Backend data object |
Validation / migration rule.

This is the second half of build step 2's "current parameter/FK registries",
and it is what makes that step's acceptance test -- "no missing FK" --
checkable at all. The parameter registry says what each parameter IS; this
says which equation CONSUMES it and which registry is authoritative for its
value.

    python -m sahacore.data.build_eq_param_fk <path-to-workbook>

TWO PROPERTIES OF THE SOURCE THAT SHAPE THIS EXTRACTOR

1. Only 22 of the 126 rows name their keys explicitly. The other 104 say
   "see formula inputs and named parameter refs" -- a pointer back to the
   equation sheet rather than a key list. Those rows are kept, with
   keys_are_explicit=false, because they still declare an authoritative
   registry and a backend object, which is most of their value. Dropping
   them would make the registry look 5x smaller than it is.

2. `eq_id` is NOT unique. A-001, A-002 and B-001 each appear twice: once in
   the block that lists parameter keys explicitly and once in the block that
   maps equations to Python functions, with different backend objects
   (nutrient_absorption_params vs layer_a_absorption_kernel). The sheet's
   own row number is therefore the stable identity.

3. A key resolves ONLY within its own row's authoritative sheet. The same
   token means different things in different rows: `Q` is the
   inter-compartment flow in B-002/B-003 (authority: P1 Parameters 134+ and
   P1 Nutrients 81) and the process-noise covariance in E-003/E-004
   (authority: State Vector v33, Rao-Blackwellization, E · Estimation
   Build). Resolving keys globally against one registry silently equates
   them. So resolution here is always per row.

ALIASES. The FK sheet and the parameter registry spell the same parameter
differently -- `k_i1` against `k1_i`, `Km_i` against `K_m,i`,
`T_half_fast_days` against `T_half,i`. Each alias below is stated explicitly
with the difference it bridges, rather than being produced by a fuzzy match
that could pair two unrelated symbols.
"""
import json
import re
import sys
from pathlib import Path

import openpyxl

SHEET = "PARAM · Eq Param FK"
OUT = Path(__file__).parent / "eq_param_fk.json"
PLACEHOLDER = "see formula inputs"

# FK key -> (parameter-registry symbol, the equation IDs the alias is valid
# for, why the two spellings differ).
#
# SCOPED, NOT GLOBAL. A first version of this table was keyed on the spelling
# alone, and produced two false resolutions that a reviewer caught:
#
#   `delta_i` in K3-FIX-04 (backend object hawkes_params, alongside
#   lambda_max/mu_base/nu_D) was resolved to #16 delta_ij, the Layer A
#   co-nutrient absorption interaction coefficient. Unrelated quantities.
#
#   `Km` in the QSSA row was resolved to #15 K_m,i, the absorption Michaelis
#   constant in mg. QSSA's Km is an enzyme constant in micromolar.
#
# The same spelling means different things in different rows, exactly as `Q`
# does, so every alias now names the rows it applies to and is inert
# everywhere else.
ALIASES = {
    "k_i1": ("k1_i", {"A-001"}, "subscript order: entity-then-component vs component-then-entity"),
    "k_i2": ("k2_i", {"A-001"}, "subscript order"),
    "lambda_i1": ("lam1_i", {"A-001"}, "lambda spelled out; subscript order"),
    "lambda_i2": ("lam2_i", {"A-001"}, "lambda spelled out; subscript order"),
    "F_base_i": ("F_base,i", {"A-002"}, "underscore vs comma before the entity subscript"),
    "F_max_i": ("F_max,i", {"A-002"}, "underscore vs comma"),
    "Km_i": ("K_m,i", {"A-002"}, "underscore placement inside the symbol"),
    "V1": ("V_f,i", {"B-002/B-003"}, "compartment numbered rather than named: 1 = fast"),
    "V2": ("V_s,i", {"B-002/B-003"}, "compartment numbered rather than named: 2 = slow"),
    "k_fs": ("k_fs,i", {"B-002/B-003"}, "entity subscript dropped"),
    "gamma_ij": ("gamma_ij", {"A-002"}, "identical spelling; scoped so it cannot leak into another row"),
}

# Keys that are foreign keys to a NON-parameter registry -- an action, a rule,
# a model, a version -- and so can never resolve in the parameter registry.
# Classified rather than reported as missing.
NON_PARAMETER_KEYS = {
    "veto_rule_id", "action_id", "hazard_model_id", "nuisance_model_id",
    "score_version", "evidence_tier", "E_value_method", "transition_Q",
    "cofactor_hill_params", "W_params", "cooldowns", "g_factors",
    "deferral_flag", "propensity_bounds", "side",
}

# Registry sheets this build has actually loaded, and the table that holds
# each. Anything else is declared authoritative by the sheet but not yet
# imported -- which is the honest reading of "no missing FK" today.
LOADED_REGISTRIES = {
    "P1 Nutrients 81": "engine_internal.nutrients",
    "P1 Nutrients 81 M:N": "engine_internal.nutrients",
    "P1 Parameters 134+": "engine_internal.parameter_registry",
    "★ Damage Registry — Canonical": "engine_internal.damage_registry_canonical",
    "REG · Nutrient×Cluster Long": "engine_internal.nutrient_cluster_weights",
    "P1 TVMCD Pathways": "tvmcd_pathways_15.json",
    "M-PARAM Registry": "engine_internal.layer_m_scarring_params",
    "P1 QSSA ATP-GSH-NAD": "engine_internal.qssa_atp_complexes",
    "IO · Lineage DataMap": "engine_internal.raw_events (+ ledger tables)",
    "Action_Space": "engine_internal.action_space",
    # The FK sheet names the authority by its historical sheet name. That
    # sheet is not the registry: its own third row reads "REFERENCE ONLY --
    # the sheet name is historical and does not guarantee the active registry
    # row count. Production/build loaders MUST use MERGE·VETO Drug-Nutrient
    # 339, the active registry with 339 unique canonical rule_ids." So the
    # authority this name denotes IS the table below, and the redirect is the
    # workbook's own, not a guess about which sheet was meant.
    "VETO Canonical 339": "engine_internal.veto_drug_nutrient",
}


# '★ Param Registry +20' writes Greek letters where the FK sheet spells them
# out. Transliteration only, and only for comparison -- no symbol is renamed.
_GREEK = {
    "λ": "lambda", "γ": "gamma", "κ": "kappa", "τ": "tau", "θ": "theta",
    "α": "alpha", "β": "beta", "μ": "mu", "σ": "sigma", "ρ": "rho",
    "δ": "delta", "ε": "epsilon", "η": "eta", "ω": "omega", "ν": "nu",
    "Ω": "Omega", "ξ": "xi", "φ": "phi", "ψ": "psi",
}


def translit(text: str) -> str:
    for greek, latin in _GREEK.items():
        text = text.replace(greek, latin)
    return text


# FK key -> (symbol in '★ Param Registry +20', the equation rows it is valid
# for, why the two spellings differ). Scoped exactly as ALIASES is, and for
# the same reason.
#
# Only entries whose difference is more than the Greek alphabet belong here.
# `mu_base`/`μ_base`, `delta_i`/`δ_i` and `nu_D`/`ν_D` match after
# transliteration alone and are deliberately NOT listed: an alias that
# restates a rule already applied is a place for a mistake to hide.
EXT20_ALIASES = {
    "alpha_scar": ("α_scar,k", {"K3-FIX-01"},
                   "Greek alpha spelled out, and the sheet carries the "
                   "per-cluster subscript k that the FK key omits"),
    "beta_autophagy": ("β_autophagy,k", {"K3-FIX-01"},
                       "Greek beta spelled out; same per-cluster subscript"),
}


# FK keys that '★ Equation Backbone' defines as the OUTPUT of an equation
# rather than a value to look up. Each entry cites the backbone row and the
# formula, and is scoped to the FK rows it applies to -- the same discipline
# as ALIASES, for the same reason.
#
# `CL` was reported MISSING_FK on B-002/B-003 for exactly the right reason:
# it is in neither authority that row names. The backbone shows why. It is
# not a parameter anyone forgot to write down; B4 computes it from B5 and B6.
#
# `Q` in the same row is deliberately NOT here. B2 and B3 use it and no
# backbone row defines it, so it stays a missing FK -- which is the
# distinction this table exists to make rather than blur.
COMPUTED_BY_BACKBONE = {
    "CL": ("B4", "CL = CL_renal + CL_hepatic", {"B-002/B-003"}),
}


def _split_authorities(cell: str | None) -> list[str]:
    """The authority cell lists one or more sheets separated by ';', often
    with a parenthetical gloss ('★ Damage Registry — Canonical (108 weighted
    nutrient×cluster rows; ...)'). The gloss itself contains semicolons, so
    the parentheses are stripped before splitting."""
    if not cell:
        return []
    text = re.sub(r"\([^)]*\)", "", str(cell))
    return [part.strip() for part in text.split(";") if part.strip()]


def extract(workbook_path: str) -> list[dict]:
    ws = openpyxl.load_workbook(workbook_path, data_only=True)[SHEET]
    rows = []
    for r in range(3, ws.max_row + 1):
        eq = ws.cell(row=r, column=1).value
        keys_cell = ws.cell(row=r, column=2).value
        if not eq or not keys_cell:
            continue
        explicit = PLACEHOLDER not in str(keys_cell)
        keys = (
            [k.strip() for k in str(keys_cell).split(",") if k.strip()]
            if explicit else []
        )
        authorities = _split_authorities(ws.cell(row=r, column=3).value)
        rows.append({
            "source_row": r,
            "eq_id": str(eq).strip(),
            "keys_are_explicit": explicit,
            "consumes_keys": keys,
            "authoritative_sheets": authorities,
            "loaded_registries": [LOADED_REGISTRIES[a] for a in authorities
                                  if a in LOADED_REGISTRIES],
            "all_authorities_loaded": bool(authorities) and all(
                a in LOADED_REGISTRIES for a in authorities),
            "backend_object": (str(ws.cell(row=r, column=4).value).strip()
                               if ws.cell(row=r, column=4).value else None),
            "validation_rule": (str(ws.cell(row=r, column=5).value).strip()
                                if ws.cell(row=r, column=5).value else None),
        })
    return rows


# A key resolves against the columns of whichever registry ITS OWN row
# declares authoritative -- not against the parameter registry globally.
# `T_half_fast_days` is not a parameter-registry symbol; it is a column of
# P1 Nutrients 81, which is exactly what row B-001 names as its authority.
REGISTRY_KEY_ALIASES = {
    "engine_internal.nutrients": {
        # A1's absorption kernel. Only the FAST gamma is a column; the slow
        # component of the mixture is deliberately mapped to None so it
        # reports as a real missing FK rather than quietly resolving.
        "k_i1": "gamma_k_shape",
        "lambda_i1": "lambda_per_min",
        "k_i2": None,             # A1 slow gamma shape -- no column exists
        "lambda_i2": None,        # A1 slow gamma rate  -- no column exists
        "w_i": "w_fast",
        # A4's bounded fraction.
        "F_max_i": "f_max",
        "F_base_i": None,         # no column exists
        "Km_i": None,             # no column exists
        "gamma_ij": None,         # interaction terms live in O·O9 / MERGE·VETO k_ij
        "gamma_cook": None,       # A7 cooking factor: a per-food modifier, not a nutrient column
        "gamma_condition": None,  # A4 condition modifier: comes from O·O8, not the nutrient row
        # B-001.
        "T_half_fast_days": "half_life_fast_d",
        "T_half_slow_days": "half_life_slow_d",
    },
    "engine_internal.damage_registry_canonical": {
        "tau_damage": "tau_damage_days",
        "eta": "eta_hi",          # the row carries both sides; `side` selects which
        "threshold": "theta_hi",  # likewise
    },
    "engine_internal.layer_m_scarring_params": {
        "theta_elastic": "theta_elastic_au",
        "gamma_scar": "gamma_scar",
        "alpha_scar": None,       # registry ships only the alpha/beta RATIO, not alpha itself
        "beta_autophagy": None,   # same
    },
}


def resolve_key(key: str, registry_symbols: set[str],
                loaded: list[str], columns: dict[str, set[str]],
                all_loaded: bool = True, eq_id: str = "",
                ext20_symbols: set[str] | None = None) -> tuple[str, str | None]:
    """Classify one FK key against its row's own authoritative registries.

    Returns (status, where). Statuses:
      NON_PARAMETER  a foreign key to an action/rule/model registry
      COMPUTED       '★ Equation Backbone' defines it as an equation's
                     output, so there is no value to look up
      RESOLVED       found in one of this row's loaded authorities
      NOT_LOADED     this row's authority exists in the workbook but this
                     build has not imported it yet
      RESOLVED_ELSEWHERE
                     found in the parameter registry, which this row does
                     not name as its authority. Legitimate for engine-wide
                     constants (the damage exponent p is one), but recorded
                     separately so a cross-registry resolution is never
                     mistaken for the declared one.
      MISSING_FK     the authority IS loaded and the key is in no loaded
                     registry at all -- the only status that fails
                     "no missing FK"
    """
    if key in NON_PARAMETER_KEYS:
        return "NON_PARAMETER", None

    # A quantity an equation computes is not a parameter with a missing value.
    if key in COMPUTED_BY_BACKBONE and eq_id in COMPUTED_BY_BACKBONE[key][2]:
        backbone_id, formula, _ = COMPUTED_BY_BACKBONE[key]
        return "COMPUTED", f"equation_backbone:{backbone_id} ({formula})"

    for registry in loaded:
        aliases = REGISTRY_KEY_ALIASES.get(registry, {})
        if key in aliases:
            target = aliases[key]
            if target is None:
                continue  # explicitly not a column of this registry
            if target in columns.get(registry, set()):
                return "RESOLVED", f"{registry}.{target}"
        if registry == "engine_internal.parameter_registry":
            if key in ALIASES and eq_id in ALIASES[key][1]:
                symbol = ALIASES[key][0]
                if symbol in registry_symbols:
                    return "RESOLVED", f"parameter_registry:{symbol}"
                return "ALIAS_BROKEN", symbol
            if key in registry_symbols:
                return "RESOLVED", f"parameter_registry:{key}"
        elif key in columns.get(registry, set()):
            return "RESOLVED", f"{registry}.{key}"

    if not loaded:
        return "NOT_LOADED", None

    # Engine-wide constants are legitimately defined in the parameter
    # registry even when a row names a per-entity registry as its authority.
    if key in registry_symbols:
        return "RESOLVED_ELSEWHERE", f"parameter_registry:{key}"
    if key in ALIASES and eq_id in ALIASES[key][1] and ALIASES[key][0] in registry_symbols:
        return "RESOLVED_ELSEWHERE", f"parameter_registry:{ALIASES[key][0]}"

    # '★ Param Registry +20' is the second parameter registry. No FK row names
    # it as its authority -- it postdates the FK sheet -- so anything found
    # here is RESOLVED_ELSEWHERE by the same rule that governs the base
    # registry: the parameter is defined, just not in the sheet this row
    # points at. That is a parameter_gaps question, not a missing_fk one.
    ext20 = ext20_symbols or set()
    if ext20:
        by_translit = {translit(s): s for s in ext20}
        if key in ext20:
            return "RESOLVED_ELSEWHERE", f"param_registry_ext20:{key}"
        if translit(key) in by_translit:
            return "RESOLVED_ELSEWHERE", f"param_registry_ext20:{by_translit[translit(key)]}"
        if key in EXT20_ALIASES and eq_id in EXT20_ALIASES[key][1]:
            target = EXT20_ALIASES[key][0]
            if target in ext20:
                return "RESOLVED_ELSEWHERE", f"param_registry_ext20:{target}"

    # A key can only be called MISSING when EVERY registry its row declares
    # authoritative has actually been imported. If one of them is still
    # unloaded, the honest answer is that we have not looked yet -- accusing
    # the build of a missing FK against a sheet nobody has opened would
    # inflate the failure count with work that simply is not done.
    if not all_loaded:
        return "NOT_LOADED", None
    return "MISSING_FK", None


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m sahacore.data.build_eq_param_fk <workbook.xlsx>")
    rows = extract(sys.argv[1])

    registry = json.loads(
        (Path(__file__).parent / "parameter_registry_192.json").read_text(encoding="utf-8"))
    symbols = {p["symbol"] for p in registry}

    here = Path(__file__).parent
    columns = {
        "engine_internal.nutrients": set(json.loads(
            (here / "nutrients_81.json").read_text(encoding="utf-8"))[0]),
        "engine_internal.damage_registry_canonical": set(json.loads(
            (here / "damage_registry_canonical.json").read_text(encoding="utf-8"))[0]),
        "engine_internal.layer_m_scarring_params": set(json.loads(
            (here / "layer_m_scarring_params_12.json").read_text(encoding="utf-8"))[0]),
        "engine_internal.nutrient_cluster_weights": set(json.loads(
            (here / "nutrient_cluster_weights.json").read_text(encoding="utf-8"))[0]),
        "engine_internal.qssa_atp_complexes": set(json.loads(
            (here / "qssa_atp_complexes_5.json").read_text(encoding="utf-8"))[0]),
        "tvmcd_pathways_15.json": set(json.loads(
            (here / "tvmcd_pathways_15.json").read_text(encoding="utf-8"))[0]),
        "engine_internal.veto_drug_nutrient": set(json.loads(
            (here / "veto_drug_nutrient_339.json").read_text(encoding="utf-8"))[0]),
        "engine_internal.action_space": set(json.loads(
            (here / "action_space_127.json").read_text(encoding="utf-8"))["actions"][0]),
    }

    ext20 = {r["symbol"] for r in json.loads(
        (here / "param_registry_ext20.json").read_text(encoding="utf-8"))
        if r["symbol"]}

    for row in rows:
        row["key_resolution"] = {
            key: {"status": status, "resolved_in": where}
            for key in row["consumes_keys"]
            for status, where in [resolve_key(key, symbols, row["loaded_registries"],
                                              columns, row["all_authorities_loaded"],
                                              row["eq_id"], ext20)]
        }

    OUT.write_text(json.dumps(rows, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    explicit = [r for r in rows if r["keys_are_explicit"]]
    counts: dict[str, int] = {}
    for r in explicit:
        for v in r["key_resolution"].values():
            counts[v["status"]] = counts.get(v["status"], 0) + 1
    print(f"wrote {len(rows)} FK rows to {OUT.name} "
          f"({len(explicit)} with explicit keys, {len(rows)-len(explicit)} pointing back to their equation sheet)")
    for status in sorted(counts):
        print(f"   {status:<16}{counts[status]}")
    broken = [(r["eq_id"], k) for r in explicit
              for k, v in r["key_resolution"].items() if v["status"] == "ALIAS_BROKEN"]
    if broken:
        raise SystemExit(f"alias points at a symbol not in the registry: {broken}")


if __name__ == "__main__":
    main()
