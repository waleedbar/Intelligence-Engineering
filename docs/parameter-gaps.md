# Per-nutrient parameter gaps

What the engine cannot compute from the workbooks we hold, established by an
exhaustive audit: all 11 distinct workbooks (33 uploads deduplicated by
content hash), all five PDFs, the four CSV result files, the four WhatsApp
images, and the raw OOXML of the masters — hidden sheets, defined names,
inline strings, drawings and embedded parts.

Audit date: 2026-09-08.

## The finding

**The `P1 Nutrients 81` sheet we hold is the uncalibrated version of the
table.** Two of its columns are shipped at their documented placeholder
values, and five columns the engine needs are absent entirely.

The workbook says so itself. `P1 Parameters 134+`, row 120:

| | |
|---|---|
| Symbol | `F_max,i` |
| Full name | Maximum absorbed fraction |
| Description | "Hard upper bound on the fraction of ingested amount that can enter the modeled absorbed pool" |
| Range | `0 < F_max <= 1` |
| Weight | **Critical** |
| Calibration method | **"Nutrient-specific literature; default 1.0 until calibrated"** |

Read directly from the workbook, `F_max` is **`1` for all 81 nutrients** —
the entire column is the uncalibrated default. That is not a plausible
physiological table: iron's maximum absorbed fraction is roughly 0.15,
calcium's roughly 0.3. `V_f` is likewise `50 dL` for 80 of the 81 rows (the
exception is water, at 500).

## The proof that calibrated values exist

The TwinAPI workbook, sheet `11 Worked Trace`, section B, headed "TRACE
PARAMETERS — swap any real nutrient's row to trace it the same way". Its own
preamble: *"Every number is computed, not illustrative."* Its source cell for
the absorption row cites this very sheet: "A4 bounded fraction · **P1
Nutrients 80 (v39s) / 81 (v39sEng)**".

| Parameter | Vitamin C | Magnesium | Ours |
|---|---|---|---|
| Dose (mg) | 180 | 120 | — |
| Gamma w / k1 / λ1 | 0.7 / 2.0 / 1/25 | 0.4 / 2.0 / 1/40 | k matches; λ differs |
| **F_max** | **0.90** | **0.45** | **1.0 / 1.0** |
| **F_base** | **0.75** | **0.30** | absent |
| **Km** | **200** | **250** | absent |
| Gastric T50 / kappa | 75 / 1.3 | 95 / 1.1 | absent |
| Half-life (days) | 0.25 | 1.0 | 0.5 / 1.0 |
| **V1 / V2 (dL)** | **32 / 60** | **40 / 140** | 50 / — |
| **Q / CL (dL/min)** | **0.35 / 0.30** | **0.20 / 0.12** | absent |
| F_abs (computed) | 0.652 | 0.259 | — |

Not one value matches ours except the gamma shape `k`. Our `F_max` is 1.0
where the trace says 0.90 and 0.45; our `V_f` is 50 dL where the trace says
32 and 40; our vitamin C half-life is 0.5 d where the trace says 0.25.

Two independent corroborations:

* `P1 Bariatric Module` (column "F_bio Base") and `P1 GLP-1 Module` (column
  "F_base") give baseline bioavailabilities for 18 nutrients — iron 0.15,
  calcium 0.30, zinc 0.30, vitamin E 0.30, copper 0.35, magnesium 0.40,
  B12 0.50, vitamin D3 0.50, vitamin K 0.50, folate 0.50, vitamin A 0.70,
  selenium 0.80, potassium 0.90, protein 0.90, thiamine 0.90, leucine 0.90,
  carbohydrate 0.95, fat 0.95. The 14 that appear in both sheets agree
  exactly. Every one is below 1.0.
* `layer_b_results.csv` carries `CL_total` and `k_el` for seven nutrients,
  constant across all 128 timesteps, so they are parameters rather than
  state. The half-lives they imply — iron 60 d, vitamin D 15 d, B12 180 d,
  calcium 0.8 d, protein 0.25 d, vitamin C 0.4 d, zinc 5 d — are clean
  literature figures, and only iron matches any column we hold.

A calibrated parameter set exists, has been used to compute a published
verification trace, and has been run end to end through Layers A–D.

## The gaps, with their parameter-registry rows

All from `P1 Parameters 134+`.

| # | Symbol | Layer | Eq | Units | Range | Weight | State in our copy |
|---|---|---|---|---|---|---|---|
| 120 | `F_max,i` | A | A4 | — | 0 < F ≤ 1 | Critical | **present but stubbed to 1.0 on all 81** |
| 14 | `F_base,i` | A | A5 | — | 0.01–1.0 | Critical | absent (18 recoverable) |
| 15 | `K_m,i` | A | A5 | mg | 10–5000 | Critical | absent |
| 25 | `V_f,i` | B | B2,B3 | L | 1–50 | Critical | **present but stubbed to 50 dL on 80/81** |
| 29 | `V_s,i` | B | B3 | L | 5–200 | High | absent |
| 37 | `f_unbound,i` | B | B5–B7 | — | 0.01–1.0 | Critical | absent |
| 41 | `CL_int,i` | B | B6 | mL/min | 0–5000 | High | absent |

`Q_liver` (#40) is **not** a gap: one physiological quantity with a published
formula — "allometric CO = 6.5*(BW/70)^0.75 L/min (ICRP Pub 89 2003);
Q_H = 0.260*CO" — already implemented in `sahacore/engine/pharmacokinetics.py`.

The two stubbed columns are the more dangerous half of this list, because
they are present. Code reading them gets a number and no warning.

### Consequence for our own tests

Validation gate C2 ("Monte-Carlo doses from 0 to 5x K_m. Pass: F_abs <= F_max
in 100% of draws") currently draws `F_max` from the registry, where it is
1.0 for every nutrient. `F_abs` is bounded by 1 by construction, so the gate
passes trivially. It is not wrong, but it is not yet testing what it is meant
to test, and it will only become a real bound once calibrated `F_max` values
arrive. Flagged rather than quietly relied on.

## What is NOT missing

Three items previously carried on the gap list do not belong there.

**Cluster damage thresholds.** `damage_registry_canonical` carries `eta_hi`
and `eta_lo` on **108 / 108** rows and `theta_hi` / `theta_lo` on **92 / 108**,
plus `tau_damage_days`, `tau_heal_days` and `weight_pct` on all 108. Only 16
rows lack thresholds:

* **C7**: `b2_mg`, `b6_mg`, `b9_ug`, `b12_ug`, `choline_mg`,
  `aa_methionine_mg`, `aa_glycine_mg`
* **C9**: `b6_mg`, `b9_ug`, `b12_ug`, `vit_d_iu`, `iron_mg`, `magnesium_mg`,
  `omega3_dha_g`, `aa_tryptophan_mg`, `aa_tyrosine_mg`

**`V_s` as a structural prior.** `P1 Scoring Alerts` row 132 states
"V_f=50dL, V_s=500dL are POPULATION-AVERAGE STRUCTURAL PRIORS, not
personalized values", adapted by the filter through allometric scaling.
A universal 500 dL default therefore exists. It is still worth asking for
per-nutrient values, since the trace gives 60 and 140 dL for vitamin C and
magnesium — an order of magnitude below the structural prior — but the
engine is not blocked without them.

**`Q_liver`.** As above: formula, not a table.

## What the search ruled out

So that this is not re-litigated:

* **No sheet is missing from the master.** `01_IMPORT_MANIFEST` lists exactly
  205 sheets; the workbook contains exactly 205; the two sets match with zero
  difference in either direction.
* **`v39sEng` adds nothing.** It is identical to `v39sEng2` across all 204
  shared sheets, cell dimensions included, differing only by the added
  `★ v39w Signal Patch`.
* **No hidden content.** Neither master has a hidden or very-hidden sheet, a
  defined name, or an embedded object. `sharedStrings.xml` is empty because
  the workbooks use inline strings; a full-text scan of the raw worksheet XML
  found no per-nutrient value for any missing parameter.
* **The five previously unopened workbooks** (the `v39sEng` master and the
  Twin / Atlas / Pulse / Plan variants distinct from their `...API`
  counterparts, plus the v31 input-signals file) contain only the formulas
  that consume these parameters, never a per-nutrient value.
* **The PDFs and the WhatsApp images** are product and UI material — the four
  images are SahaTwin, Pulse, Atlas and Plan screen mockups.
* **A scan for any table keyed by nutrient** across all ~470 sheets found 26
  sheets mentioning 20 or more distinct nutrients. Each was opened. The only
  per-nutrient parameter tables are `P1 Nutrients 81`,
  `★ Nutrient Class Registry` (class A–E and observation anchor — real data
  we have not yet loaded), `P1 Clusters 81x12` (the weight matrix we hold as
  `nutrient_cluster_weights`) and `★ Damage Registry — Canonical`.

## Note on an earlier wrong conclusion

An intermediate pass in this audit concluded that nothing had been removed,
reading `04 Engine Binding` row 20's `D20=P1 Nutrients 80 | E20=P1 Nutrients
81` as a rename between two masters rather than a removal. The rename reading
of that particular row is correct — the sheet's header does say
`D4=WHERE in v39s`, `E4=WHERE in v39sEng` — but the conclusion drawn from it
was not. `F_max = 1` on all 81 rows, against a registry that calls that value
"default 1.0 until calibrated", settles the question independently of how any
citation is read.

## Consequence for the build

`05 Build Flow & Deploy` phase 1 is "Registries + parameters + nutrients (the
data spine)". The parameters half cannot be completed from what we hold.
Layers A–D are implemented and pass their equation tests, but they are
running on placeholder ceilings and volumes. Structure is unblocked;
calibration is not.
