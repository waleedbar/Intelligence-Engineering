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

## Final mechanical verification

Run against all 12 distinct workbooks, searching every cell of every sheet.
Recorded here so the request to Dr. Ali rests on counts, not on recollection.

**Is the `F_max` column really all 1.0?** Every sheet in the corpus whose name
mentions "Nutrient" was checked for an `F_max` column. Exactly one has one:

    P1 Nutrients 81 -> F_max at row 4 -> 81 numeric values, distinct = {1}

No other sheet in any workbook carries an `F_max` column at all.

**Are the five parameters really absent?** Every cell mentioning each one, in
every workbook, classified:

| Parameter | Label cells found | What they are |
|---|---|---|
| `F_base` | 18 | 4 definition/FK rows, 1 citation, 1 trace (2 nutrients), 2 module tables (18 nutrients). No 81-row column. |
| `K_m` | 31 | QSSA enzyme Km in µM and MM-repair Km — different quantities — plus the definition row and the FK reference. No per-nutrient absorption Km. |
| `V_s` | 10 unique | All definition or description rows (`P1 DataMap` B34, `P1 Parameters 134+` F34, `P1 MC Engine` B19, `O·O1 Anthropometrics` D11, `P1 Scoring Alerts` C103, `P1 Onboarding` D155). No column. |
| `f_u_ref` | 12 unique | The personalisation formula `f_u = f_u_ref * (1 - 0.1*max(BMI-25,0)/25)` in `O·O1 Anthropometrics` E17 and `P1 Onboarding` E161, whose own input cell reads "f_u_ref **per nutrient**". No table of f_u_ref. |
| `CL_int` | **2** | Both the same definition row, `P1 Parameters 134+` C46. Nothing else in the entire corpus. |
| `w_k^fix` | **2** | Both the same cell, `P1 Core Equations` F37, a formula reference. No table of the 12 weights. |

(Counts double where two workbooks are byte-identical masters; unique counts
are given where that matters.)

**Are the 16 blank thresholds our loader's fault?** No. Read directly from
`★ Damage Registry — Canonical`: 108 data rows, of which 16 carry a literal
em-dash `—` in both `θ_hi` and `θ_lo`. The loader reproduces the workbook
faithfully.

**Scope of the claim.** This verifies the files we were given. It cannot
verify what exists elsewhere — and the Worked Trace and the Layer A–D CSVs
are evidence that a calibrated set does exist somewhere. That is precisely
what the request asks for.

## What we got wrong (2026-09-09 review)

Challenged to re-examine rather than re-confirm, two claims in this document
did not survive. Recorded because a gap list is only useful if it is trusted.

### V_f and V_s are NOT missing, and V_f is NOT stubbed

This document previously called `V_f = 50 dL` a placeholder and `V_s` absent.
Both are wrong. `O·O1 Anthropometrics` rows O1.1 and O1.2 define them as
**per-person** quantities computed at onboarding:

    O1.1  V_f = V_ref   * (BW/70)^0.75    V_ref   = 15 L
    O1.2  V_s = V_s_ref * (BW/70)^0.85    V_s_ref = 30 L

with the note, verbatim: *"V_ref=15L — GENERIC PRIOR ONLY, not a universal
physiological plasma volume. Apparent volume is compound-specific: use
per-nutrient V_f,i **where characterised**."*

"Where characterised" is the design saying, in its own words, that
per-nutrient volumes are an optional refinement over a body-weight prior —
not a table whose absence is a defect. `sahacore/engine/pharmacokinetics.py`
already implements both formulas with the v39l F-AX defaults, so this was
never a gap. Removed from the request.

A genuine question does survive here, and it is a different one: `V_f` has
**three** irreconcilable references — 50 dL (`P1 Nutrients 81` column O),
35 dL at 70 kg (`P1 DataMap` row 33, `0.05 × weight_kg × 10`), and 150 dL at
70 kg (`O1.1`, 15 L). A 4x spread across three sheets deserves a ruling. That
is now what the message asks about, instead of asking for a table.

### F_max = 1.0 was overstated

The finding is real — `P1 Parameters 134+` row 120 gives the calibration
method as "default 1.0 until calibrated", and all 81 rows sit at 1 — but the
consequence claimed here was too strong.

In A4, `F_abs = F_max·σ[logit(F_base/F_max) − log1p(q/Km) + …]`. With
`F_max = 1` the ceiling simply never binds and the absorbed fraction is
driven by `F_base` and the modifiers; at zero dose with no modifiers
`F_abs → F_base`, which is the correct limit. So an uncalibrated `F_max`
costs a **safety margin** — nothing stops the modifiers pushing iron toward
implausible absorption — rather than producing a wrong central estimate.

The genuinely blocking pair is `F_base` and `K_m`, which are absent. The
message now leads with those and asks about `F_max` as a confirmation.

### What survived the challenge

The core claim, re-tested rather than restated. The Worked Trace's parameters
were fed into our own A4 implementation with every modifier set to zero:

| | trace F_base / Km | our A4 output | trace's stated F_abs |
|---|---|---|---|
| Vitamin C | 0.75 / 200 | **0.652174** | 0.652 |
| Magnesium | 0.30 / 250 | **0.258621** | 0.259 |

Six-decimal agreement from the trace's own numbers through the canonical
equation. Those are calibrated values, not illustrations — and they are not
in any table we hold.

## 2026-09-09: the rulings master arrived, and it settles the question

`10_01_26_SahaPlusAI_MASTER_Claude_Sol_Kimi_v39k.xlsx` — **244 sheets** — is
the "rulings master" the four product workbooks cite in their ANCHORS tables
as `v39s.xlsx (245 sheets)`. It contains **62 sheets absent from the build
master**, including the four this document had listed as missing
(`★ v35.9 Rulings D01-D13`, `★ v35.9 Definitions`,
`★ v35.9 Ledger & M5 Calibration`, `★ D-01 CORRECTED SYS`) and the
`P1 Nutrients 80` sheet the Worked Trace cites as its source.

### The "removed columns" theory is disproven

`P1 Nutrients 80` in v39k has the **identical 21 columns** as
`P1 Nutrients 81` in the build master:

    # · ID · Name · Category · Unit · γ_k · γ_θ · λ · κ_fast · κ_slow ·
    w_fast · T½_fast · T½_slow · V_f · State Semantics · Canonical State
    Unit · F_max · s_hi · s_lo · Evidence Prior

and the same values: **`F_max = 1` on all 81 rows**, `V_f = 50 dL` on 80 of
81. No `F_base`, no `K_m`, no `V_s`, no `Q`, no `CL`.

So nothing was stripped between the rulings master and the build handoff.
The table has always had this shape. Earlier entries in this document
inferred a removal; that inference was wrong and is retracted.

### Scanning the 62 new sheets

Every occurrence of the five missing parameters across the sheets unique to
v39k:

| Parameter | Hits | What they are |
|---|---|---|
| `F_base` | 9 | The A4 formula, the `D5 · Parameter Registry` definition row, and a GLP-1 route label. No values. |
| `K_m` | 44 | The QSSA CBS constant (4000 µM), the 15 pathway Vm/Km pairs (which we already hold and which match exactly), and definitions. No per-nutrient absorption Km. |
| `CL_int` | 2 | Both definitions — `D1 · Core Equations` and `D5 · Parameter Registry`. |
| `f_u_ref` | 7 | Definitions in `P1 Variables 208+` and `D5 · Parameter Registry`. |
| `w_k^fix` | **0** | Absent entirely. |

`v39guide.docx` (89,000 characters of narrative) contains no `F_base`,
`F_max`, `K_m`, `CL_int`, `f_unbound` or `w_k` value either — its only `Km`
references are the CBS constant and the pathway table.

### Conclusion

Across **449 sheets in two masters**, plus a 4-page guide, five product
workbooks, a signal database, five PDFs and four CSVs, these values appear
**only as definitions and formulas, never as data**:

* `F_base,i` — 18 of 81 recoverable from the Bariatric and GLP-1 module
  tables; the other 63 have never been authored
* `K_m,i` — 0 of 81
* `f_u_ref,i` — 0 of 81
* `CL_int,i` — 0 of 81
* `w_k^fix` — 0 of 12

They were **never written**, not removed. That is a materially different
message to send: it is a request for a decision, not for a lost file.

The Worked Trace's numbers (vitamin C F_base 0.75 / Km 200; magnesium 0.30 /
250) remain the only concrete values anywhere, and `18_GAPS` GAP015 rules on
that sheet directly: *"Worked trace is static: workbook has zero formulas
even though it says every number is computed and reproducible … do not treat
this sheet alone as validation."* They reproduce the sheet's own F_abs
through our A4 to six decimals, so someone computed them — but they are two
nutrients, not a registry.

### What v39k does give us

Genuinely new, and worth loading:

* `★ v35.9 Rulings D01-D13` — the founder rulings, including D-01, the
  C-namespace / O-namespace split that `18_GAPS` GAP025/GAP026 depend on
* `★ v35.9 Ledger & M5 Calibration` — the `adaptation_ledger` table schema
  (append-only, RLS-scoped, `engine_internal` holds before/after values while
  `client_render` exposes only the type) and the M5 weight calibration
  protocol with safe initial values
* `★ v35.9 Definitions`, `★ D-01 CORRECTED SYS`
* `D1 · Core Equations` … `D15 · API & DB Schema` — a fifteen-sheet
  machine-level reference series
* `★ v37.1 Replay Contract`, `★ v38 Live Verification Lab`,
  `★ v38 Param Addendum`, `★ State Migration 208→219`, and the v34–v39
  adjudication trail

## 2026-09-09: seven more parameters the registry does not hold

Found while closing FK coverage by loading `EQ · Canonical Build Rows`. This
section is a different kind of finding from the ones above: not a per-nutrient
column that was never filled in, but a *symbol an equation consumes that the
192-row registry does not carry under that equation's layer at all*.

They surfaced because the matcher now refuses to resolve a token to a
parameter of another layer. Eleven input tokens spell a registry symbol
without being one; `engine_internal.withheld_input_tokens` lists them and
`tests/test_eq_build_rows.py::test_the_tokens_that_look_like_parameters_and_are_not_are_named`
pins every one by (equation, token).

Seven of them are the substantive findings:

| Equation | Token | Needed for | Nearest registry symbol | Why it is not the same |
|---|---|---|---|---|
| C-004, C-005, K3-FIX-03 | `ρ` | persistence decay in `Z_hi,k,n+1 = ρ_hi Z_hi,k,n + …` | #108 `rho`, Layer H | #108 is the ADMM penalty parameter |
| C-004, C-005 | `g` | forcing gain in the same recursion | — | no `g` in the registry |
| D-001 | `a_k` | score logistic slope | — | no `a_k` in the registry |
| D-001 | `b_k` | score logistic intercept | #93 `b_k (F2)`, Layer F | #93 is the cause-specific bias of a Layer F sub-network |
| K3-FIX-01 | `α` | scarring rate (`alpha_scar`) | #73 `alpha (UKF)`, #102 `alpha (UCB)` | UKF sigma-point spread and UCB exploration constant |
| K3-FIX-01 | `β` | autophagy rate (`beta_autophagy`) | #75 `beta (UKF)`, #98 `beta_jk` | same |
| K3-FIX-04 | `δ` | Hawkes decay, off `M-PARAM Registry` | #16 `delta_ij`, Layer A | co-nutrient absorption interaction coefficient |

Two of these are **not** new gaps once the workbook is read carefully, and
neither is bridged in code, because the correspondence is a
reparameterisation rather than a spelling — writing it into the loader would
be exactly the invention this build refuses:

* **C-004/C-005's `ρ` and `g`.** The registry states the same recursion in
  exact-discretisation form: #125 `k_Z,k` (damage decay constant) and #126
  `g_Z(k,dt)` (exact forcing multiplier), both C2,C3. `ρ` is a function of
  `k_Z,k` and the step; it is not another name for it. Dr. Ali should confirm
  the intended mapping.
* **D-001's `a_k` and `b_k`.** D1 states the same logistic as #58 `beta_k`
  (steepness) and #59 `mu_k` (midpoint), so `a_k = β_k` and `b_k = −β_k μ_k`.
  Both #58 and #59 are already in this document's gap list and in
  `build_parameter_registry.DELIBERATELY_UNRESOLVED` — no values were ever
  authored for them either way.

`K3-FIX-01`'s `α`/`β` are the same two rates already recorded above as the
`missing_fk` pair `(K3-FIX-01, alpha_scar)` and `(K3-FIX-01, beta_autophagy)`
— the `M-PARAM Registry` ships `max_alpha_beta_ratio` and `bound_gamma_r`,
the ratio and its guard, never the rates. This is a second, independent
confirmation of that gap from a different sheet.

`K3-FIX-04`'s `δ` is the Hawkes decay. It is worth naming separately because
it is the *third* time this token has tried to resolve to #16 `delta_ij`: an
unscoped alias table did it once in the FK loader, a reviewer caught it, and
the Greek spelling in the build sheet did it again. It is now blocked by the
layer rule as well as by the alias scoping.

### What to ask for

Adding to the request in "Consequence for the build" above:

* the persistence pair for C2/C3 — either `ρ_hi/ρ_lo` and `g_hi/g_lo`
  directly, or confirmation that `k_Z,k` and `g_Z(k,dt)` are the intended
  form and the conversion to use
* the score logistic's `a_k` and `b_k` for the 12 clusters — or `beta_k` and
  `mu_k`, which are the same two numbers in the other parameterisation
* the Hawkes `δ` (and `μ`, `ν`) for `K3-FIX-04`, which live in the
  unimported `K3 Fixes` sheet

## 2026-09-09: four more, from loading the safety registries

`missing_fk` went from 4 to 8 when `MERGE·VETO Drug-Nutrient 339` and
`Action_Space` loaded. The count did not regress — it became truthful.

`H-001/H-006` (Layer H's conservative-decision objective) declares those two
sheets authoritative for its keys. While neither was imported, its keys were
`NOT_LOADED` — unfinished importing on our side, which this build deliberately
does not report as a missing FK. Both are loaded now, so the keys neither
table carries are reported for what they are:

| Key | Meaning in H1/H6 | Where it is not |
|---|---|---|
| `lambda_b` | budget penalty weight | not in VETO, Action_Space, or the parameter registry |
| `z_B` | budget-bound z-score | same |
| `z_R` | risk-bound z-score | same |
| `baseline_delta` | baseline offset for the decision comparison | same |

Its two siblings **do** resolve: `lambda_u` is #131 (physiological uncertainty
penalty) and `lambda_r` is #132 (risk upper-bound penalty), both Layer H, both
`RESOLVED_ELSEWHERE` against the parameter registry. So the objective is
half-parameterised: the penalties on uncertainty and risk exist, the budget
penalty and the two bounds that make them comparable do not.

### One naming trap worth recording

The FK sheet names `VETO Canonical 339` as the authority. That sheet is **not**
the registry. Its own third row:

> REFERENCE ONLY — the sheet name is historical and does not guarantee the
> active registry row count. Production/build loaders MUST use MERGE·VETO
> Drug-Nutrient 339, the active registry with 339 unique canonical rule_ids.

It holds 266 rows. A loader that matched the authority column against sheet
names would have imported a truncated safety table under the right-looking
name. The redirect is recorded in `build_eq_param_fk.LOADED_REGISTRIES` and
pinned by `test_the_veto_authority_name_resolves_to_the_registry_not_the_stub_sheet`.

### What to ask for

Adding to the earlier requests:

* `lambda_b`, `z_B`, `z_R` and `baseline_delta` for H1/H6 — or confirmation
  that they live in a sheet not yet named as authoritative for that row

## 2026-09-09: a correction — six of them were never missing

`★ Param Registry +20` loaded, and six parameters this document reported as
absent from the workbook turned out to be in it.

| Reported here as | Actually in `★ Param Registry +20` as | Value |
|---|---|---|
| `alpha_scar` — MISSING_FK on K3-FIX-01 | `α_scar,k` Scarring rate | 0.001–0.01 /day |
| `beta_autophagy` — MISSING_FK on K3-FIX-01 | `β_autophagy,k` Autophagy clearance | 1e-4–1e-3 /day |
| `δ` — OTHER_LAYER on K3-FIX-04 | `δ_i` Hawkes jump | 0.3/event |
| `μ` — "to ask for" | `μ_base` Hawkes baseline | 0.05 |
| `ν` — "to ask for" | `ν_D` Hawkes decay | 0.15 |
| (not previously listed) | `κ_D` Hawkes reversion | 0.1 |

`missing_fk` fell from 8 to 6. Layer M's rate parameters and the whole Hawkes
row now resolve.

### What went wrong in the reasoning

The claim made here was **"the workbook does not contain it."** The evidence
supported only **"the sheets this build has imported do not contain it."**
Those are different statements, and the second is the only one that was ever
checkable while the import was unfinished.

`01_IMPORT_MANIFEST` lists `★ Param Registry +20` at order 21 with import
status YES and backend Yes. It was in the plan the whole time. This build had
imported 13 of the manifest's 124 backend sheets when the "18 missing
parameters" list was written.

A regex sweep of the sheets still unimported finds candidate locations for
**seventeen of the eighteen**:

* `F_base` — GLP-1 and Bariatric Onboarding Contracts, `Module · Bariatric (priors)`
* `T50`, `kappa`, `epsilon_base`, `lambda_b`, `alpha_scar`, `beta_autophagy` — `★ Equation Backbone`
* `a_k`/`b_k`, `ρ`/`g` — `P1 DataMap`
* `f_unbound` — `O·O1 Anthropometrics`, `O·Engine Connections`, `P1 Core Equations`
* `lam_rep` — `O · Onboarding Canonical`, `09 Glossary & Symbols`
* `R_min` — `Alert Architecture`
* `z_B`/`z_R` — `P2 Validation Protocol`
* `CL`, `Q` — `GLP-1 Onboarding Contract`, `K3 · Mechanistic Modules`

A regex hit is not a value — `F_base` in an onboarding contract may be a
modifier rule rather than a per-nutrient table. But it is enough to make the
"missing" list unsafe to send to anyone until the manifest is finished.

### The rule this build now follows

**Nothing is reported missing from the workbook until every sheet
`01_IMPORT_MANIFEST` marks `import=YES, backend=Yes` has been imported.**
Until then the honest status is NOT_LOADED, which the FK resolver already
distinguishes from MISSING_FK and which
`test_a_missing_fk_is_only_claimed_when_every_authority_is_loaded` already
enforces per row. The failure here was in this document, which made a claim
the resolver itself never made.

The sections above are left as written, with this correction appended rather
than folded in, so the reasoning error stays visible.

## Incomplete rows found while importing, for the workbook's author

Not parameter gaps — rows the source sheets leave unfinished. Each is loaded
as-is and reported by a view, rather than dropped or filled in.

| Sheet | Row | What is missing | View |
|---|---|---|---|
| `★ Supplement Registry` | 20, Betaine (trimethylglycine / TMG) | effect cap, evidence position, cluster permission — the name is the only cell filled | `engine_internal.supplement_incomplete` |

Betaine matters a little more than a blank row usually would: it is a
methyl-donor with a canonical nutrient counterpart (`betaine_mg` is not in the
81, but choline is, and the two are metabolically coupled), and the registry's
whole purpose is to stop a supplement inheriting a dietary weight it has not
earned. Without a cap, Betaine has no stated position at all.

## 2026-09-09: '★ Equation Backbone' settles three more

`missing_fk` 6 → 5, and two entries elsewhere in this document are wrong.

### `CL` is not a parameter

It was listed as a missing FK on B-002/B-003 with the note "the registry
defines `CL_int,i` and `Q_liver` — different quantities. There is no symbol
for either of these." The first half was right; the conclusion was not.
Backbone B4:

    CL = CL_renal + CL_hepatic
    B5:  CL_renal   = GFR·f_filtered·(1−f_reabsorbed)     ← from lab eGFR
    B6:  CL_hepatic = Q_H·E_H  (well-stirred; E_H embeds f_u)

No registry was ever going to carry it. It now reports `COMPUTED`, a status
added for exactly this: the key is real, the equation that produces it is
named, and there is nothing to ask anyone for.

`Q` in the same row is deliberately **not** reclassified. B2 and B3 consume
it and no backbone row defines it, so it stays a missing FK. A "computed"
bucket that absorbed both would turn a real gap into a reassuring word.

### `ρ` and `g` are computed, exactly as hypothesised

The earlier section "seven more parameters the registry does not hold" listed
C-004/C-005's `ρ` and `g`, hypothesised they derive from #125 `k_Z,k`, and
deliberately refused to encode that — "a reparameterisation rather than a
spelling", pending confirmation. Backbone C2 gives it verbatim:

    rho = exp(-k·dt);  g = -expm1(-k·dt)/k

So they are not gaps. The refusal to guess was right, and the confirmation
came from finishing the import rather than from asking.

### Running total of the correction

The original list was **18 parameters to request from the workbook's author**.
After importing three sheets the manifest had always listed:

| | |
|---|---|
| found with values (`★ Param Registry +20`) | 6 |
| shown to be computed (`★ Equation Backbone`) | 3 — `CL`, `ρ`, `g` |
| **still genuinely open** | **9** |

Nine of eighteen, and the import is at 21 of 124 backend sheets. The list
should not be sent until it is finished.

## Source rows that are incomplete or inconsistent, as found

A running list for the workbook's author. None of these is a parameter gap;
each is a cell or a count the source leaves unfinished. All are loaded as-is
and surfaced by a view rather than dropped or filled in.

| Sheet | Where | What | View |
|---|---|---|---|
| `★ Supplement Registry` | row 20, Betaine (TMG) | name only — no effect cap, evidence position or cluster permission | `supplement_incomplete` |
| `P1 DataMap` | row 8 | "Gamma shape parameter", Layer A, equation A1, symbol cell empty (almost certainly `k`) | `datamap_unnamed_variable` |
| `P1 DataMap` | section A banner | claims "158+ ENGINE VARIABLES" over 96 rows | — |
| `P1 DataMap` | section B banner | claims "105 ONBOARDING FIELDS" over 63 rows | — |
| `P1 DataMap` | sheet title | claims "227 items" over 212 data rows in five sections | — |

Some DataMap rows do name two variables in one cell ("k₁, λ₁"), which
accounts for part of the count gap but not the whole of it. Both numbers are
recorded — what the banner claims and what the sheet holds — rather than one
being chosen.

`P1 DataMap` sections C, D and E are deliberately not imported. D restates
the action space and E restates the equation backbone's inputs and outputs,
both of which are loaded from their own sheets; a second copy is a second
thing to keep in agreement. C is integration metadata with no consumer yet.

## 2026-09-09: a CRITICAL message that refers the reader to nobody

Found by loading `MERGE·VETO FDA Messages` and joining it to the 339-rule
library, which had been carrying a `message_id` pointing at nothing.

**`MSG-CRITICAL-STABLE`**, in full:

> Safety first — with {medication}, keeping your {nutrient} intake steady day
> to day helps things stay consistent — aim for a similar amount rather than
> big swings.

CTA: *Learn more*. No prescriber. No pharmacist. The other six CRITICAL
templates all hand off to one.

Two rules render it, both CRITICAL:

| Rule | Drug | Nutrient | The rule's own `action` column |
|---|---|---|---|
| VETO-DN-0265 | Insulin (any) | Carbohydrate intake | STABLE PATTERN — **discuss with prescriber** |
| VETO-DN-0267 | Sulfonylureas | Carbohydrate intake | STABLE PATTERN — **discuss with prescriber** |

So the rule mandates a referral and the template that renders it drops one —
on the two interactions where a carbohydrate swing is a hypoglycaemia risk.

This build does not rewrite it. Regulated wording is not an engineering
decision. It is loaded as written, reported by
`engine_internal.critical_message_without_referral`, asserted in CI to be
exactly one row, and pinned by name in the extractor so a second such
template stops the build.

**For Dr. Ali:** should `MSG-CRITICAL-STABLE` carry the prescriber referral
its two rules already specify?

## 2026-09-09: two sheets disagree about the organ namespace

`★ SYS Registry (organs)` is marked AUTHORITATIVE and states a binding rule:

> **Why NOT O1–O12** — the O-namespace is occupied by onboarding.
> **Binding rule** — any NEW organ reference must use a SYS code.

`REG · Organ×Pathway Long` uses `O1`–`O12` for its 12 organ nodes.

It predates the ruling — the SYS sheet says *new* references — so this is not
a violation to fix in the loader. But the collision is live: `O1` is the
cardiovascular organ node in one sheet and the anthropometrics module in
`O·O1 Anthropometrics`, which Layer 0 will read. Both are loaded as written,
and a test asserts the disagreement still exists so it cannot be resolved by
an accidental edit in either direction.

**For Dr. Ali:** should `REG · Organ×Pathway Long` be regenerated with SYS
codes, or is the O-namespace grandfathered there?

### And one place where two sheets agree, which is worth as much

`REG · Organ×Pathway Long` holds 48 links over 12 organs and **13** pathways,
D1 to D13. There are no organ weights for D14 or D15.

`00_ENGINEER_START` gate `d14_d15_fail_closed` reads GLOBAL_MODIFIER_PENDING:
*"No invented organ weights. Fail closed until evidence-locked mapping is
signed off."*

The gate came from one sheet and the weights from another, imported days
apart. They agree. A CHECK constraint now stops a D14 or D15 weight being
inserted at all, and the extractor refuses to write one.

### Targets with no official basis

`★ Target Registry (versioned)` carries 6 rows. Two — CoQ10 and betaine —
have no Institute of Medicine DRI or UL at all. The sheet's own note:

> literature-based wellness proxies for adequacy display only, NOT clinical
> dosing. This matters for FDA General Wellness positioning — they must
> render as adequacy %, never as a treatment dose.

`engine_internal.targets_without_official_basis` is the list any rendering
code must consult.

## 2026-09-09: the verification lab runs Layer M outside its own admitted region

`Live Verification Lab` (manifest order 5) is the sheet that calls itself
*"the load-bearing numbers, re-derived by live formulas in front of you"*.
Six labs, each a worked example with a PASS/FAIL verdict. Every one of them
reproduces here to machine precision — `tests/test_verification_labs.py`
recomputes each published quantity in Python from the sheet's own inputs.

One of them is exercised at a point its sibling sheet forbids.

LAB 4 and LAB 6 both run the Layer-M scar update at:

| input | value |
|---|---|
| `γ_scar` | 0.69 |
| `α_scar` | 0.004 /day |
| `β_autophagy` | 0.001 /day |
| `θ_elastic` | 50 |

So `r = α/β = 4` and the destabilising group `γ·r = 2.76`.

`★ Scarring Bistability Guard` (manifest order 17) caps `γ·r` per cluster and
says of the cap, in its section 3 heading, *"assert these at build time"*.
Against 2.76:

- **eleven of the twelve caps are below it.** C7 admits 0.87, C9 0.97, C5 1.08.
- **only C6 admits it**, at 4.86.
- `γ_scar = 0.69` **is not a value the registry assigns to any cluster** —
  `M-PARAM Registry` uses 0.6 and 1.2, and nothing else.
- `θ_elastic = 50` **is C5's value**, and C5's cap is 1.08, the second
  tightest in the table.

Both labs return PASS, and both are right to. LM-P01 asks only whether
`0 ≤ S_next ≤ 1`, and LM-P02 whether two half-steps equal one full step; the
demo satisfies both. The gap is that **neither lab evaluates the bistability
margin at all**. LAB 6's own `Parameter rules` row lists what it checks —

> S∈[0,1]; theta>0; alpha>=0; beta>0; gamma>=0; dt>=0; Vmax_base>=0

— and the group `γ·r` is not among them.

**Not corrected here.** Amending a published worked example is the workbook
owner's call, and the labs' arithmetic is not in question. What this build
does instead:

- `engine_internal.bistability_margin(γ, α, β)` implements PG-1 —
  `B_k = cap_k / (γ_k · r_k)`, reported per cluster as the sheet asks, with
  PG-3's `B_k < 1.25` proximity flag alongside the pass.
- `engine_internal.demo_point_outside_admitted_region` is the eleven rows,
  asserted in CI.
- A CHECK constraint refuses any `gamma_scar` outside {0.6, 1.2} in the caps
  table, so a third value has to be a deliberate edit.

**For Dr. Ali:** should the demo point move onto an admitted cluster, or is
0.69 there deliberately to exercise the formula away from the calibrated
values?

## 2026-09-09: LAB 3 calls a gain 'operating' that three sources call zero

Same sheet, separate finding. LAB 3 row 100 is labelled:

> η_net (operating gain)

and holds **0.05**. Three places in the workbook say otherwise:

| source | says |
|---|---|
| `00_ENGINEER_START` row 27, gate `eta_net_zero` | `Cluster coupling — OFF (ETA=0)` |
| `P1 Parameters 134+` #138 `eta_net` | *"production value is exactly 0"*; range *"0 production; any non-zero value is shadow/data-derived"* |
| `P1 Parameters 134+` #141 `rho_Gamma` | *"matrix diagnostic; **do not derive an eta ceiling from 1/rho alone**"* |

And rows 118–119 of the lab do exactly what #141 rules out by name: they
compute `stability bound 1/ρ̂ = 1.1543` and then a `margin ×0.5 (recommended
ceiling)` of **0.577**. Parameter #141's reason is stated too — the spectral
radius *"describes Γ but is not a stability governor for the complete
physiological dynamics"*.

The candidate Γ supports that reading. Of its 144 cells, **19** are non-zero;
C10 and C12 drive nothing, and C3, C4, C7, C8 and C11 are never driven. It is
a sketch of a few proposed pathways, not a coupling model of the twelve.

The lab's arithmetic is sound and its verdict (`η_net·ρ̂ < 1`) is true. The
disagreement is over what the number *means* — a shadow value being exercised,
or an operating one. Read as operating, an engineer building from this sheet
would ship cluster coupling switched on at a gain the invariant says is off,
with a ceiling derived the way #141 forbids.

**This build follows the invariant and the registry: `η_net` stays 0.**
`engine_internal.eta_net_disagreement` records all three sides in one row, and
CI asserts it returns exactly one. `tests/test_verification_labs.py` pins both
positions, and says in its docstring that if the lab is ever corrected the
test should be deleted rather than loosened.

**For Dr. Ali:** is 0.05 in LAB 3 a shadow-mode value that should be labelled
as one, and should rows 118–119 carry #141's caveat?

## And a corroboration worth as much

The lab's spectral radius is a 20-iteration estimate, `ρ̂ = 0.86630573`. Run
the power iteration to convergence and the true radius is `0.86631229` — a
difference of **6.6e-6**, comfortably inside the lab's own `|ρ̂ − 0.8663| <
1e-3` gate, which both values pass. The sheet's estimate is honest and its
tolerance is the right size for it.

Likewise the twelve caps: `★ Scarring Bistability Guard` states them twice —
once in section 3 and once in a section 8 *"INDEPENDENT VERIFICATION
RECEIPT"* — and `M-PARAM Registry`, a different sheet imported days earlier,
carries the same twelve rows again. All three agree on `γ_scar`, the cap, the
max `α/β` ratio, `τ_dam`, `τ_heal` and `V`. Both stated identities hold to the
source's own two-decimal precision: `cap = γ_scar × max(α/β)` and
`V = 1.443 · τ_dam/τ_heal`, worst deviation 0.0068.

## 2026-09-09: the test battery answers two of the questions above

`★ Validation Test Battery` (manifest order 14) turned out to hold answers to
questions this file was about to put to Dr. Ali. Importing it first was the
right order, and the reason is recorded here as much as the result.

### It confirms η_net = 0, and rules out the 1/ρ ceiling a fourth time

Test **C8**, BLOCKING, opens its method with *"With η=0 as production
baseline"* and sets the criterion as *"η remains 0 unless held-out
calibration improves and max Re eig(J_full)…"*. Test **S7**, BLOCKING, comes
at it from the other side: *"Refit with η_net = 0 against the fitted value.
Coupling is retained only if held-out calibration IMPROVES."*

Neither mentions the spectral radius. The battery's stability criterion is
the **full Jacobian**, exactly as parameter #141 says. So `Live Verification
Lab` rows 118–119 — `stability bound 1/ρ̂` and a `margin ×0.5 (recommended
ceiling)` of 0.577 — are not shorthand for the real gate; they are a
different, looser one that the battery does not recognise.

**The question to Dr. Ali narrows accordingly.** It is no longer *"is 0.05 a
shadow value?"* — the workbook answers that in four places. It is: *should
LAB 3 rows 118–119 carry C8's caveat, so an engineer reading the lab does not
implement the 1/ρ ceiling?*

### It already specifies the bistability guard as a blocking test

Test **C17**, BLOCKING: *"For each cluster compute B_k = cap_k/(γ_k·r_k) and
the posterior violation probability p_viol,k… B_k ≥ 1 AND p_viol,k < 0.01 for
all 12 clusters. A point estimate passing while p_viol ≥ 0.01 [is not a
pass]."* That is PG-2 from `★ Scarring Bistability Guard`, which names C17 as
its placement — the two sheets corroborate each other exactly.

The battery also carries **C14** (the point check), **C15** (exactly one
equilibrium per forcing level), **C16** (θ_elastic ratified per cluster,
42–70 AU) and **S11** (recovery symmetry). So the guard is not an isolated
worry; it is a five-test admission block.

`bistability_margin()` implements the B_k half. The `p_viol` half needs a
posterior over (γ, r) that Phase 2's cohort fit has not produced — which the
guard sheet says itself. Recorded as PARTIAL, not ENFORCED.

### Two of this repo's own tests were looser than the battery requires

Found by importing the criteria and diffing them against what the repo
actually asserts:

| test | battery says | this repo said | now |
|---|---|---|---|
| **I7** 81×12 column simplex | *"All twelve columns sum to 100.0 exactly"* | `abs=1e-2` | exact equality |
| **I8** REG column simplex | *"All twelve columns sum to 1.000000"* | `abs=1e-4` | `abs=1e-9` |

The data met the tighter criteria all along — the damage columns each sum to
the float `100.0` and the nutrient-cluster columns to within 4e-16. But a
tolerance of 1e-2 would have accepted a column that was half a percent wrong,
which is a real weight error hiding under a passing test.

## 2026-09-09: what C1 actually costs, and why the demo grid cannot meet it

Test **C1**, BLOCKING: *"Integrate the normalised kernel over 0→∞
numerically. |∫h − 1| < 1e-6 for all 81 nutrients."*

`Live Verification Lab` LAB 1 integrates the same kernel and gets
**0.99480379**, a residual of **5.2e-3** — four orders of magnitude above
C1. The lab's own gate is `< 1e-2` and its note calls it the *"workbook
demo-grid gate"*, so the sheet knows. But the size of the gap is worth
recording, because the reason is not obvious.

**The kernel is fine.** Refining the grid converges on 1:

| dt (min) | T (min) | ∫h·dt | \|1−I\| | C1 |
|---|---|---|---|---|
| 10 | 720 | 0.9948037921 | 5.20e-03 | fail |
| 1 | 4320 | 0.9999025558 | 9.74e-05 | fail |
| 0.1 | 20000 | 0.9999970215 | 2.98e-06 | fail |
| 0.01 | 40000 | 0.9999999061 | 9.39e-08 | **pass** |

**The cost is the quadrature order, and it is not the one you would assume.**
Measured convergence of the trapezoid rule on each component:

| component | shape k | observed order |
|---|---|---|
| fast | 2.5 | 2.50 |
| slow | **1.5** | **1.50** |
| (control) | 3.0 | 4.00 |

The order equals `k`. A gamma pdf carries `t^(k-1)` at the origin: for
k = 1.5 that is `t^0.5`, whose derivative is unbounded at t = 0, and the
endpoint singularity — not the smooth interior — sets the rate. So the
mixture converges at **O(dt^1.5)**, not the O(dt²) trapezoid gives on a
smooth integrand, and reaching 1e-6 needs dt ≈ 0.01 min.

**Consequences for whoever implements C1:**

1. Sizing the grid from an assumed O(dt²) will miss the target by orders of
   magnitude. Halving dt buys a factor of 2.8, not 4.
2. Any nutrient whose shape parameter is nearer 1 is worse still — at k = 1.1
   the rate is O(dt^1.1) and 1e-6 is out of reach by refinement alone.
3. The fix is not a finer grid. Each component of the mixture is a normalised
   pdf, so the analytic integral is `w + (1−w) = 1` by construction; C1's
   real content is that the **implementation's** normalisation constant
   (the division by Γ(k)) and its `w ∈ [0,1]` are right. A singularity-aware
   quadrature, or integrating each component analytically, meets the
   criterion without a four-million-point grid.

This is why C1 is recorded as PARTIAL rather than ENFORCED: this build
verifies the kernel against the workbook's published integral, on the
workbook's grid, and that grid does not meet the workbook's own criterion.
Nothing here needs Dr. Ali's decision — it is an implementation note for the
engineer who builds Layer A, which is why it is written down now rather than
discovered then.

## 2026-09-09: the outcome log is a Phase-1 obligation written on a Phase-7 sheet

`★ Scoped Builds — LTMLE Bandit` (manifest order 6) specifies Layers G and H,
which are build-flow phases 7 and 8. Nothing on it can be built for a long
time. It was imported anyway, for one sentence:

> **SHARED PREREQUISITES (block BOTH items)**
> **1 · Historical outcome log** — *"Both learn from a per-user longitudinal
> record the ONLINE engine **must already be writing**"*

and its restatement as the last of the eight open founder decisions:

> **8 · BOTH** — *"confirm the historical outcome log is being written"*
> *"Prerequisite — nothing offline can start without it"*

**"Already writing" is a claim about today, not about phase 7.** A log that
begins when Layer G begins gives Layer G nothing to learn from, and the
months that were not recorded cannot be recovered by any amount of later
engineering.

### What this build actually writes

`★ Build Guide Python` step 1 lists the ledger's contents:

> raw_events, event_quality, controls_u, measurements_y, bitemporal
> effective_at/knowledge_at, checkpoints, lineage hashes and replay-job keys

This build has **all of them and nothing else** — it matches its own step
exactly. And it still does not satisfy the prerequisite: there is no per-user
outcome panel, and no served-event log.

### A second sheet names the missing tables

Battery test **I12**, BLOCKING:

> `served_action_event` / `served_warning_event` payload hash and `served_at`
> remain unchanged; revised decision is a new linked version.

and **LM-P09** *"Served-event immutability"* asserts over the same thing. So
the served-event log is not this build's idea — it is what a BLOCKING
acceptance test is written against. It is absent from build-guide step 1 and
absent from this repo.

### Not fixed here, and why

Inventing `served_action_event` from a one-line assertion would be designing
schema the workbook has not specified — column names, what a payload hash
covers, what "linked version" means. The status is recorded as `MISSING` in
`engine_internal.scoped_build_prerequisite`, CI asserts
`unmet_scoped_prerequisites` returns exactly one row, and
`tests/test_scoped_builds.py` pins both halves: that step 1's tables exist,
and that the served-event tables do not.

**For Dr. Ali — and this one has a clock on it, unlike the others:**

> Should the ledger start writing the outcome panel and the served-event log
> now, while it is young? Every month it does not is a month Layers G and H
> can never learn from. If yes, which sheet specifies their columns — I did
> not find one beyond I12's assertion.

### The other two shared prerequisites

| # | prerequisite | status |
|---|---|---|
| 1 | Historical outcome log | **MISSING** |
| 2 | T-1 firewall — *"Both train server-side… never raw clinical"* | **IN_PLACE** (`tests/test_firewall.py`) |
| 3 | Shadow mode first — *"Compute + log, do NOT serve"* | **NOT_APPLICABLE_YET** — nothing is served |

### And eight decisions that block the code, recorded verbatim

The sheet marks them *"required BEFORE code starts"*. They are loaded into
`engine_internal.founder_decision` unanswered, because answering one would be
inventing product policy. Decision 5 — the bandit's reward proxy — carries
the sheet's own note calling it *"the single biggest decision"*, stated twice:
once in the table and once as an inline warning on item 2.

## 2026-09-09: Layer 0 is 12/14 buildable — the 15→12 bridge is not in the workbook

`O · Onboarding Canonical` (manifest 128) is `★ Build Guide Python` step 3
written out: fourteen steps, ONB-001..ONB-014, each with its equation, I/O,
parameter refs, QA, and the `sahacore.onboarding.*` function to write.

**Twelve can be written today. Two cannot**, and the reason is a missing
crosswalk rather than missing effort.

### The gap, precisely

`O·O11 Damage State Init` produces **fifteen** pathway warm-start values,
`ξ_path,p(t0) = ln(0.1 + composite_risk_p)` for p = 1..15. Every one of its
fifteen rows ends with the same instruction:

> `15→12 bridge → ξ_hi/ξ_lo; no direct x_hat slot`

and its header repeats it: *"Map the 15 pathway warm-start values through the
canonical 15→12 bridge, then initialize ξ_hi[163:174] and ξ_lo[175:186]"*.

The slots ONB-012 fills at 163–186 are **twelve clusters**. Between fifteen
pathways and twelve clusters sits a bridge that **five sheets name**:

| sheet | wording |
|---|---|
| `O·O11 Damage State Init` | "through the canonical 15→12 bridge" |
| `O·O12-O14 State Init` | "O11 + P1 Cluster Map 15-12" |
| `O·Engine Connections` r42 | "15 pathway ξ_path warm-start values → canonical 15→12 bridge" |
| `★ Build Map — concept to code` | "pass through the canonical 15→12 bridge before ξ_hi/ξ_lo initialization" |
| `M-MAP Integration` | "uses the existing 15->12 cluster map" |

### `P1 Cluster Map 15-12` is not that bridge

It is titled *"PHASE 1: 15 TVMCD Pathways mapped to 12 Clusters"* and its
first column header reads `Cluster`. Its contents are neither:

- **rows are `O1: Cardiovascular` … `O12: Reproductive`** — organ systems.
  Its own v35.9.3 banner says so: *"rows on this sheet describe ORGAN SYSTEMS
  and are keyed SYS1–SYS12 … They must never be referenced by a bare C-code —
  C1–C12 belong to physiological processes."*
- **columns are D1..D13** — thirteen pathways, not fifteen.
- its 48 non-zero weights are **already in this build**, loaded from
  `REG · Organ×Pathway Long` as `engine_internal.organ_pathway_weight`, which
  is what that data actually is.

### The search that establishes the absence

Not "I did not find it" — every sheet was scanned. A pathway→cluster bridge
must carry twelve cluster ids and fifteen pathway ids in one place:

```
sheets with ≥10 cluster ids AND ≥10 pathway ids:  0
sheets with  ≥6 cluster ids AND  ≥6 pathway ids:  7
```

and all seven of those are equation sheets where `C1..C8` are **Layer C
equation numbers**, not clusters — a third meaning of `C<n>` in this workbook,
alongside process clusters and the SYS/O organ collision already reported.

### What is corroborated, and worth as much

- **ONB-012's slot layout matches `state_vector_219.json` exactly**, block for
  block, across all 219 slots — two sheets imported days apart agreeing on the
  engine's own state.
- **`Z1..Z15` in `O·O11` are `D1..D15` elsewhere** — all fifteen names line up
  one for one (`Z1`/`D1` Glycation/AGE … `Z15`/`D15` VitD Insufficiency). The
  two namespaces are one set under two spellings.
- **The damage slots hold ξ, not Z.** The canonical sheet writes them `Z_hi`/
  `Z_lo`; the registry names them `xi_hi`/`xi_lo`, unit `log(AU)`. Battery
  test **C3** (BLOCKING, *"Damage positivity (log-coordinates)"*, criterion
  `Z(t) = exp(ξ) − ε ≥ 0`) is what rests on the distinction — writing Z into a
  ξ slot passes a length check and breaks positivity everywhere downstream.
  Pinned in `tests/test_onboarding_canonical.py`.

### For Dr. Ali

> Where is the canonical 15→12 pathway-to-cluster bridge? `P1 Cluster Map
> 15-12` is named as it in five places but holds a 12-organ × 13-pathway
> matrix, and its own banner says its rows are organ systems. Without it
> ONB-011's fifteen warm-start values cannot reach the twelve ξ slots, and
> Layer 0 stops at 12 of 14 modules.

Note this is **not** the same as the O1–O12 namespace question reported
earlier — that one is about naming. This one is a missing artefact.

## 2026-09-10: ONB-001 is implemented — and BSA is specified where it is not defined

`O·O1 Anthropometrics` (manifest 71) is the authority for the first of Layer
0's fourteen modules, and the first sheet in this build whose contents are
**executed** rather than checked. Ten equations, twelve sourced parameters,
and `sahacore/onboarding/anthropometrics.py` implementing them.

### BSA is declared by two sheets and defined by neither authority

`O · Onboarding Canonical` and `EQ · Canonical Build Rows` both give ONB-001
as including, in identical words:

> `BSA=sqrt(height_cm*weight_kg/3600)`

and `P1 DataMap` row 109 says height is *"Used for BMI, BSA calculations"*.

`O·O1 Anthropometrics` — which both of those rows name as the authority —
has equations **O1.1 through O1.10 and no BSA**. Nor does any other O1
equation consume BSA: `V_f` and `V_s` scale on body weight, not surface area.
A workbook-wide search for `BSA` returns exactly those three mentions and
nothing else.

So ONB-001 is specified to produce a quantity that **nothing in the workbook
reads**. Implemented anyway — the formula is Mosteller's and is given
explicitly and identically in two places, so there is nothing to guess — and
recorded in `engine_internal.onboarding_declared_elsewhere` with
`absent_from_authority_sheet = true` and `consumed_by = {}`.

**For Dr. Ali:** is BSA meant to be consumed by a later layer, or is it a
leftover from an earlier version of ONB-001?

### The values are stored as text, again

Every value in O1's PARAMETERS table is stored in the workbook as a **string**
— `'15'`, not `15`. This is the same defect that once loaded 73 of 192 rows
into the parameter registry and passed silently. The extractor converts and
refuses anything that will not parse, so a value cannot reach a physiological
calculation as a string.

### What is a parameter and what is part of the equation

The package's standing rule is that no physiological constant is written into
a `.py`. Applying it needed a distinction the sheet itself draws:

- **In the PARAMETERS table** — `V_ref`, `V_s_ref`, the allometric exponents,
  `k_IR`, the WHtR cutoff, the four waist thresholds, the neck threshold, the
  BMI cutoff. Each has a **cited source** (IDF/WHO harmonized 2009, Ashwell
  et al. 2012, West et al. 1997, Anderson & Holford 2008, STOP-Bang). All
  twelve are read from the registry.
- **Written into the formulas** — the 70 kg allometric reference, Mifflin-St
  Jeor's `10 / 6.25 / 5 / +5 / −161`, the `0.3` in O1.7, the `0.1` and `25`
  in O1.8, O1.9's `0.45 / 0.30 / 0.20 / 0.05`, Mosteller's `3600`. Changing
  one of these is changing the equation, not retuning a parameter, so they
  are transcribed with it.

A test enforces the first half by reading the module's AST and requiring each
of the twelve keys to be dereferenced off a parameter object. It deliberately
does **not** scan for numeric literals: the module has many that belong there,
and a check that could not tell the two kinds apart would be either wrong or
ignored.

### Two cautions kept because they change what a number means

The sheet says of `V_ref = 15 L`:

> GENERIC PRIOR ONLY, not a universal physiological plasma volume

and of `V_s_ref = 30 L`:

> GENERIC PRIOR ONLY (see V_ref note). Use per-nutrient V_s,i where
> characterised.

Both functions therefore take an optional reference so a caller with a
characterised nutrient can supply it, and the extractor refuses to write if
that wording ever leaves the sheet.

### And one place the sheet corroborates itself

O1.7's declared range is `1.0-8.5`. `CRP_mult = 1 + 0.3·max(BMI−25, 0)`
reaches exactly **8.5** at BMI = 50 — which is the top of O1.3's own declared
BMI range of `15-50`. The two ranges were derived together rather than
written independently, and that is pinned.

## 2026-09-10: ONB-002 — PA_benefit has two definitions and neither resolves

`O·O2 MVPA Prior` (manifest 72) is ONB-002's authority. Eight equations;
**six are implemented, two cannot be.**

### The conflict

| source | formula for `PA_benefit` |
|---|---|
| `O·O2 MVPA Prior` O2.4 — **the authority** | `PA_benefit = 100 * (1 − HR_Arem)` |
| `O · Onboarding Canonical` ONB-002 | `PA_benefit = 100*(1−exp(−MET_min_week/K_PA))` |
| `EQ · Canonical Build Rows` ONB-002 | *identical to the row above* |

These are **different functions**. One is an epidemiological hazard ratio
"anchored at 150-300 min/wk zone"; the other is a saturating exponential in
MET-minutes. Neither reduces to the other.

**And neither is computable:**

- `HR_Arem` is described on the authority sheet and **never given** — no
  formula, no table, no parameter row. Searched the whole workbook: it
  appears only inside O2.4 and in the copy of O2.4 on `P1 Onboarding`.
- `K_PA` appears in **exactly two cells** — the two consolidated rows above —
  and in neither the 192-parameter registry nor the +20 extension.

O2.5 (`rho_modified`) then needs O2.4's output **and** `rho_pop`, "population
mean repair", which appears twice in the workbook, both times inside O2.5
itself, and is in neither registry.

Not implemented. `PA_benefit` feeds Layer C's repair rate through
`O·Engine Connections` r17, so a guessed dose-response curve would not stay
contained. Recorded as `computable = false` with the missing symbol named, and
CI asserts `onboarding_o2_gaps` returns exactly two rows.

**For Dr. Ali:** which definition of `PA_benefit` is current, and where is
its constant — the Arem hazard-ratio curve, or `K_PA`?

## 2026-09-10: `P1 Activities 50` promises twelve cluster columns and has six

Its banner reads:

> 50-Activity Catalog — MET Values + **12-Cluster** Impact Weights

and its section heading *"COMPLETE ACTIVITY CATALOG WITH CLUSTER IMPACTS"*.

The columns are `C1 Membrane`, `C2 Glucose`, `C3 Protein`, `C4 Electro`,
`C5 Inflamm`, `C6 Oxidative` — and then the row ends. Not blank cells: **no
columns at all**. Every one of the 51 rows stops at column 15.

So an activity's impact is computable for half the clusters. Loaded as it
stands, with `clusters_declared = 12` and `clusters_present = 6` recorded.
**Not padded with zeros** — a zero would read as "this activity does not
affect methylation", which is a physiological claim the sheet does not make.

### And six intensity labels disagree with the Compendium

The sheet cites *"2024 Compendium of Physical Activities (Herrmann et al.
2024)"* as the source of its MET values. Six rows carry an intensity label
outside the Compendium's own bands:

| activity | MET | sheet | Compendium |
|---|---|---|---|
| `vacuum`, `pilates`, `tai_chi` | 3.0 | Light | Moderate |
| `standing_work` | 3.3 | Light | Moderate |
| `cycle_stat` | 3.5 | Light | Moderate |
| `tennis` | 6.0 | Moderate | Vigorous |

**Recorded, not enforced.** The sheet cites the Compendium for its MET
*values* and never says its *labels* follow the Compendium's bands, so a
check that failed on this would be imposing a rule the source does not claim.
My first version of that check did exactly that and was wrong; it now tests
only that the bands are internally ordered.

It still matters: O2.6 splits activity by these labels while weighting with
**4.5 and 7.5** — the midpoints of the Compendium's bands, not of this
catalogue's, whose Light band runs to 3.5 and whose Vigorous band runs to
16.8.

**For Dr. Ali:** are the six missing cluster columns pending, and are the
intensity labels meant to follow the Compendium's boundaries?

## 2026-09-10: an audit of my own work — three misses, and a mechanical fix

Asked to check the recent work before continuing, rather than summarise it.
Three real defects, one of them substantive.

### 1. I reported ONB-001 as complete when two of O1.9's three inputs are undefined

`O1.9 mu_centadip = 0.45*e_waist + 0.30*e_WHtR + 0.20*e_BMI + 0.05*I(neck>40cm)`

`e_waist` is defined by O1.10. **`e_WHtR` and `e_BMI` are not defined
anywhere.** They appear in exactly two cells in the whole workbook — inside
O1.9 and inside its duplicate on `P1 Onboarding` — described as *"normalized
[0,1] indices"* with no formula, no thresholds and no parameter row.

The code was not wrong: `central_adiposity_composite` takes them as
arguments, so nothing was invented. **The reporting was wrong.** ONB-001 was
committed as ten equations implemented, and two thirds of one of them cannot
be computed from the workbook.

`f_u_ref` in O1.8 is the same story — two mentions, both inside O1.8. Note
that parameter **#37 `f_unbound,i` declares exactly the same range, 0.01-1.0**.
That is suggestive and it is *not* evidence: the spellings differ and the
81-nutrient registry has no unbound-fraction column. Left unbridged, in the
style of `build_eq_param_fk.ALIASES`, which requires a declared reason.

### The pattern, and the fix

These are not isolated. A symbol that appears **exactly twice** — once on its
own sheet, once on `P1 Onboarding`, which duplicates the O-sheets — is a
symbol nothing defines:

| symbol | used by | mentions |
|---|---|---|
| `e_WHtR` | O1.9 | 2 |
| `e_BMI` | O1.9 | 2 |
| `f_u_ref` | O1.8 | 2 |
| `HR_Arem` | O2.4 | 2 |
| `rho_pop` | O2.5 | 2 |
| `K_PA` | consolidated ONB-002 | 2 |
| `CRP_ref` | O11 Z3 | 2 |

I caught three of these by reading and walked past four. Reading does not
scale to twelve more O-sheets, and an undefined symbol reaching code becomes
a guess.

So `sahacore/data/onboarding_symbols.py` now does it mechanically: for every
imported onboarding equation it pulls the symbols off the right-hand side and
accounts for each against the parameters, the other equations' left-hand
sides, and the declared user inputs. Anything left over is a hole in the
source. `tests/test_onboarding_symbols_resolve.py` **fails on a symbol that
has not been reported**, so finding one means reading the sheet and writing
down what is missing.

Its tokeniser is itself tested against the three things this workbook does
that break a naive parser: version tags (`[v39l F-DM]`), units glued to
numbers (`40cm` must not yield `cm`), and a second definition on a second
line. Getting any of those wrong makes the guard vacuous.

### 2. An unused import

`import math` in `mvpa_prior.py`, left over from a draft. Removed.

### 3. Nothing checked that a built module is the one the contract names

`O · Onboarding Canonical` names a `sahacore.onboarding.*` function per step.
Two are built and both match — but nothing verified it, so a module written
under a different name would have satisfied no contract while looking done.
Now tested.

### And a standing item, now guarded

Six JSON seeds have no loader and no version: `arthur_signals_raw`,
`arthur_signals_validated`, `damage_clusters_12`, `lifestyle_states_24`,
`mechanistic_states_9`, `tvmcd_pathways_15`. Left over from before this
build's conventions. They are pinned by a test, so a **seventh** — a new
extractor shipped without its loader — fails.

My first version of that test listed `activities_50.json` among them. It is
not an orphan: `load_onboarding_o2` reads it. The test caught my own wrong
assumption before it was committed.

### For Dr. Ali — one question, seven symbols

> Seven symbols are used in onboarding equations and defined nowhere in the
> workbook: `e_WHtR`, `e_BMI` (O1.9), `f_u_ref` (O1.8), `HR_Arem` (O2.4),
> `rho_pop` (O2.5), `K_PA` (consolidated ONB-002), `CRP_ref` (O11 Z3). Each
> appears exactly twice — on its own sheet and in the `P1 Onboarding` copy.
> Where are their definitions?

## 2026-09-10: CORRECTION — the 15→12 map exists. I reported it as missing.

On 2026-09-09 this file said, under *"Layer 0 is 12/14 buildable — the 15→12
bridge is not in the workbook"*, that the pathway-to-cluster map five sheets
name does not exist. **That was wrong, and it was committed and pushed.**

It is in **`TVMCD · 15 Pathways Build`** (manifest order 131), in a column
called `Cluster outputs`, giving two or three clusters for every one of the
fifteen pathways:

```
D01 → C02,C12,C10      D06 → C02,C09,C12      D11 → C10,C04
D02 → C06,C05,C09      D07 → C12,C05,C09      D12 → C06,C03,C12
D03 → C05,C12,C08      D08 → C09,C05,C08      D13 → C07,C12,C09
D04 → C06,C09,C12      D09 → C04,C12          D14 → C08,C05,C07
D05 → C07,C06,C09      D10 → C03,C10          D15 → C10,C05,C11
```

### How the search missed it — and it is subtler than it sounds

The search matched `C1..C12` and `D1..D15` and required **ten or more
distinct ids of each**. This sheet writes them zero-padded: `C02`, `D01`.

But **not all of them are padded** — `C10`, `C11`, `C12` and `D10`–`D15` need
no padding. So the sheet scored **3 cluster ids and 6 pathway ids**, and was
passed over for being *under the threshold*, not for scoring nothing.

That is the part worth remembering. A pattern that had returned **0** would
have looked broken and invited a second look. One that returns **3** looks
like a sheet that merely mentions a few clusters in passing. **A partial
match is more dangerous than no match.**

Re-run with padding allowed, it is the **only** sheet of the 205 carrying ten
or more of each. So the earlier conclusion *"there is exactly one candidate"*
was right; the identification was wrong.

`tests/test_tvmcd_pathways.py` pins both patterns and both scores, so the
lesson is executable rather than a note.

### What the map gives — and what still blocks ONB-011/ONB-012

It gives **membership**. It does not give:

1. **Weights.** `C12` is fed by eight pathways, `C11` by one. Turning fifteen
   pathway values into twelve cluster values needs a combination rule and the
   sheet states none — so an unweighted mean would not be a neutral default,
   it would be a chosen one.
2. **C01.** No pathway lists `C01` Membrane Integrity as an output at all.
   One of the twelve clusters would warm-start from nothing. Not zero-filled:
   a zero is a claim.
3. **The hi/lo split.** ONB-012 fills `ξ_hi[163:174]` **and** `ξ_lo[175:186]`
   — twenty-four slots from fifteen values. Nothing says how.

So ONB-011 and ONB-012 stay blocked, but the question changes from *"where is
the bridge?"* to three specific and much more answerable ones.

### And a reading that cuts the other way

The sheet's `Initialization` column says: *"from O·O11 warm-start or zero with
prior covariance for D03"*. Each pathway carries its **own** state
(`logZ_inflam`, `logZ_AGE`, …) warm-started from O11. So `Cluster outputs`
may describe a **runtime aggregation** of pathway states, not a warm-start
remapping at all. Both readings fit what is written; the sheet does not
settle it. That is now the first thing to ask.

### For Dr. Ali — replacing the earlier question

> `TVMCD · 15 Pathways Build` maps each pathway to two or three clusters.
> (a) Is that the "canonical 15→12 bridge" ONB-011 means, or a runtime
> aggregation — the Initialization column suggests O11 warm-starts the
> *pathway* states directly? (b) What weights combine several pathways into
> one cluster? (c) What feeds C01 Membrane Integrity, which no pathway lists?
> (d) How do fifteen values split into ξ_hi and ξ_lo?

## 2026-09-10: every extractor was reading part of its table

Setting out to build ONB-003, the first thing `O·O3 Sleep Deficit` showed was
a column called **Engine Target** — where each equation's output goes:
*"Layer C: Z3 Inflammation rate"*, *"Layer B (B1): V_f"*. Then a check: does
O1 have it too?

It does. So does O2. **I had imported both without it.**

### Why it was invisible

Every extractor's header check verified the labels it was **given** and said
nothing about the columns it was **not**. A sheet with seven columns and an
extractor declaring six agree perfectly, and the seventh is lost in silence.

An audit across all 25 extractors found five sheets losing **sixteen columns**:

| sheet | columns dropped |
|---|---|
| `O·O1 Anthropometrics` | Engine Target |
| `O·O2 MVPA Prior` | Engine Target |
| `TVMCD · 15 Pathways Build` | Uncertainty treatment, Validation scenario |
| `Action_Space` — info actions | VOI score, State/output affected, **Safety/VETO**, Expiration, Policy class, Exploration, State uncertainty, Evaluation |
| `Action_Space` — rollout phases | **Sample Threshold**, **Convergence Criterion**, Safety Notes |

None is decoration. `Engine Target` is the wiring from Layer 0 into the rest
of the engine. `Safety/VETO` is a safety position on every information
action. `Sample Threshold` and `Convergence Criterion` are what let a rollout
phase advance — a rollout schedule without them is a list of names.

The `TVMCD` one is the sharpest: **I wrote that extractor the same day**, with
a `check()` that refuses empty columns and a docstring calling the sheet a
*"complete server implementation table"* — while dropping two of its columns.

### The fix

`sahacore/data/sheet_header.py` — one `check_header` used by every extractor.
It verifies the declared labels **and** that nothing follows them. All 25
extractors now use it; four private copies and nine inline loops are gone.

`tests/test_extractors_take_whole_tables.py` makes it non-optional: an
extractor that declares a `HEADER_ROW` must import and call `check_header`,
and may not keep a private header check. It reads source rather than the
workbook, so it runs in CI, where the workbook is not.

**Its honest limit,** written into the module: the scan stops at the first
empty cell, because a table's columns are contiguous. A sheet that put a gap
and then more columns of the *same* table would still slip through. Scanning
a fixed distance instead was tried and reached into the wide numeric grids
that sit further along the same row in `Live Verification Lab`.

### `sql/035`, not an edit to `sql/032`

`sahacore.migrate` records a migration by **filename**. Editing an applied
one would change what a fresh build creates and leave every existing database
silently short of the column. Migrations are append-only, so the recovered
columns arrive by `ALTER TABLE` in a new file — which is also why the new
`safety_veto IS NOT NULL` constraint is added `NOT VALID`.

### What this says about the earlier misses

This is the third search-shaped failure in two days, and they rhyme:

1. `e_WHtR`, `e_BMI`, `f_u_ref` — read past because reading is not a search.
2. The 15→12 map — missed because the pattern scored it **3**, not 0.
3. Sixteen columns — missed because the check only looked where it was told.

Each time the tool answered exactly the question asked and the question was
too narrow. The fixes have the same shape too: make the check say what it
*cannot* see (`onboarding_symbols`), or refuse to pass when something is
present that was not declared (`sheet_header`).

---

## 2026-09-10: ONB-003 — O3 defines every symbol it uses, and disagrees with itself three ways

`O·O3 Sleep Deficit` is the first of the three O-sheets whose symbols all
resolve. `python -m sahacore.data.onboarding_symbols` now covers O1, O2 and
O3, and O3 adds nothing to the unresolved list — its one composite input,
`e_sleepqual`, is defined in O3.7's own Variables cell as `(5-quality)/4`,
which is exactly what O1.9 fails to do for `e_WHtR` and `e_BMI`. O3.6 also
carries its ordinal encoding inline rather than in a separate table, so the
module reads it instead of retyping it.

The sheet also has **no PARAMETERS table**. Every constant — the 7-hour
threshold, 0.081, 0.045, 0.18, the 7–9 hour window, O3.7's weights — lives
inside a formula. That is a difference in the source, not a relaxation of the
no-hardcoding rule: a value the sheet puts in a formula is part of the
formula, and it is transcribed with it.

What the sheet does not do is agree with itself. Three findings, none
corrected.

### 1. Two definitions of sleep deficit, and they are not the same function

| | O3.1 `SDS` | O3.5 `sleep_def` |
|---|---|---|
| formula | `(7 - sleep_hrs)/7 * quality_factor` | `0` if `7≤h≤9`; `min(1,(7-h)/2)`; `min(1,(h-9)/2)` |
| at 9 h | `-0.29 × quality_factor` | `0` |
| oversleeping | **negative** | positive |
| declared range | 0–1 | 0–1 |

SDS is signed and unclamped, so it breaks its own declared range above the
target. `sleep_def` is two-sided and clamped, and treats 7–9 hours as the
healthy window. Both are implemented under their own names —
`sleep_deficit_score` and `sleep_deficit_index` — so a caller cannot take one
for the other.

### 2. O3.1's quality weighting reaches none of its declared consumers

This is the one that costs something. O3.1's Engine Target column reads
`O3.2, O3.3, O3.4, O11`. The first three are on this same sheet, and **not
one of them mentions SDS**. All three compute from
`deficit_hrs = max(0, 7 - sleep_hrs)` — the raw clock shortfall, with no
quality weighting whatsoever.

So two users who both sleep five hours, one rating their sleep 1/5 and the
other 5/5, get **identical** Z3 inflammation, Z6 insulin-resistance and Z10
sarcopenia modifiers. Their SDS values are `2/7` and `0` — the full range of
the score — and nothing on this sheet consumes the difference.

It compounds with the quality factor's own shape: `quality_factor =
1 - (rating-1)/4` is **zero** at rating 5, so `SDS = 0` for *any* sleep
duration a user rates 5/5. Two hours and eight hours both score zero.

Either O3.2–O3.4 should read SDS and do not, or O3.1's engine target names
consumers it does not have. Which of those is true decides whether sleep
quality affects Layer C at all. O11 is unimported and may yet be SDS's only
real consumer.

### 3. O3.7 mixes two badness indices with one goodness index

`mu_sleep = 0.5*sleep_def + 0.3*e_sleepqual + 0.2*e_sched`

| term | best case | worst case | direction |
|---|---|---|---|
| `sleep_def` (O3.5) | 0.0 | 1.0 | high = worse |
| `e_sleepqual` | 0.0 | 1.0 | high = worse |
| `e_sched` (O3.6) | **1.0** | **0.0** | **high = better** |

O3.6 is `(consistency_score - 1)/3` over `Very Inconsistent=1 … Very
Consistent=4`, so a perfectly regular sleeper scores 1.0 on a term that is
added to two penalties. The best possible sleeper therefore scores **0.2**
and the worst **0.8**: the declared 0–1 range is unreachable at both ends,
and improving your schedule *raises* your sleep-badness prior.

Flipping the term would change what a Layer E state prior means, so it is
asserted rather than corrected — in `build_onboarding_o3.check()` and in
`test_o3_7_mixes_two_badness_indices_with_one_goodness_index`.

### How findings 2 and 3 were found

Neither came from reading the sheet. Both came from writing a test that had
to state what the best and worst cases were, and finding the arithmetic would
not produce them. That is the fourth time in three days that the check found
what the reading did not — and unlike the previous three, this one needed no
new tool, just a test that refused to be written vaguely.

### For Dr. Ali — three questions

1. **Should O3.2, O3.3 and O3.4 read SDS or `deficit_hrs`?** As written they
   read `deficit_hrs`, and sleep *quality* reaches Layer C nowhere. If that
   is intended, O3.1's engine target should not name them.
2. **Which shortfall measure is canonical above 9 hours** — SDS's negative
   value, or `sleep_def`'s zero?
3. **Is O3.6's polarity intended in O3.7?** As written, better schedule
   consistency increases `mu_sleep`.

---

## 2026-09-10: ONB-004 — the best-specified O-sheet, and a break it shares with two others

`O·O4 Stress Index` is the strongest of the four O-sheets imported so far.
Every symbol resolves. Every constant is stated. It carries three tables —
the PSS-10 instrument, nine equations, three interpretation bands — and it
makes claims that can be checked against each other, which none of O1, O2 or
O3 does.

### What it gets right, and what that made possible

**It states its reverse-scored items twice.** Once in a `Reverse?` column,
once inside O4.1's formula as `r_i' = 4-r_i for i in {4,5,7,8}`. Neither is
more authoritative, so the extractor holds them to each other and refuses to
import a sheet where they disagree. They agree, and they are the published
PSS-10's items 4, 5, 7 and 8 — which matters because the sheet's own header
reads **"CORRECTED: PSS-10, NOT PSS-4"**, so an earlier revision scored a
different instrument.

**Its bands corroborate its equations.** Two independent checks, both pass:

| the bands say | the equations say | at Θ_AL = 1 |
|---|---|---|
| High: "+40% damage sensitivity" | O4.5 `γ_cort = 1 + 0.4·Θ_AL` | +40% ✓ |
| Moderate: "−15% is the maximum at Θ_AL=1" | O4.9 `λ_rep_mod = 1 − 0.15·Θ_AL` | −15% ✓ |

and across the Moderate band's 14–26, O4.9 gives −5.25% to −9.75%, against
the sheet's stated "≈−5% to −10%".

**Its bands tile 0–40** with no gap and no overlap, so every possible PSS-10
total has exactly one stated meaning.

A sheet that agrees with itself in places that were written separately is
evidence its numbers were meant rather than typed. That is worth saying
plainly, because most of this document is the opposite.

### The finding: `p_stressprot` reaches nothing

O4.3 computes

    stress_idx_adj = max(0, stress_idx_raw − p_stressprot)
    where p_stressprot = 0.05 per practice (cap 0.20)

and its Engine Target names `O4.4, O4.5, O4.6, O4.7`. **None of the four
reads it.** O4.4 is `Θ_AL = PSS10/40` — recomputed from the total, not taken
from the adjusted index — and O4.5 through O4.9 all read `Θ_AL`.

So the credit a user earns for stress-management practices, worth up to 0.20
of a 0–1 scale, changes no modifier the engine uses. A user reporting four
practices gets identical cortisol, inflammation, glucose, CVD and repair
modifiers to one reporting none.

It is easy to miss because **O4.2 and O4.4 are the same function**:
`stress_idx_raw = PSS10/40` and `Θ_AL = PSS10/40`. `Θ_AL` reads as though it
descends from the stress index. It does not.

`stress_index_adjusted` is implemented and called by nothing, which is what
the sheet specifies. It is not wired into `allostatic_load` on this build's
initiative: that would move five downstream modifiers on an authority the
sheet does not give.

## The same break, three times — so it stopped being a reading problem

O3.1's quality weighting reached none of its declared consumers. O4.3's
stress credit reaches none of its declared consumers. Both were found by
hand, one per sheet, by writing a test that had to state a best and a worst
case and finding the arithmetic would not produce them.

Finding the second one the same way as the first is the signal. Ten O-sheets
remain, and an equation that computes something real and is read by nobody is
**invisible to every other check in this repo** — the symbols resolve, the
formula transcribes verbatim, the header matches, the loader loads.

So `sahacore.data.onboarding_symbols` now carries a second mechanical check,
`broken_routings`:

> An Engine Target cell that names other equations on the same sheet is a
> claim those equations consume this one's output. Each named consumer is
> checked for any symbol this equation defines. Targets naming a layer
> (`Layer C: Z3`) are off-sheet and not checked — nothing here can see
> Layer C.

### It immediately found a third, in a sheet imported two days ago

**O2.1** routes `MVPA_wk` to `O2.2, O2.3, O2.4`. The first two read it. O2.4
is `PA_benefit = 100·(1 − HR_Arem)` and does not.

This one is **not a separate defect** — it is the known `HR_Arem` hole seen
from the other side, and it is *evidence about that hole*. O2.4 describes
`HR_Arem` as coming from a "dose-response curve, Anchored at 150-300 min/wk
zone", and min/wk is exactly `MVPA_wk`'s unit. So the routing tells us the
missing curve is meant to be a function **of `MVPA_wk`**.

That identifies the missing curve's argument. It does not supply the curve.

### The pattern this makes four of

1. `e_WHtR`, `e_BMI`, `f_u_ref` — read past, because reading is not searching.
2. The 15→12 map — missed because the pattern scored it **3**, not 0.
3. Sixteen columns — missed because the check only looked where it was told.
4. Three dead routings — missed because nothing asked *"and does anyone read
   this?"*

Each time the tool answered exactly the question asked and the question was
too narrow. The fix has the same shape every time: make the check report what
is *unaccounted for*, rather than confirm what was declared.

### For Dr. Ali — three questions on O4

1. **Should O4.4 read `stress_idx_adj` instead of recomputing from PSS10?**
   As written, stress-management practices affect nothing. If that is
   intended, O4.3's engine target should not name O4.4–O4.7.
2. **Are O4.2 and O4.4 meant to be the same quantity?** They are identical
   formulas under two names with different engine targets.
3. **Is `HR_Arem` a function of `MVPA_wk`?** O2.1's routing and O2.4's
   "150-300 min/wk" both say so; the curve itself is still missing.

---

## 2026-09-10: the UI contract was manifest order 70, and I built four modules before it

`O·Step-by-Step Questions` is **manifest order 70**. O1 is 71, O2 is 72, O3
is 73, O4 is 74. I built all four before importing the sheet that says what
their inputs *are*.

Nothing failed, because every O-sheet names its own inputs in a Variables
column. What was missing was any way to **check** them: an O-module's inputs
could only be compared against the same O-sheet that declared them, which is
the sheet agreeing with itself.

The clearest symptom is in my own code. `onboarding_symbols.DECLARED_INPUTS`
is a hand-written set carrying this comment:

> Written by hand because "this is an answer the user gives" is not something
> a parser can tell from a name.

That was true only while this sheet was unimported. It states exactly that,
for every input, in a column called **Maps To**. 73 questions across 12
steps, each with its answer options, its variable, and which O-module
consumes it.

### What it corroborates

**The PSS-10 reverse set, a third time.** The workbook now states it in three
independently written places, and all three agree on items 4, 5, 7 and 8:

| # | where | how |
|---|---|---|
| 1 | `O·O4` `Reverse?` column | `YES` on four rows |
| 2 | `O·O4` O4.1's formula | `r_i' = 4-r_i for i in {4,5,7,8}` |
| 3 | Step 8 question text **and** Maps To | `...(REVERSE)` and `r4 → O4 (reverse)` |

That matters because O4's header reads "CORRECTED: PSS-10, NOT PSS-4". Three
agreeing statements is the evidence the correction landed everywhere.

**O4.3's cap is exactly the number of practices the UI offers.** O4.3 credits
0.05 per stress-management practice, capped at 0.20 — which is four. Step 8
offers four practices plus "None". So the cap is precisely reachable and
cannot be exceeded, and neither sheet mentions the other.

**O3.6's scale matches Step 9's options** — four ordered choices, scored 1 to
4. O3 abbreviates two labels ("Somewhat", "Fairly"); the UI writes them out.

### What it contradicts

#### 1. O5.5's "midpoints" are not the midpoints of the bands the UI offers

Step 3 asks "Daily sugary drink servings" with options `0 / 1-2 / 3-4 / 5+`.
O5.5's Variables cell reads `SSB_serv_day from Step 3 (midpoint: 0/0.5/1.75/3)`.

| band | true midpoint | sheet's "midpoint" |
|---|---|---|
| `0` | 0 | 0 ✓ |
| `1-2` | 1.5 | **0.5** |
| `3-4` | 3.5 | **1.75** |
| `5+` | open | 3 |

The sheet knows how to write a correct midpoint — **O5.2 does it exactly**,
for alcohol: bands `0 / 1-3 / 4-7 / 8+` with declared values `0 / 2 / 5.5 /
10`, and 2 and 5.5 are the true midpoints of `1-3` and `4-7`.

It changes a Layer C input. `e_SSB = min(1, SSB_serv_day/1.5)`:

| band | with the sheet's value | with the true midpoint |
|---|---|---|
| `1-2` | **0.333** | **1.0** (saturated) |
| `3-4` | 1.0 | 1.0 |

So a user answering "1–2 sugary drinks a day" is recorded at a third of
maximum glycation exposure rather than at maximum. Only that band's outcome
differs; `3-4` saturates either way.

#### 2. O5's five tobacco categories are not what the UI collects

O5.1 and O5.7 both map a single five-valued variable — `Never`,
`Former(>1yr)`, `Former(<1yr)`, `Occasional`, `Daily`. Step 10 asks **two**
questions:

- `smoke_status`: `Yes daily / Yes occasionally / No`
- `quit_time`: `Within last year / More than a year ago / Never`

Neither offers "Former". The five categories must be **derived** by joining
the two answers — "No" plus "Within last year" is presumably `Former(<1yr)` —
and **no sheet states the join rule**.

#### 3. `units_week` and `drinks_wk` are the same question under two names

Step 10 collects `drinks_wk` with bands `0 / 1-3 / 4-7 / 8+`. O5.2 encodes
`units_week` over exactly those bands. O5.4 and O5.6 then do arithmetic on
`drinks_wk`. The sheet never says they are the same quantity, but the UI
offers only one alcohol question, so they must be.

**That makes O5.6's male branch unreachable.** With `drinks_wk` taking O5.2's
midpoints, its maximum is 10:

    Female: e_alcohol = min(1, max(0, (drinks_wk − 7)/7))   → tops out at 0.43
    Male:   e_alcohol = min(1, max(0, (drinks_wk − 14)/14)) → is 0 for every answer

Both are declared `0-1`. A male cannot score above zero on hepatic-fibrosis
alcohol exposure under any answer the UI accepts, and a female cannot exceed
0.43.

#### 4. The sleep slider may not reach O3.5's upper branch

Step 9 collects sleep with a "Slider 0-8+ hours". O3.5 has a third branch for
`h > 9`. Whether it is reachable depends on what "8+" permits, which the
sheet does not say. Flagged, not assumed either way.

### The lesson, again, and it is the same one

I searched for Step 3's SSB answer labels expecting them to be absent — and
`O·Step-by-Step Questions` had them, along with the labels for every other
banded question in the workbook. The habit of *looking once more before
concluding absence* has now paid out four times.

The structural version of the same lesson: **I skipped manifest orders 69 and
70 and started the O-series at 71.** The manifest is the project's own build
order, and it put the UI contract before the modules that consume it for a
reason. Order 69 (`O·Overview`) is still unimported.

### For Dr. Ali — four questions on the UI contract

1. **Are O5.5's SSB values meant to be midpoints?** They are labelled as
   such and are not; O5.2's alcohol midpoints are exact.
2. **How do Step 10's two smoking questions become O5's five categories?**
   No sheet gives the rule.
3. **Are `units_week` and `drinks_wk` the same answer?** If so, O5.6's male
   branch is identically zero.
4. **Does the Step 9 sleep slider go above 9 hours?** If not, O3.5's upper
   branch is dead code.

---

## 2026-09-10: ONB-005 — the first sheet checked against the UI, and a sixth hole

`O·O5 Substance Exposure` (manifest 75) is the first O-sheet imported **after**
its own UI contract. Every earlier O-module's inputs could only be checked
against the same O-sheet that declared them, which is the sheet agreeing with
itself. Four of the five findings below exist only because that is no longer
true.

### What corroborates

**O5.2's alcohol midpoints are exact.** Step 10 offers `0 / 1-3 / 4-7 / 8+`
and O5.2 encodes `0 / 2 / 5.5 / 10`. 2 and 5.5 are the true midpoints of
`1-3` and `4-7`. This is the control for finding 1: the sheet demonstrably
knows how to write a midpoint.

**O5.3's ceiling matches its declared range.** `k_ox = λ_smoke · λ_alcohol`
tops out at 1.4 × 1.1 = 1.54, against a declared "1.0-1.5+".

### 1. O5.5's "midpoints" are not midpoints

Already recorded under the UI-contract import; now checked in code. Step 3's
bands are `0 / 1-2 / 3-4 / 5+`; O5.5 declares `0/0.5/1.75/3`; the true
midpoints are `0/1.5/3.5`. A user answering "1–2 sugary drinks a day" scores
`e_SSB = 0.333` instead of 1.0.

### 2. The five tobacco categories are not what the UI collects

O5.1 and O5.7 both map `Never / Former(>1yr) / Former(<1yr) / Occasional /
Daily`. Step 10 asks two questions — `smoke_status` (Yes daily / Yes
occasionally / No) and `quit_time` — and **neither offers "Former"**. The
five must be a join, and no sheet gives the rule.

### 3. O5.1 and O5.7 rank those five differently

| category | `pack_years` (O5.1) | `tobacco_idx` (O5.7) |
|---|---|---|
| Never | 0 | 0 |
| Former(>1yr) | 2 | 0.15 |
| Former(<1yr) | **5** | **0.35** |
| Occasional | **5** | **0.50** |
| Daily | 20 | 1.00 |

One answer, two indices, two orderings: `pack_years` ties a recent
ex-smoker with an occasional smoker, `tobacco_idx` does not. They feed
different Layer C targets, so both orderings are live.

### 4. O5.6's male branch is unreachable

`e_alcohol = min(1, max(0, (drinks_wk − T)/T))`, T = 7 female, 14 male. The
UI asks about alcohol once, so `drinks_wk` cannot exceed `units_week`'s
largest encoded value, **10**. A male therefore scores 0 on every answer the
interface accepts; a female tops out at 0.43. Both are declared `0-1`.

Implemented as written, with `drinks_wk` and `units_week` kept as **separate
arguments** so the non-bridge stays visible rather than baked in.

### 5. `sitting_hrs` — the hole only the UI contract could find

O2.8 is `eta_sed = I(sitting_hrs > 6) · 0.15`, and its Variables cell says
**"sitting_hrs from Step 2 UI"**. Step 2 does not collect it. It asks *"Hours
spent standing daily"* (`standing_hrs`, options `<1 hr / 2 hrs / 3 hrs / 5
hrs`) — a different quantity, since time not spent standing is not time spent
sitting.

Searched the whole workbook before concluding: `sitting_hrs` appears only on
`O·O2` and its duplicate on `P1 Onboarding`.

**But sitting time is real elsewhere in the engine** — state slot 185 is
"Kalman-smoothed sitting time", and `P1 DataMap` row 53 carries "Sedentary
time / Minutes of sitting/inactivity", fed by device sedentary detection
(row 190). So the quantity exists. What is missing is any way to obtain it
**at onboarding, before a device is connected** — which is exactly when O2.8
runs.

It is deliberately **not** bridged to `standing_hrs`. The resemblance is
precisely the trap: that is the same move this build refuses for `f_u_ref`
and parameter #37.

This is the sixth entry in `KNOWN_UNRESOLVED`, and the first found by a check
rather than by reading.

## The hand-written set is gone

`onboarding_symbols.DECLARED_INPUTS` carried this comment:

> Written by hand because "this is an answer the user gives" is not something
> a parser can tell from a name.

It now reads all 62 inputs from `O·Step-by-Step Questions`. Nine of its
twenty-one entries were that list retyped; the twelve that remain are
**bridges**, each with its stated reason — `waist` is `waist_cm` abbreviated,
`h` is `sleep_hrs` abbreviated, `SSB_serv_day` is `SSB_serv` per day. Every
one is a bridge declared by a person, never inferred from resemblance.

And the check can now do what a hand-written set never could: report an input
the equations declare and the interface does not collect. It found one on its
first run.

### Nine detector gaps fixed, none by suppression

Adding O5 reported nine new "undefined" symbols and **not one was a source
hole** — all were the analyser failing to read the notation:

| symbols | what was actually wrong |
|---|---|
| `Never`, `Former`, `Daily`, `Occasional` | answer *labels* read as quantities |
| `pack_years`, `units_week`, `tobacco_idx`, `SSB_serv_day` | the variable an encoding table *defines* never appears on a left-hand side |
| `Female`, `Male`, `e_alcohol` | O5.6's case guards `Female:` / `Male:` hid the definition behind them |

Fixed by three rules, each true of the notation rather than convenient: an
answer encoding **defines** the variable it encodes and its labels are data;
a case guard prefixes a definition the way `where` does. The ninth,
`drinks_wk`, was resolved by reading the UI contract.

### For Dr. Ali — two new questions

1. **Where does `sitting_hrs` come from at onboarding?** O2.8 needs it, Step
   2 collects standing hours instead, and device data does not exist yet at
   that moment.
2. **Which tobacco ranking is right?** O5.1 ties a recent ex-smoker with an
   occasional smoker; O5.7 does not.

---

## 2026-09-10: ONB-006 — the best-sourced sheet, and twelve symbols with no values

`O·O6 Family History` (manifest 76) is the only O-sheet that says where its
numbers came from. Every relative risk cites a study — EPIC-InterAct for type
2 diabetes, an AHA meta-analysis for stroke, first-degree-relative studies for
the cancers. Worth stating plainly, because most of this document is the
opposite.

It also states each relative risk **four times** — inside the formula as
`ln(RR)`, again pre-computed (`* 1.000`), again in the Variables cell
(`RR=2.72`), and again in the reference table — so the extractor recomputes
the logarithm and holds all four together. Nothing here rests on one cell.

### The one row that needs explaining

`ln(2.72) = 1.000632`, which rounds to **1.001**. The sheet writes **1.000**.

That is not an error. The T2D relative risk is ***e***, whose log is exactly
1, and 2.72 is *e* rounded for display. So the `ln(RR)` column is the exact
one and the `RR` column is the rounded one — the same "each column is
independently rounded" shape already recorded for `★ Scarring Bistability
Guard`. Every other row is straightforward correct rounding to three
decimals (error ≤ 5e-4); T2D's 6.3e-4 is the only one that is not.

The module therefore reads the sheet's **pre-computed** log rather than
recomputing `ln(2.72)`, because O6.2's declared range ("0 or 1.000") was
written against it.

### Checked against the UI, in both directions

Step 6 collects exactly six family-history checkboxes and O6.2–O6.7 read
exactly those six. A history collected and never read would be a question
asked for nothing; one read and never collected would be an equation that
cannot run. Neither happens here — the first O-sheet for which that could be
verified at all.

### The finding: twelve symbols named and never given

O6.8 and O6.9 are standard statistics written with **none of their inputs**.

| equation | names | supplies |
|---|---|---|
| O6.8 Pearson-Aitken | `mu`, `Sigma_12`, `Sigma_22`, `x2`, `mu_2` | nothing |
| O6.9 liability threshold | `g`, `e`, `threshold`, `sigma` | nothing |
| O6.10 | `eta_hi`, `FH_relevant` | see below |
| O6.11 | `sigma2_base` | nothing |

There is no covariance anywhere in the workbook between a family history and
a damage state, no population mean vector, no liability threshold for any of
the six conditions, and no default prior variance. The mathematics is
complete; only the numbers are missing.

So `pearson_aitken_posterior` and `liability_probability` take **every**
missing input as an argument, exactly as O1.9's `e_WHtR` is an argument. A
module that invented a covariance block would be inventing the prior.

#### `eta_hi` — the strongest bridge candidate so far, and still not bridged

O6.10's Variables cell says `eta_hi = base damage sensitivity`. Parameter
**#47** is `eta_hi,k`, layer C, equation C2, full name **"High damage
sensitivity"**. Same base spelling, same layer, same words; the `,k` is the
per-cluster subscript O6.10 drops while stating a general rule.

That is far better evidence than `f_u_ref` ever had — and it is still
inference, not a declaration, so it goes to the author rather than into the
code.

#### `FH_relevant` — answerable, but not by the sheet that asks

O6.10 raises damage sensitivity 30% when a family history is "relevant per
pathway", and defines relevance nowhere. The RR table's **Z-Pathway
Affected** column *does* map each condition to its pathways, and that is what
`relevant_pathways` reads. But the sheet never says that column is what
`FH_relevant` means, so the symbol stays reported.

### O6.11 is ambiguous and is not resolved

`sigma2_inflated = sigma2_base * 1.5 if FH positive` does not say **which**
family history, and the six are collected separately. Two readings:

- **any of six ticked** → a user with one distant relative gets the whole
  prior inflated, on every pathway
- **this pathway's own history** → only the pathways that history touches

`variance_inflation` therefore takes an explicit boolean rather than a
`FamilyHistory`. Choosing would be inventing the prior.

### A bug my own test caught

`load_o6_pathways` first joined equations to table rows **on the log-hazard**.
CVD, colon cancer and breast cancer all carry `ln(2.0) = 0.693`, so three
conditions collapsed into one and **CVD silently received breast cancer's
pathway** (Z2 instead of Z7).

The fix is a key that is actually unique: each equation is named `"FH " +` its
condition, exactly, and the extractor now asserts that correspondence and
checks the relative risks match across the join. Recorded because the failure
mode is the recurring one — a lookup that returns *something* is more
dangerous than one that returns nothing.

### For Dr. Ali — four questions

1. **Is O6.10's `eta_hi` parameter #47 `eta_hi,k`?** Everything matches but
   the cluster subscript.
2. **Where do O6.8's covariances and O6.9's thresholds come from?** Twelve
   symbols across four equations have no values anywhere.
3. **Which family history does O6.11 inflate on** — any of the six, or the
   pathway's own?
4. **Is the RR table's Z-Pathway column what `FH_relevant` means?** It is the
   only candidate, and the sheet does not say so.

---

## 2026-09-10: ONB-007 — the sheet that initialises 81 states and supplies no numbers

`O·O7 Diet Pattern Priors` (manifest 77) is the largest gap found in this
build. Its first equation is the whole point of the sheet:

    O7.1   C_f(0)_i ~ N(mu_pattern_i, sigma2_pattern_i)
    engine target: "Layer E: x_hat(0)[1..81]"

Those are the starting values of **81 of the engine's 219 states** — every
nutrient it tracks. To fill them the sheet needs a mean and a variance per
nutrient per pattern:

**8 patterns × 81 nutrients × 2 parameters = 1,296 numbers. The workbook has
none of them.**

What it supplies instead is prose, one line per pattern:

| pattern | key nutrient shifts | typical deficiencies |
|---|---|---|
| Mediterranean | "High omega-3, olive oil, fiber" | "None typical" |
| Vegan | "No animal products" | "B12, Iron, Zinc, Omega-3, Ca, VitD" |

Useful to a dietitian. Uncomputable by anything.

### Searched before concluding

- `mu_pattern` and `sigma2_pattern` appear in the entire workbook **only** on
  this sheet and its duplicate at `P1 Onboarding` row 328.
- The 81-nutrient registry carries kinetics — gamma shapes, decay constants,
  half-lives, `s_hi_log`, `s_lo_log` — and **no baseline-intake column of any
  kind**.
- The only other sheet whose name suggests patterns, `M-WPAT Patterns
  Alarms`, is Layer W's behavioural alarms and has nothing to do with diet.

So `nutrient_prior` **raises** rather than returning a number. A stub
returning zero, or a population average, would put an invented initial
condition into 81 states and nothing downstream could ever tell. The
exception is its own type, `PriorNotSupplied`, so it cannot be mistaken for a
mistyped nutrient id and so the day it is fixed the fix is greppable.

This blocks ONB-007 the way ONB-011 and ONB-012 are blocked — but more
sharply. Those are missing a *mapping*; this is missing 1,296 *numbers*.

### The pattern list is stated three times and the three disagree

| source | says |
|---|---|
| this sheet | **8** patterns; its own UI Label column marks two "Not in current UI" |
| `P1 DataMap` row 125 | "Radio (**8** options)", default "Standard Balanced" |
| the questionnaire, Step 3 | **6** options, including **Intermittent Fasting** |

The sheet already knows about two of the three gaps — DASH and Carnivore have
priors and cannot be selected, and it says so. Credit where due.

**What nothing anywhere mentions is that the interface offers a seventh
pattern the sheet has never heard of.** A user selecting *Intermittent
Fasting* matches no pattern, no nutrient shift, no deficiency list and no
prior.

Two further UI options fail an exact-label match — `Mediterranean` against
the sheet's "Mediterranean Diet", and `Low-carb/Keto` against
"Low-carb/Ketogenic". Those are near-misses with an obvious intended meaning,
and they are recorded rather than bridged, for the same reason `f_u_ref` is
not tied to parameter #37 and `sitting_hrs` is not tied to `standing_hrs`.
They are a *different kind* of problem from Intermittent Fasting, which has
no candidate at all, and keeping them apart is the point.

### O7.4 needs an encoding that does not exist

`DQI = (fruit_serv + veg_serv) / 10`, declared range 0-1, feeding O11's Z5.

Step 3 collects fruit and vegetable servings as **bands** — `0 / 1-2 / 3-4 /
5+` — and no sheet in the workbook says what those bands are worth. O5.2
gives midpoints for alcohol and O5.5 gives (wrong) ones for sugary drinks;
fruit and vegetables get none at all. So the declared 0-1 range cannot be
verified, and `diet_quality_index` takes servings rather than a band.

### What is buildable, and is built

O7.2's update is correct as written and needs no missing constant:

    sigma2_post = 1 / (1/sigma2_prior + k/sigma2_obs)

Precisions add, and each day of food logging contributes one more unit of
observation precision. `prior_weight` is that rearranged, which turns O7.3's
schedule ("days 1-7 the prior dominates, day 14+ the logs do") from decoration
into something checkable. O7.3 itself is reported as the sheet's **schedule**,
not as a computation — which source actually dominates depends on the ratio of
the two variances, and O7.1 supplies neither. Days 8–13 are named
`"transition"` rather than assigned to a side, because the sheet says nothing
about them.

Note the circularity: O7.2's `sigma2_prior` is exactly what O7.1 fails to
supply. Correct arithmetic that cannot be run until the priors exist.

### Five detector gaps fixed, none by suppression

Adding O7 reported seventeen new "undefined" symbols and **not one was a
source hole beyond the ones above**:

| symbols | what was actually wrong |
|---|---|
| `Day`, `Days`, `dominate(s)`, `food`, `logs`, `prior`, `large`, `small` | O7.3's whole cell is **prose**, not a formula |
| `C_f` | `~` asserts a distribution and defines its left side, exactly as `=` defines a value |
| `_i` | a trailing subscript tokenised out of `C_f(0)_i` |
| `N` | names the Normal distribution |

Each fix is a rule true of the notation: a cell with **no relation operator at
all** (`=` or `~`) asserts nothing and so names nothing; `~` is a relation
operator; a token starting with `_` is a subscript. `C_f` is then bridged to
the state vector's `C_fast` block — a structural match, not a resemblance:
that block is slots 1–81 and O7.1's engine target reads `x_hat(0)[1..81]`.

And one earlier trap recurred in a new place: a plain search for a digit read
`"High omega-3, olive oil, fiber"` as a table of numbers, because `omega-3`
and `B12` carry digits in their **names**. Same shape as the hyphen in
`dose-response`. The check now looks for a standalone number.

### For Dr. Ali — three questions

1. **Where do the 1,296 nutrient priors come from?** This is the single
   largest missing thing in the build: the initial condition of 81 of 219
   states. Without it, ONB-007 cannot initialise Layer E at all.
2. **What happens when a user selects Intermittent Fasting?** The interface
   offers it and the engine has no pattern for it.
3. **What are Step 3's fruit and vegetable bands worth numerically?** O7.4
   divides their sum by 10 and nothing says what `1-2` means.

---

## 2026-09-10: ONB-008 — a safety rule worth more than the table it sits above

`O·O8 Condition Modifiers` (manifest 78) is the only O-sheet with no numbered
equations. It is one ten-row table plus a single sentence of prose, and the
sentence is the important part.

### The compatibility rule

> **COMPATIBILITY RULE**: any legacy positive `F_bio` multiplier `m` is
> interpreted as an **ODDS** multiplier and converted to
> `Δlogit_abs = ln(m)`. The production equation is
> `F_abs = F_max · sigmoid(logit(F_base/F_max) + Σ Δlogit_abs)`;
> **no direct multiplication may exceed [0,1]**.

An absorbed fraction is bounded and a multiplier is not. The whole rule in one
comparison, from the tests:

| | result |
|---|---|
| `F_base = 0.8`, multiplied by 1.5 directly | **1.2** — not a fraction of anything |
| the same through log-odds, `F_max = 0.9` | **0.831** |
| a multiplier of **1,000**, same inputs | 0.8989 — still under `F_max` |
| no multipliers at all | `F_base` exactly |

That last row is the identity a compatible rewrite has to satisfy: with no
shifts the transformation must return what it was given, or it is a different
model rather than a safe way to express the same one. And `F_max` is a real
column in the 81-nutrient registry, so this composes with what is already
imported rather than needing a number nobody has.

Implemented verbatim in `sahacore/onboarding/condition_mods.py`, with
`apply_multipliers` provided so the conversion cannot be skipped by someone
who has legacy multipliers and reaches for the obvious thing.

### Five gates, and a design that will not let you drop one

The table does not say `eta_Z7 ×1.5`. It says:

- `eta_Z3 ×1.2` **only if symptoms support it** (IBS)
- `eta_Z7 ×1.5` **only when calibrated** (Cardiovascular context)
- `eta_Z11 ×1.5` **only when confirmed** (Osteoporosis)
- `eta_Z13 ×1.5` **only when calibrated** (Stroke history)
- "Use inflammation/repair modifier **when active**" (Celiac — a gate with no
  number behind it)

A reader who took the factor and dropped the clause would apply a 50%
damage-sensitivity increase the sheet explicitly withheld.

So `eta_multiplier` takes `gate_satisfied` as a **keyword-only argument
defaulting to False**, and raises `GateNotSatisfied` otherwise. The careless
call — the one that just asks for the number — fails. What "calibrated" or
"confirmed" actually *means* is defined nowhere in the workbook, so the
decision cannot be made here; it can be made impossible to make by accident.

The `Evidence role` column does the same work in the other direction, and is
kept verbatim for the same reason: *"Safety/target modifier; do not force K
malabsorption"*, *"Timing, not global absorption extent"*, *"Clinical
context; not an absorption multiplier"*. Each is a warning against one
specific misreading.

### The finding: more than half the declared effects are unquantified

The Z-pathways column declares **20** condition-to-pathway links. Only **9**
carry a factor.

| condition | declares | quantifies | left unstated |
|---|---|---|---|
| Type 2 Diabetes | Z1, Z6 | Z1 ×1.5, Z6 ×2.0 | — |
| Hypertension | Z7, Z9 | Z7 ×1.3 | **Z9** |
| CKD (Stage 3+) | Z9, Z14 | Z9 ×3.0 | **Z14** |
| NAFLD/MASLD | Z8, Z13 | Z8 ×2.0 | **Z13** |
| Celiac disease | Z5, Z11, Z12 | *none* | **Z5, Z11, Z12** |
| IBS | Z3, Z14 | Z3 ×1.2 | **Z14** |
| GERD/Acid reflux | Z3 | *none* | **Z3** |
| Cardiovascular context | Z7, Z12 | Z7 ×1.5 | **Z12** |
| Osteoporosis | Z11, Z15 | Z11 ×1.5 | **Z15** |
| Stroke history | Z13, Z7 | Z13 ×1.5 | **Z7** |

**Type 2 Diabetes is the only condition that quantifies everything it
declares.**

Those 11 links are stored with `factor` **NULL**, not 1.0, and
`eta_multiplier` raises rather than returning 1.0 — because *"declared
affected, effect unstated"* and *"no effect"* are different claims, and
defaulting silently converts the first into the second.

### The interface offers a condition with no row — again

Step 5's gastrointestinal question names **"IBS, GERD, Celiac, UC, NAFLD"**.
There is no **UC** row. Same shape as O7's Intermittent Fasting, one sheet
later.

And the condition set cannot be checked properly at all: of Step 5's five
questions only **two** name any condition, one of those trails off with
"etc.", so exactly **one** gives a checkable list. Three say only
"Multi-select checkboxes".

### Two counts I asserted and then computed

I wrote "four modifiers are gated" — it is five rows, four of which gate a
number. I wrote "one of five questions enumerates its options" — two name
conditions, one completely. Both were corrected by computing before
committing, which is the third time this pattern has shown up in this file.

### For Dr. Ali — three questions

1. **What do the eleven unquantified links do?** Celiac declares Z5, Z11 and
   Z12 affected and gives a factor for none.
2. **What establishes "calibrated" and "confirmed"?** Four modifiers are
   withheld until then, and neither term is defined.
3. **What happens when a user reports ulcerative colitis?** Step 5 offers it
   and this sheet has no row for it.

---

## 2026-09-10: ONB-009 — two registries in one workbook disagree about a safety hazard

`O·O9 Drug-Nutrient Mods` (manifest 79) gives twenty drug-nutrient rows. Two
things about it are new.

### O8's rule, confirmed by another sheet's arithmetic

`O·O8` says a legacy multiplier becomes `Δlogit_abs = ln(m)`. This sheet,
written separately, does exactly that five times:

| drug × nutrient | m | sheet's Δlogit_abs | ln(m) |
|---|---|---|---|
| Metformin × B12 | 0.70 | −0.356675 | −0.356675 |
| PPIs × Mg | 0.75 | −0.287682 | −0.287682 |
| PPIs × Ca | 0.80 | −0.223144 | −0.223144 |
| PPIs × B12 | 0.85 | −0.162519 | −0.162519 |
| PPIs × Fe | 0.80 | −0.223144 | −0.223144 |

Correct to six decimals, every one. This is the **first place in the build
where one sheet's rule is verified by a different sheet's numbers** rather
than by its own restatement — and the CI verify step now recomputes it in
SQL, so Postgres checks it too.

### Fifteen rows are not absorption effects, and the sheet says so twice

Their rule cell holds an action class — `TIMING`, `MONITOR`, `VETO`,
`VETO/MONITOR`, `CLEARANCE`, `N/A` — and two production targets spell out
what that means, in the strongest terms a spreadsheet has:

> Levothyroxine — *"Layer H: timing VETO; **do not alter nutrient F_abs**"*
> Fluoroquinolones — *"Layer H: timing VETO; **nutrient F_abs unchanged**"*

In both, chelation reduces absorption of the **drug**. Code that read it the
other way would cut a user's calcium target because they take a thyroid
tablet. So `delta_logit_abs` **raises** on those rows, quoting the sheet's own
sentence, rather than returning a number or a convenient zero — returning 0.0
would be as wrong as returning a shift, because this is a different *kind* of
effect, not a smaller one.

Statins × CoQ10 is the same distinction from the other side: CRITICAL, real,
and *"Biosynthesis depletion; not intestinal F_abs"*.

### The finding: O9 and the VETO registry disagree, downwards

| | severity | action |
|---|---|---|
| `VETO-DN-0265` Insulin (any) × Carbohydrate intake | **CRITICAL** | "STABLE PATTERN — discuss with prescriber" |
| `VETO-DN-0267` Sulfonylureas × Carbohydrate intake | **CRITICAL** | "STABLE PATTERN — discuss with prescriber" |
| O9 row 29 — Insulin/sulfonylureas × Glucose | **MODERATE** | "MONITOR", *Layer H: glucose safety* |

Same drug class, the same hypoglycaemia hazard. One registry routes it to a
**prescriber**; the other asks for a **measurement**. This is the pair earlier
sessions flagged as MSG-CRITICAL-STABLE, now seen from the other side.

Recorded, not resolved. `severity_disagreements()` reports it and a CHECK
constraint refuses to store a "disagreement" whose two severities are equal,
so the row cannot go stale silently.

**The bridge is declared by hand, one pair at a time.** A substring match on
"Metformin" pulls in seven VETO rows about different nutrients, and comparing
severities across those would manufacture disagreements that are not there.
Only the pair actually read row-by-row is recorded.

### The two severity scales do not match at all

| | scale |
|---|---|
| O9 | CRITICAL / MODERATE / LOW |
| VETO registry | CRITICAL / HIGH / MODERATE / LOW / CONTROVERSIAL |

O9 has **no HIGH tier**, and HIGH is the VETO registry's **largest** — 111 of
339 rows, just under a third (CRITICAL 94, MODERATE 110, LOW 23,
CONTROVERSIAL 1). An O9 row cannot express what the biggest slice of that
registry says. That is a plausible mechanism for the insulin disagreement
rather than an excuse for it: with no HIGH available, a HIGH-shaped hazard has
to round somewhere, and here it rounded down.

### The interface gap, third sheet running

Step 7 names 22 medications. Three are the same drug spelled differently —
"ACE Inhibitors & ARBs" against "ACE inhibitors/ARBs", "Oral Contraceptives"
against "Oral contraceptives" — and normalising case and `&`/`/` bridges those
without changing a word. **Eight remain:**

- **seven with no row of any kind**: Antibiotics, Antiplatelet, Beta Blockers,
  Magnesium, SNRIs, Theophylline, Vitamin E
- **"Diuretics"**, which is a *broader* class than the sheet's "Thiazide/loop
  diuretics" — a different question from a drug with no row, and kept separate

And it runs the other way too: **Warfarin is modelled, with a CRITICAL Vitamin
K veto, and the interface never names it.** Step 7's first row is a free-text
"Search bar + categories", so the named medications are examples rather than
the whole list — which is itself why neither direction can be closed from
here.

### One claim I made loosely and then measured

I wrote that HIGH is "a third" of the VETO registry. It is 111 of 339 —
32.7%, just *under* a third. What is true and worth saying is that it is the
**largest** tier. Corrected in four files before committing.

### For Dr. Ali — three questions

1. **Which severity is right for insulin and sulfonylureas?** One registry
   says CRITICAL and refers to a prescriber; this one says MODERATE and asks
   for a measurement.
2. **Should O9 have a HIGH tier?** Without one it cannot express the VETO
   registry's largest category.
3. **What happens for the seven medications with no row** — and for warfarin,
   which the interface cannot record?

---

## 2026-09-10: ONB-010 — the cleanest UI alignment yet, and one weight from nowhere

`O·O10 Goal Priority Wts` (manifest 80) turns a user's ranked health goals
into the `pi_k` weights Layers D and F use.

### What it gets right

**It cites its sources** — AHA and REDUCE-IT for heart health, ADA 2024 for
metabolism, NOF/IOF for bone, EFSA for immunity, ASRM for fertility. Only
`O·O6 Family History` does the same. Two sheets out of ten.

**It agrees with itself.** Every goal row states `2.5 (if Primary)` and the
rules table gives `Primary = 2.5` independently.

**The ladder is monotone and its baseline is exactly 1.0:**

| rung | pi_k |
|---|---|
| Primary (1st selected) | 2.5 |
| Secondary (2nd selected) | 2.0 |
| Tertiary (3rd selected) | 1.5 |
| Unselected | **1.0** |

The baseline being *exactly* one is what makes `pi_k` a multiplier on a reward
term rather than a rescaling of everything — a user who ranks nothing gets the
unweighted reward, not a shrunken one.

**And Step 11 lines up completely** — the best agreement any O-sheet has had
with the interface. Its eight options are this sheet's eight rows: six
exactly, and two where the sheet truncates the UI's label ("Immunity &
Inflammation Control" → "Immunity & Inflammation"). Nothing unmatched in
either direction, for the first time.

### The finding: the heaviest weight is assigned from a question whose answers are not goal areas

The rules table says the Primary goal — `pi_k = 2.5`, the top rung — is the
*"Highest priority goal from **Step 4/11**"*.

| | options |
|---|---|
| **Step 11** `goal_areas[]` | Heart Health · Metabolism & Diabetes · Longevity & Anti-Aging · Bone Health · Immunity & Inflammation Control · Gut Health · Fertility & Hormone Health · Stress & Mental Health |
| **Step 4** `primary_goal` | Weight Loss · Muscle Gain · Energy Levels · Digestive Health · Chronic Condition · Manage Benefits · Healthy Aging |

Step 11's eight **are** this sheet's rows. Step 4's seven are **none of
them**. "Weight Loss" has no `pi_k`, no nutrient targets and no Z-pathways —
and it is the answer to the question literally called *primary_goal*.

So either Step 4 does not supply the Primary goal and the rule should say
Step 11 alone, or Step 4's answers need a mapping into these eight that no
sheet provides. `weight_for` therefore takes a **rank**, not a goal name, and
`goal_for_ui_option` raises on a Step 4 answer rather than returning a silent
1.0.

### What these weights multiply is an open founder decision

The rules table names its engine equation: **`H1: r_t^pi = SUM(pi_k · r_k)`**.

Layer H is the conservative bandit, and `★ Scoped Builds — LTMLE Bandit`
lists the bandit's reward proxy as **OPEN FOUNDER DECISION 5**, with its own
note calling it *"the single biggest decision"*.

So this sheet settles `pi_k` precisely — to one decimal, with a monotone
ladder and a clean baseline — for a sum whose terms `r_k` are undecided.
`weighted_reward` composes them and makes the caller supply `r_k`, so the
undecided half stays visible rather than being defaulted.

### For Dr. Ali — two questions

1. **Does the Primary weight come from Step 4 or Step 11?** The rule says
   both; only Step 11's answers are goal areas.
2. **What is `r_k`?** `pi_k` is fully specified and the reward it weights is
   still open founder decision 5.
