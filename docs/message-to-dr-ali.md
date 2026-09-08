Subject: SahaCore — status, and five per-nutrient columns I need to finish the data spine

Dr. Ali,

Quick status first. Layers A, B, C and D are implemented and tested against
the workbook's own numbers — the Validation Test Battery gates C1, C2, C5, S3
and S4 all pass, and Layer M reproduces every one of the QA-023…QA-029 golden
values from the Live Verification Lab to 1e-15. The event ledger with
bitemporal replay is built (Replay Contract steps 1–11, RT-02 and AUD-01
passing), and the T-1 database firewall from `08 · Delivery & Firewall` is
enforced at the role level, so QA-014 is green. 363 tests, all passing in CI
against PostgreSQL.

I've now audited every workbook you sent — all 11 distinct files, sheet by
sheet — to find the per-nutrient parameters Layers A and B need. Five columns
are not in any of them, and I don't want to invent values for parameters the
registry marks Critical.

**What I'm asking for: five columns on the P1 Nutrients table, for all 81.**

Using the row numbers in `P1 Parameters 134+`:

| # | Symbol | Layer | Units | Range given | Weight | What I have |
|---|---|---|---|---|---|---|
| 14 | `F_base,i` | A | — | 0.01–1.0 | Critical | 18 of 81 |
| 15 | `K_m,i` | A | mg | 10–5000 | Critical | 0 of 81 |
| 29 | `V_s,i` | B | L | 5–200 | High | 0 of 81 |
| 37 | `f_unbound,i` | B | — | 0.01–1.0 | Critical | 0 of 81 |
| 41 | `CL_int,i` | B | mL/min | 0–5000 | High | 0 of 81 |

`Q_liver` (#40) is fine — it's a single physiological value with the ICRP
Pub 89 formula, already implemented. `V_f`, `F_max`, `T½_fast`, `T½_slow`,
`γ_k`, `γ_θ`, `λ`, `κ_fast/slow`, `w_fast`, `s_hi`, `s_lo` are all present in
`P1 Nutrients 81` and loaded.

**Why I believe these exist somewhere.** Three things point the same way:

1. `04 Engine Binding` in the Twin workbook, row 20, says the per-nutrient
   row should carry "Half-life, F_max/F_base/Km, V1/V2, Q/CL". The sheet we
   hold carries half-life, F_max and V1 — not F_base, Km, V2 or CL.

2. The same sheet's header says its citations were checked against a master
   with **245 sheets**. The two masters I hold have 204 and 205. About forty
   sheets cited by the files I have, I've never seen. If the nutrient
   parameters live in one of those, that would explain everything.

3. The `layer_b_results.csv` you sent contains `CL_total` and `k_el` for
   seven nutrients, constant across all 128 timesteps — so they're
   parameters, not state. The half-lives they imply (iron 60 d, vitamin D
   15 d, B12 180 d, calcium 0.8 d, protein 0.25 d, vitamin C 0.4 d, zinc
   5 d) are literature values that don't match the `T½` columns in
   `P1 Nutrients 81`. So a fuller parameter set exists and has been run.

**Three smaller items while I'm asking:**

- `K_m,i` is the thinnest — the registry gives only the 10–5000 mg range and
  one worked example, "Vitamin C K_m ~200mg" (Levine 1996). If a full table
  doesn't exist, tell me and I'll build one from published transporter
  saturation data with every value sourced and flagged as fitted, for you to
  review. I'd rather do that openly than quietly pick numbers.

- `★ Damage Registry — Canonical` is almost complete: `eta_hi`/`eta_lo` on
  108 of 108 rows, `theta_hi`/`theta_lo` on 92. Sixteen rows have no
  threshold — seven in C7 (B2, B6, B9, B12, choline, methionine, glycine) and
  nine in C9 (B6, B9, B12, vitamin D, iron, magnesium, DHA, tryptophan,
  tyrosine).

- `V_f` in `P1 Nutrients 81` takes only two distinct values across all 81
  nutrients (50 dL and 500 dL). That may be deliberate as a placeholder, but
  I wanted to flag it rather than assume.

**What I'm doing meanwhile.** Layer E (the RB-SR-UKF) is next and its
structure doesn't depend on these — 219 states, 164 linear / 55 nonlinear,
111 sigma branches are all fixed and already verified. So I'll build it in
parallel. Nothing is stalled; the parameters affect what the engine computes
on, not whether it computes.

One correction I should make, since I may have said otherwise earlier: I no
longer think anything was removed from the nutrient table. The
"P1 Nutrients 80" / "P1 Nutrients 81" difference is just the two masters
naming the same sheet differently after nitrate became #81 — the Engine
Binding sheet says so explicitly in its header. The gap is that we're working
from a smaller master, not that a column was deleted.

Happy to take any of this on a call if that's faster.

Waleed
