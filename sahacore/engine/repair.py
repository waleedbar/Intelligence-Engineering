"""Layer C: equation C6 (MM Repair, Competitive) in Dr. Ali's v39sEng2
workbook, sheet 'P1 Core Equations'.

Source formula (transcribed verbatim, "*** CORRECTED ***" in source):

    repair_k = Vm * Z_k / (Km * (1 + SUM_{j!=k} Z_j/K_j) + Z_k)

Competitive inhibition across the 15 TVMCD pathways sharing repair
enzymes: every other pathway's damage stock (Z_j, scaled by its own Km)
competes for the same repair capacity, so repair_k falls as any other
pathway's damage rises -- not just its own.

CATASTROPHIC ALERT (source's own words): if the forcing damage rate for a
pathway exceeds Vm, no steady state exists for that pathway's stock. That
check needs the damage *rate* (an external forcing input, e.g. from
u_hi_k/u_lo_k in C2/C3), which this function doesn't receive -- it's the
responsibility of whatever integrates this into the C2-C4 ODE loop, not
this pure rate calculation.

*** SCOPE OF THIS MODULE ***
The source flags (v32.4 note) that production "Vm" here is really
V_max_eff = Vm * exp(-gamma_scar*S) * f_ATP * f_NAD -- a QSSA-coupled
value that depends on Layer M's scarring state S (not built) and the QSSA
sidecar's f_ATP/f_NAD support fractions (not built). So vm_values here is
a plain input, same pattern as Cbar_i in damage.py and z_k in scoring.py:
pass the raw per-pathway Vm from tvmcd_pathways_15.json for now, or the
real V_max_eff once Layer M/QSSA exist -- this function doesn't compute
that adjustment itself.
"""


def competitive_repair_rate(
    pathway_id: str,
    z_values: dict[str, float],
    vm_values: dict[str, float],
    km_values: dict[str, float],
) -> float:
    """repair_k for one pathway, given every pathway's current damage
    stock Z_j (z_values) and each pathway's own (Vm, Km) (vm_values,
    km_values) -- e.g. read from tvmcd_pathways_15.json, keyed by
    pathway_id ('Z1'..'Z15')."""
    z_k = z_values[pathway_id]
    vm_k = vm_values[pathway_id]
    km_k = km_values[pathway_id]
    competitive_sum = sum(
        z_values[j] / km_values[j] for j in z_values if j != pathway_id
    )
    return vm_k * z_k / (km_k * (1 + competitive_sum) + z_k)


def competitive_repair_rates(
    z_values: dict[str, float],
    vm_values: dict[str, float],
    km_values: dict[str, float],
) -> dict[str, float]:
    """repair_k for every pathway in z_values, computed with the shared
    competitive-inhibition pool."""
    return {
        pathway_id: competitive_repair_rate(pathway_id, z_values, vm_values, km_values)
        for pathway_id in z_values
    }
