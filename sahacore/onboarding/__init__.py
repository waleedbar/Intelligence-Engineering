"""Layer 0 — the onboarding prior bridge.

'★ Build Guide Python' step 3: turn a person's onboarding answers into the
engine's starting point, x(t0) in R^219 and P(t0), plus the first control
vector. Acceptance: "length x0=219; PSD P0".

'O · Onboarding Canonical' names the fourteen modules, ONB-001 to ONB-014,
and this package holds one per row. Twelve can be written today; ONB-011 and
ONB-012 wait on the 15->12 pathway-to-cluster bridge that is missing from the
workbook -- see engine_internal.onboarding_blocked and docs/parameter-gaps.md.

NO PHYSIOLOGICAL CONSTANT IS WRITTEN IN THIS PACKAGE. Every threshold,
coefficient and reference value is read from the extracted registries, which
carry the sheet, row and literature source each came from. A number typed
into a .py cannot be versioned, diffed, or traced back to the study it came
from, and 'P1 Parameters 134+' exists precisely so that it does not have to be.
"""
