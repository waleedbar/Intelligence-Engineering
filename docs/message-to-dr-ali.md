# Message to Dr. Ali

Two versions. Send the short one on WhatsApp; keep the long one for email or
for when he asks for detail.

**Scope note (for us, not for him).** An earlier draft of this asked for
`V_f` and `V_s` as well. That was wrong and has been removed — see
`docs/parameter-gaps.md`, "What we got wrong". It also led with `F_max`,
which is a real gap but a milder one than that draft implied. The request
below is the narrowed, verified version.

---

## SHORT (WhatsApp)

Hi Dr. Ali — progress note and one request.

Layers A, B, C and D are built and passing the workbook's own validation
gates (C1, C2, C5, S3, S4), Layer M reproduces the Live Verification Lab
golden values to 1e-15, the event ledger with bitemporal replay is done, and
the T-1 database firewall is enforced at the role level so QA-014 is green.
364 tests, all green in CI against PostgreSQL.

Wiring Layer A/B, I hit one real gap. **`F_base,i` and `K_m,i` aren't in
`P1 Nutrients 81`** — the two per-nutrient values A4 needs
(`F_abs = F_max·σ[logit(F_base/F_max) − log1p(q/Km) + …]`). I found 18 of
the 81 `F_base` values in the Bariatric and GLP-1 module tables (they agree
exactly where they overlap), but no `K_m` for any nutrient beyond the
vitamin C ~200 mg example in the parameter registry.

The Twin workbook's `11 Worked Trace` has both for two nutrients — vitamin C
F_base 0.75 / Km 200, magnesium 0.30 / 250 — and I checked they're real:
fed into our A4 with no modifiers they reproduce the sheet's own stated
F_abs to six decimals (0.652174 vs 0.652, 0.258621 vs 0.259). So a
calibrated set exists somewhere.

**Could you send the calibrated `P1 Nutrients` table with `F_base` and `K_m`
for all 81?** Three smaller things while you're in there:

1. `f_u_ref` per nutrient — `O1.8` computes `f_u = f_u_ref × (1 − 0.1·max(BMI−25,0)/25)`
   and its own input cell says "f_u_ref per nutrient", but I can't find that table.
2. `CL_int,i` — appears in exactly two cells across all 12 workbooks, both the
   same definition row.
3. The 12 `w_k^fix` display weights for CHS, and 16 rows in
   `★ Damage Registry — Canonical` carrying "—" for θ_hi/θ_lo (7 in C7, 9 in C9).

One thing to sanity-check rather than send: `F_max` is 1.0 on all 81 rows,
and `P1 Parameters 134+` row 120 gives its calibration method as
"default 1.0 until calibrated". With a real `F_base` the model still computes
correctly — the ceiling just never binds — so it's a lost safety margin
rather than a wrong answer. Is 1.0 intentional for now?

Nothing is blocked. Layer E's structure doesn't depend on any of this, so
I'm starting it. Happy to jump on a call if that's quicker.

Waleed

---

## LONG (email)

Subject: SahaCore — F_base and K_m are missing from P1 Nutrients 81

Dr. Ali,

Status first. Layers A, B, C and D are implemented and tested against the
workbook's own numbers — Validation Battery gates C1, C2, C5, S3 and S4 pass,
and Layer M reproduces every QA-023…QA-029 golden value from the Live
Verification Lab to 1e-15. The event ledger with bitemporal replay is built
(Replay Contract steps 1–11, RT-02 and AUD-01 passing), and the T-1 database
firewall from `08 · Delivery & Firewall` is enforced at the role level, so
QA-014 is green. 364 tests, all passing in CI against PostgreSQL.

I've audited every file — all 12 distinct workbooks, the PDFs, the CSVs and
the raw XML of the masters. Here is what I can't resolve from them.

### 1. `F_base,i` and `K_m,i` — the blocking pair

A4 is `F_abs = F_max·σ[logit(F_base/F_max) − log1p(q/Km) + Σγ·tanh(z) +
γ_cook + γ_cond]`. `F_base` and `Km` are the two per-nutrient values it needs,
and neither is a column in `P1 Nutrients 81`.

What I could find:

* **`F_base`: 18 of 81.** `P1 Bariatric Module` column "F_bio Base" (17
  nutrients) and `P1 GLP-1 Module` column "F_base" (15). The 14 that appear
  in both agree exactly — iron 0.15, calcium 0.30, zinc 0.30, vitamin E 0.30,
  copper 0.35, magnesium 0.40, B12/D3/K/folate 0.50, vitamin A 0.70,
  selenium 0.80, potassium/protein/thiamine/leucine 0.90, carbohydrate and
  fat 0.95.
* **`K_m`: 0 of 81.** `P1 Parameters 134+` row 15 gives only the 10–5000 mg
  range and one example, "Vitamin C K_m ~200mg" (Levine 1996). Every other
  `Km` in the workbooks is a QSSA enzyme constant in µM or the MM-repair
  `K_m = θ_elastic` — different quantities.

The Twin workbook's `11 Worked Trace` has both for two nutrients: vitamin C
F_max 0.90 / F_base 0.75 / Km 200, magnesium 0.45 / 0.30 / 250. I verified
these are genuine rather than illustrative — fed into our A4 implementation
with all modifiers zero, they reproduce the sheet's own stated outputs to six
decimals (0.652174 against 0.652; 0.258621 against 0.259). So a calibrated
set exists and has been run.

**Ask: the calibrated `P1 Nutrients` table with `F_base` and `K_m` for all 81.**

### 2. `f_u_ref,i`

`O·O1 Anthropometrics` O1.8 computes `f_u = f_u_ref × (1 − 0.1·max(BMI−25,0)/25)`
and its own input cell reads "f_u_ref **per nutrient**, BMI from O1.3". The
personalisation formula is there; the reference table it consumes is not.
`O·Engine Connections` G9 likewise says "Unbound fraction per nutrient".

### 3. `CL_int,i`

Appears in exactly two cells across all 12 workbooks, both the same
definition row (`P1 Parameters 134+` C46). B6's well-stirred model needs it
for the low-extraction limit: `E_H = f_u·CL_int / (Q_H + f_u·CL_int)`.
`Q_liver` itself is fine — one physiological value with the ICRP Pub 89
formula, already implemented.

### 4. The 12 `w_k^fix` display weights

`P1 Core Equations` defines `CHS = 100 − Σ w_k^fix·D_final_k / Σ w_k^fix`,
with `w_k^fix` described as "clinically-reviewed CONSTANT display weights".
The formula appears in three sheets; the twelve values appear in none — two
cells in the whole corpus, both the formula reference. Without them the
composite score can't be computed as specified.

### 5. Sixteen damage thresholds

`★ Damage Registry — Canonical` is otherwise complete: η_hi/η_lo on 108 of
108 rows, θ_hi/θ_lo on 92. Sixteen rows carry a literal "—" — seven in C7
(B2, B6, B9, B12, choline, methionine, glycine) and nine in C9 (B6, B9, B12,
vitamin D, iron, magnesium, DHA, tryptophan, tyrosine).

### Two things to confirm rather than send

**`F_max` is 1.0 on all 81 rows.** `P1 Parameters 134+` row 120 gives its
calibration method as "Nutrient-specific literature; default 1.0 until
calibrated", and the Worked Trace uses 0.90 and 0.45. With a real `F_base`
the model still computes correctly — the ceiling simply never binds — so this
costs a safety margin rather than producing a wrong number. Is 1.0
intentional for now?

**`V_f` has three different references.** `P1 Nutrients 81` column O gives
50 dL; `P1 DataMap` row 33 gives `0.05 × weight_kg × 10` (35 dL at 70 kg);
`O1.1` gives `V_ref × (BW/70)^0.75` with V_ref = 15 L (150 dL at 70 kg),
noting that this is "a GENERIC PRIOR ONLY, not a universal physiological
plasma volume … use per-nutrient V_f,i where characterised". We implemented
O1.1 because it carries the v39l F-AX tag, but a 4× spread across three
sheets is worth a ruling. Same question for `V_s` (30 L allometric prior vs
the 500 dL structural prior in `P1 Scoring Alerts`).

### If any of these don't exist yet

Say so and I'll build them from published sources — every value cited and
flagged as fitted, for you to review — rather than quietly choosing numbers.
The API workbooks' own `07 Parameters` sheet takes the same line: *"If a
number is needed and it is not on this sheet, it does not exist yet — raise
it as a gap rather than choosing one."*

### Meanwhile

Layer E (the RB-SR-UKF) is next and its structure doesn't depend on any of
this — 219 states, 164 linear / 55 nonlinear, 111 sigma branches are fixed
and already verified — so I'm building it in parallel. Nothing is stalled.

Ruled out already, so you don't have to check: no sheet is missing from the
master (`01_IMPORT_MANIFEST` lists 205 and the file contains exactly those
205), there are no hidden sheets, defined names or embedded objects, and
`v39sEng` is byte-identical to `v39sEng2` across all 204 shared sheets.

Happy to take this on a call if that's faster.

Waleed
