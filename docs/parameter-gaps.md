# Per-nutrient parameter gaps

What the engine still cannot compute from the workbooks we hold, established by
a file-by-file audit of every uploaded workbook. Written down so the gap list
stays a checked fact rather than a memory.

Audit date: 2026-09-08. Files audited: all 11 distinct workbooks (33 uploads,
deduplicated by content hash), plus four CSV result files.

## Correction to an earlier conclusion

An earlier pass in this project concluded that the per-nutrient absorption and
clearance parameters had existed in an older `P1 Nutrients 80 (v39s)` sheet and
had been deliberately removed. **That reading was wrong**, and the correction
matters because it changes what we should be asking for.

The citation it rested on is `04 Engine Binding` in the TwinAPI workbook, row
20:

    A20=T04 | B20=Per-nutrient params
    C20=Half-life, F_max/F_base/Km, V1/V2, Q/CL per nutrient row
    D20=P1 Nutrients 80 | E20=P1 Nutrients 81

The earlier pass read columns D and E as "old value / new value". They are not.
The sheet's own header says:

    D4=WHERE in v39s | E4=WHERE in v39sEng
    A2=Every citation on this sheet was checked against the uploaded v39s
       (245 sheets) and v39sEng (201 sheets). Where the two masters name a
       sheet differently (COR-2), both names are given.

So `P1 Nutrients 80` and `P1 Nutrients 81` are **the same sheet under two
names** in two masters — a rename after nitrate was added as #81, not a
richer predecessor. Nothing on that row evidences a deletion.

Two further checks confirm it:

* `v39sEng` and `v39sEng2` are identical across all 204 shared sheets --
  same dimensions, cell for cell -- differing only by the `★ v39w Signal
  Patch` sheet that `v39sEng2` adds. No older, wider version of the nutrient
  table is hiding in the files we hold.
* The five workbooks never opened before this audit (the `v39sEng` master,
  and the Twin / Atlas / Pulse / Plan variants distinct from their `...API`
  counterparts) contain no per-nutrient value for any of the missing
  parameters -- only the formulas that consume them.

**What the same header does establish** is that a master with **245 sheets**
exists. We hold 204 (`v39sEng`) and 205 (`v39sEng2`). Roughly forty sheets we
have never seen are cited by the workbooks we do have. That, not a deletion,
is the defensible thing to ask about.

## What `P1 Nutrients 81` actually carries

20 populated columns, B through U, verified directly against the workbook (no
hidden columns, rows, comments, named ranges or hidden sheets):

| | | |
|---|---|---|
| B–F | `#`, `ID`, `Name`, `Category`, `Unit` | identity |
| G–I | `γ_k (shape)`, `γ_θ (min)`, `λ (1/min)` | Layer A kernel |
| J–L | `κ_fast`, `κ_slow`, `w_fast` | fast/slow partition |
| M–N | `T½_fast (d)`, `T½_slow (d)` | Layer B half-lives |
| O | `V_f (dL)` | fast compartment volume |
| P–Q | `State Semantics`, `Canonical State Unit` | |
| R–T | `F_max`, `s_hi (log)`, `s_lo (log)` | Layer A ceiling, Layer C sensitivities |
| U | `Evidence / Observability Prior` | |

Against what `04 Engine Binding` row 20 says the per-nutrient row should hold
-- "Half-life, F_max/F_base/Km, V1/V2, Q/CL" -- half-life, `F_max` and `V1`
(= `V_f`) are present. `F_base`, `Km`, `V2` and `CL` are not.

## The gaps, with their parameter-registry rows

Every row below is from `P1 Parameters 134+`, which declares each parameter's
units, range, weight and calibration method but tabulates no per-nutrient
value.

| # | Symbol | Layer | Eq | Units | Range | Weight | We have |
|---|---|---|---|---|---|---|---|
| 14 | `F_base,i` | A | A5 | — | 0.01–1.0 | Critical | **18 / 81** |
| 15 | `K_m,i` | A | A5 | mg | 10–5000 | Critical | **0 / 81** |
| 29 | `V_s,i` | B | B3 | L | 5–200 | High | **0 / 81** |
| 37 | `f_unbound,i` | B | B5,B6,B7 | — | 0.01–1.0 | Critical | **0 / 81** |
| 41 | `CL_int,i` | B | B6 | mL/min | 0–5000 | High | **0 / 81** |

`Q_liver` (#40) is **not** a gap: it is a single physiological quantity with a
published formula -- "allometric CO = 6.5*(BW/70)^0.75 L/min (ICRP Pub 89
2003); Q_H = 0.260*CO" -- already implemented in
`sahacore/engine/pharmacokinetics.py`.

`K_m,i` is the thinnest of all: the registry gives only a 10–5000 mg range and
a single worked example, "Vitamin C K_m ~200mg" (Levine 1996 PNAS).

### The 18 known `F_base` values

Recoverable from two module sheets, and worth recording because they were not
obvious:

* `P1 Bariatric Module`, table headed "Absolute bounded F_abs targets by
  nutrient, procedure and phase (not multipliers)", column `F_bio Base` --
  17 nutrients.
* `P1 GLP-1 Module`, table headed "Nutrient absorption ODDS / timing
  modifiers -- bounded Layer A contract", column `F_base` -- 15 nutrients.

The union is 18 unique nutrients, and the 14 that appear in both agree
exactly -- iron 0.15, B12 0.5, vitamin D3 0.5, calcium 0.3, vitamin A 0.7,
vitamin E 0.3, vitamin K 0.5, folate 0.5, zinc 0.3, magnesium 0.4, protein
0.9, carbohydrate 0.95, fat 0.95, leucine 0.9. Bariatric alone adds thiamine
0.9, copper 0.35, selenium 0.8; GLP-1 alone adds potassium 0.9.

That leaves **63 of 81 without an `F_base`**.

## A second correction: the damage thresholds are NOT missing

An earlier pass also listed "cluster-level `eta_hi,k` / `theta_E,hi,k`" as
missing. They are not. `sahacore/data/damage_registry_canonical.json`, loaded
from `★ Damage Registry — Canonical`, carries:

* `eta_hi`, `eta_lo` -- populated on **108 / 108** rows
* `theta_hi`, `theta_lo` -- populated on **92 / 108** rows
* `tau_damage_days`, `tau_heal_days`, `weight_pct` -- **108 / 108**

Only **16 rows** lack thresholds, and they are a specific, nameable set:

* **C7**: `b2_mg`, `b6_mg`, `b9_ug`, `b12_ug`, `choline_mg`,
  `aa_methionine_mg`, `aa_glycine_mg`
* **C9**: `b6_mg`, `b9_ug`, `b12_ug`, `vit_d_iu`, `iron_mg`, `magnesium_mg`,
  `omega3_dha_g`, `aa_tryptophan_mg`, `aa_tyrosine_mg`

## The four CSV files

`layer_a_results_1.csv`, `layer_b_results.csv`, `layer_c_damage.csv` and
`layer_d_scoring.csv` are the output of a working Layer A–D implementation:
128 timesteps at 10-minute intervals, all 81 nutrient columns in the Layer A
file, all 12 clusters in the Layer C and D files.

`layer_b_results.csv` carries `CL_total_<nutrient>` and `k_el_<nutrient>` for
seven nutrients -- iron, vitamin D, B12, calcium, protein, vitamin C, zinc --
constant across all 128 rows, so they are parameters rather than state.

The half-lives implied by those `k_el` values are clean literature figures:

| nutrient | t½ from `k_el` | our `T½_fast` | our `T½_slow` |
|---|---|---|---|
| iron | 60 d | 2 | 60 |
| vitamin D | 15 d | 3 | 60 |
| B12 | 180 d | 2 | 480 |
| calcium | 0.8 d | 1 | 30 |
| protein | 0.25 d | 1 | 10 |
| vitamin C | 0.4 d | 0.5 | 10 |
| zinc | 5 d | 2 | 60 |

Only iron matches a column we hold. **A parameter set richer than the one in
`P1 Nutrients 81` exists and has been run** -- which is the strongest single
piece of evidence for the request.

## Consequence for the build

`05 Build Flow & Deploy` phase 1 is "Registries + parameters + nutrients (the
data spine)", and the parameters half of it cannot be completed from what we
hold. Layers A–D are implemented and pass their own equation tests, but until
these five columns arrive they run on registry-documented *ranges* rather than
per-nutrient values. Structure is unblocked; calibration is not.
