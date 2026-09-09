"""Extracts the 192-row parameter registry from the master workbook into
parameter_registry_192.json.

Source: v39sEng2.xlsx, sheet 'P1 Parameters 134+' -- "CURRENT VERSIONED
PARAMETER REGISTRY - units, ranges, evidence provenance, RB filter
parameters, hazards and safe-decision parameters".

The sheet is six blocks sharing one header: the base registry (rows 6-143)
plus five EXTENSION blocks appended by later versions (network coupling and
spectral features; equation corrections and mechanistic sidecars; v33 nitrate
and in-filter subsystems; the multi-rate clock; the scarring bistability
guard). All six are read; the section banners and repeated headers are
skipped by requiring a parseable parameter number.

    python -m sahacore.data.build_parameter_registry <path-to-workbook>

WHY THIS REGISTRY IS THE FOUNDATION
The registry does not hold most parameter VALUES. It holds each parameter's
identity, units, admissible range, weight and calibration method, and the
per-entity registries (P1 Nutrients 81, the damage registry, the cluster
tables) hold the values. So the registry is what makes "which parameters does
this build actually have values for?" a query instead of a memory -- which is
the whole point of loading it before any further layer work.

Two columns are derived here rather than transcribed, and both are recorded
so the derivation is auditable:

  value_kind      how the sheet states the value: SCALAR (one number),
                  RANGE (an admissible interval and nothing else), FORMULA,
                  PER_ENTITY_UNSPECIFIED (explicitly "varies per cluster" or
                  similar), TEXT, or ABSENT.

  resolved_by     the registry table in THIS build that supplies the actual
                  per-entity values, or null when nothing does. A parameter
                  whose value_kind is RANGE and whose resolved_by is null is
                  a genuine hole: the engine has an interval and no number.
"""
import json
import re
import sys
from pathlib import Path

import openpyxl

SHEET = "P1 Parameters 134+"
OUT = Path(__file__).parent / "parameter_registry_192.json"

COLUMNS = [
    "param_no", "symbol", "layer", "equations", "full_name", "description",
    "units", "default_or_range", "weight", "calibration_method",
    "verification_source",
]

# Which loaded registry actually supplies each parameter's per-entity values.
# Keyed by the registry's own `symbol` string, verified against the loaded
# tables rather than assumed -- tests/test_parameter_registry.py re-checks
# every mapping against the JSON seeds.
RESOLVED_BY = {
    # Every key below is a symbol string read back from the extracted
    # registry, never a guess at what the sheet "probably" calls it -- an
    # invented key would silently resolve nothing while looking resolved.
    # Every value names a column this build actually loads, and
    # tests/test_parameter_registry.py re-checks each one against the JSON
    # seeds.

    # --- Layer A: the absorption kernel's FAST component ------------------
    # A1 is a mixture of two gammas. 'P1 Nutrients 81' carries one triple, so
    # k2_i and lam2_i (the slow component) stay deliberately unresolved.
    "k1_i": "nutrients.gamma_k_shape",
    "lam1_i": "nutrients.lambda_per_min",
    "w_i": "nutrients.w_fast",
    "F_max,i": "nutrients.f_max",

    # --- Layer B ----------------------------------------------------------
    # kappa_f,i (#24) is deliberately absent: the registry defines it as the
    # absorption RATE into the fast compartment, while nutrients.kappa_fast
    # is a partition FRACTION (kappa_fast + kappa_slow = 1 on all 81 rows).
    # Mapping them would equate two different quantities.
    "T_half,i": "nutrients.half_life_fast_d / half_life_slow_d",
    "V_f,i": "nutrients.v_f_dl",
    "Q_liver": "pharmacokinetics.hepatic_blood_flow (ICRP Pub 89 2003 formula)",

    # --- Layer C ----------------------------------------------------------
    "v_ik": "nutrient_cluster_weights.weight",
    "eta_hi,k": "damage_registry_canonical.eta_hi",
    "eta_lo,k": "damage_registry_canonical.eta_lo",
    "theta_hi,k": "damage_registry_canonical.theta_hi (92 of 108 rows)",
    "theta_lo,k": "damage_registry_canonical.theta_lo (92 of 108 rows)",
    "s_hi,i": "nutrients.s_hi_log",
    "s_lo,i": "nutrients.s_lo_log",

    # --- Layer E ----------------------------------------------------------
    "L_smooth": "replay_lag_policy.l_smooth_days",
}

# Symbols this build could plausibly claim to resolve but deliberately does
# not, each with the reason. Kept beside the map so the omission is a
# decision on the record rather than an oversight.
DELIBERATELY_UNRESOLVED = {
    "kappa_f,i": "registry defines a RATE; nutrients.kappa_fast is a partition fraction",
    "beta_k": "registry uses a sigmoid steepness/midpoint pair; cluster_scoring_params "
              "carries the a_k/b_k parameterisation of D1. Not shown to be the same.",
    "mu_k": "the midpoint half of the same sigmoid pair as beta_k; mapping it to "
            "cluster_scoring_params without showing the two parameterisations agree "
            "would silently substitute one curve for another.",
    "omega_base,k": "this is w_k^fix, the fixed CHS display weight. Range 0.01-0.2, "
                    "'set proportional to clinical importance of each cluster'. "
                    "No table of the 12 values exists in any workbook.",
}


def _as_param_no(value) -> int | None:
    """The sheet stores some parameter numbers as text and some as numbers.
    Reading only the numeric ones silently drops the first 119 rows."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and float(value).is_integer():
        return int(value)
    if isinstance(value, str) and re.fullmatch(r"\d{1,4}", value.strip()):
        return int(value.strip())
    return None


def _value_kind(default_or_range: str | None) -> str:
    if default_or_range is None:
        return "ABSENT"
    text = default_or_range.strip()
    if re.fullmatch(r"-?\d+(\.\d+)?([eE][-+]?\d+)?", text):
        return "SCALAR"
    if re.fullmatch(r"-?\d+(\.\d+)?\s*[-–]\s*-?\d+(\.\d+)?", text):
        return "RANGE"
    if re.search(r"per (nutrient|cluster|pathway|state)|nutrient-specific|cluster-specific",
                 text, re.IGNORECASE):
        return "PER_ENTITY_UNSPECIFIED"
    if re.search(r"[=*/^()]|sqrt|exp|log", text):
        return "FORMULA"
    return "TEXT"


def extract(workbook_path: str) -> list[dict]:
    ws = openpyxl.load_workbook(workbook_path, data_only=True)[SHEET]
    rows = []
    for r in range(6, ws.max_row + 1):
        cells = [ws.cell(row=r, column=c).value for c in range(2, 13)]
        param_no = _as_param_no(cells[0])
        if param_no is None or cells[1] is None:
            continue  # a section banner or a repeated header
        record = {}
        for key, raw in zip(COLUMNS, cells):
            if raw is None or (isinstance(raw, str) and not raw.strip()):
                record[key] = None
            elif isinstance(raw, str):
                record[key] = raw.strip()
            else:
                record[key] = str(raw)
        record["param_no"] = param_no
        record["value_kind"] = _value_kind(record["default_or_range"])
        record["resolved_by"] = RESOLVED_BY.get(record["symbol"])
        rows.append(record)
    return sorted(rows, key=lambda x: x["param_no"])


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m sahacore.data.build_parameter_registry <workbook.xlsx>")
    rows = extract(sys.argv[1])

    numbers = [r["param_no"] for r in rows]
    assert len(set(numbers)) == len(numbers), "duplicate parameter numbers"
    assert numbers == list(range(min(numbers), max(numbers) + 1)), "gap in parameter numbering"

    OUT.write_text(json.dumps(rows, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    unresolved = [r for r in rows
                  if r["weight"] == "Critical"
                  and r["value_kind"] in ("RANGE", "PER_ENTITY_UNSPECIFIED", "ABSENT")
                  and r["resolved_by"] is None]
    print(f"wrote {len(rows)} parameters ({numbers[0]}..{numbers[-1]}) to {OUT.name}")
    print(f"critical parameters with no value and no resolving registry: {len(unresolved)}")
    for r in unresolved:
        print(f"   #{r['param_no']:<4}{r['symbol']:<16}{r['layer']:<3}{str(r['default_or_range'])[:24]}")


if __name__ == "__main__":
    main()
