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
