# archive/ — written out of order, parked until the build reaches them

Nothing here is wrong. It is early.

`★ Build Guide Python` sets the order, and these modules belong to **step 4**:

| Step | Package | State |
|---|---|---|
| 1 | `sahacore.ledger` | built |
| 2 | `sahacore.registry` | registries loading |
| 3 | `sahacore.onboarding` — Layer 0, 14 sub-modules | **not started** |
| 4 | `sahacore.layer_a/b/c` | **the code in this folder** |

Step 4 was written before step 3 existed. Layers A/B/C take a state and return
a state; Layer 0 is what produces the first one — `x(t_0)`, the 219-state
initial vector, and `P(t_0)`, its covariance. Without step 3 these functions
have correct mathematics and nothing to run on.

They are also uncalibrated: `F_base,i`, `K_m,i`, `alpha_scar`,
`beta_autophagy`, `a_k`/`b_k` and eleven others are defined in the workbook
with units and admissible ranges but no values. See `docs/parameter-gaps.md`.

## What is here

| File | Layer | Source sheet |
|---|---|---|
| `engine/absorption.py` | A — absorption kernel | `P1 Core Equations` A1–A5 |
| `engine/pharmacokinetics.py` | B — two-compartment PK | `P1 Core Equations` B1–B6 |
| `engine/damage.py` | C — damage accumulation | `P1 Core Equations` C1 |
| `engine/repair.py` | C — Michaelis-Menten repair | `P1 Core Equations` C6 |
| `engine/scoring.py` | D — score and traffic light | `P1 Core Equations` D1–D2 |
| `engine/scarring.py` | M — durable memory | `M-EQ LayerM Equations` M1, M2 |
| `engine/qssa.py` | QSSA — ATP branch | `P1 QSSA ATP-GSH-NAD` |

`tests/` holds their 158 tests, including
`test_official_validation_battery.py`, which is the workbook's own validation
battery rather than tests written here — worth re-reading before any of this
is revived.

## Bringing a module back

```
git mv archive/engine/absorption.py sahacore/layer_a/
git mv archive/tests/test_absorption.py tests/
```

Do that when the build reaches step 4, and rename the package to the one the
Build Guide names (`sahacore.layer_a/b/c`) rather than the `sahacore.engine`
these were written under. Check each function's parameters against
`engine_internal.parameter_gaps` first: a layer that runs on placeholder
values produces numbers that look like results.

Nothing in `sahacore/` imports this folder, and CI does not collect these
tests.
