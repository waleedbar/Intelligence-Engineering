Subject: SahaCore — the P1 Nutrients table we have is the uncalibrated one

Dr. Ali,

Status first. Layers A, B, C and D are implemented and tested against the
workbook's own numbers — Validation Battery gates C1, C2, C5, S3 and S4 pass,
and Layer M reproduces every QA-023…QA-029 golden value from the Live
Verification Lab to 1e-15. The event ledger with bitemporal replay is built
(Replay Contract steps 1–11, RT-02 and AUD-01 passing), and the T-1 database
firewall from `08 · Delivery & Firewall` is enforced at the role level, so
QA-014 is green. 363 tests, all passing in CI against PostgreSQL.

I've now audited every file you sent — all 11 distinct workbooks, the PDFs,
the CSVs, and the raw XML of the masters. I found something I need to flag.

**The `P1 Nutrients 81` sheet in the master appears to be the uncalibrated
version of the table.**

`F_max` is **1.0 for all 81 nutrients**. Read straight from the workbook, not
through my loader. `P1 Parameters 134+` row 120 defines `F_max,i` as
Critical, with calibration method *"Nutrient-specific literature; default 1.0
until calibrated"* — so the whole column is sitting at its documented
placeholder. `V_f` is likewise 50 dL on 80 of the 81 rows.

The Twin workbook's `11 Worked Trace` gives the calibrated values for two
nutrients, and cites this same sheet as their source:

| | Vitamin C | Magnesium | what we have |
|---|---|---|---|
| F_max | 0.90 | 0.45 | 1.0 / 1.0 |
| F_base | 0.75 | 0.30 | — |
| Km | 200 | 250 | — |
| Gastric T50 / κ | 75 / 1.3 | 95 / 1.1 | — |
| Half-life (d) | 0.25 | 1.0 | 0.5 / 1.0 |
| V1 / V2 (dL) | 32 / 60 | 40 / 140 | 50 / — |
| Q / CL (dL/min) | 0.35 / 0.30 | 0.20 / 0.12 | — |

Nothing matches except the gamma shape. Two things corroborate it: the
Bariatric and GLP-1 modules give baseline bioavailabilities for 18 nutrients
(iron 0.15, calcium 0.30, selenium 0.80 …), every one below 1.0 and agreeing
exactly where the two sheets overlap; and `layer_b_results.csv` carries
`CL_total` and `k_el` for seven nutrients, constant across all 128
timesteps — parameters, not state — implying half-lives (iron 60 d,
vitamin D 15 d, B12 180 d, vitamin C 0.4 d) that don't match our columns.

So the calibrated table exists, has produced a published verification trace,
and has been run end to end.

**What I need: the calibrated `P1 Nutrients` table, with these columns for
all 81.** Registry row numbers from `P1 Parameters 134+`:

| # | Symbol | Weight | State in our copy |
|---|---|---|---|
| 120 | `F_max,i` | Critical | present, stubbed to 1.0 |
| 25 | `V_f,i` | Critical | present, stubbed to 50 dL |
| 14 | `F_base,i` | Critical | absent (18 recoverable) |
| 15 | `K_m,i` | Critical | absent |
| 29 | `V_s,i` | High | absent |
| 37 | `f_unbound,i` | Critical | absent |
| 41 | `CL_int,i` | High | absent |

The two stubbed ones matter most, because they look present — code reads them
and gets a number with no warning. It also means our C2 gate ("F_abs ≤ F_max
in 100% of draws") is currently passing trivially, since F_abs ≤ 1 by
construction.

`Q_liver` (#40) is fine — one physiological value with the ICRP Pub 89
formula, already implemented. And `γ_k`, `γ_θ`, `λ`, `κ_fast/slow`, `w_fast`,
`T½_fast`, `T½_slow`, `s_hi`, `s_lo` are all present and loaded, though the
trace's `λ` and `T½` for vitamin C differ from ours too, so those may be from
a different vintage.

**Two smaller items:**

- `★ Damage Registry — Canonical` is nearly complete: `η_hi`/`η_lo` on 108 of
  108 rows, `θ_hi`/`θ_lo` on 92. Sixteen rows have no threshold — seven in C7
  (B2, B6, B9, B12, choline, methionine, glycine) and nine in C9 (B6, B9,
  B12, vitamin D, iron, magnesium, DHA, tryptophan, tyrosine).

- If a full `K_m` table doesn't exist anywhere, say so and I'll build one from
  published transporter-saturation data, every value sourced and flagged as
  fitted, for you to review. The registry gives only the 10–5000 mg range and
  one example (vitamin C ~200 mg, Levine 1996) — and the trace confirms that
  200. I'd rather build it in the open than quietly pick numbers. `07
  Parameters` says the same thing: *"If a number is needed and it is not on
  this sheet, it does not exist yet — raise it as a gap rather than choosing
  one."*

**What I'm doing meanwhile.** Layer E (the RB-SR-UKF) is next and its
structure doesn't depend on any of this — 219 states, 164 linear / 55
nonlinear, 111 sigma branches are fixed and already verified. So I'll build it
in parallel. Nothing is stalled; these parameters change what the engine
computes on, not whether it computes.

Ruled out, so you don't have to check: no sheet is missing from the master
(`01_IMPORT_MANIFEST` lists 205, the file has exactly those 205), there are no
hidden sheets or defined names, and `v39sEng` is identical to `v39sEng2`
across all 204 shared sheets.

Happy to take this on a call if that's faster.

Waleed
