"""Runs every registry loader, in the order the foreign keys require.

    python -m sahacore.data.load_all

WHY THIS EXISTS. The loader sequence used to live only in .github/workflows,
as 38 lines of shell. Then the `docker` job needed the same sequence to prove
the image can populate a database from nothing, and a second copy of a list
that grows with every imported sheet is a copy that goes stale -- silently,
because a missing loader does not fail the load, it just leaves a table
empty. So the order lives here, once, and both CI jobs call this.

THE ORDER IS NOT ALPHABETICAL AND MUST NOT BE SORTED. Nutrients before the
cluster weights that reference them, the message templates before the VETO
rules whose message_id is a foreign key into them, the onboarding canonical
contract before the O-sheets it names. It is the order the sheets were
imported in, which is the order '01_IMPORT_MANIFEST' gives.

Each module is executed exactly as `python -m` would execute it, so what runs
here is what ran in CI before, including what it prints.
"""
import runpy
import sys

# Appended to as sheets are imported. tests/test_loaders.py asserts this list
# and sahacore/data/load_*.py are the same set, so a new loader cannot ship
# without joining it.
LOADERS = [
    "load_nutrients",
    "load_state_vector",
    "load_layer_c_d",
    "load_layer_m",
    "load_qssa_atp",
    "load_ledger_policy",
    "load_parameter_registry",
    "load_eq_param_fk",
    "load_eq_build_rows",
    "load_veto_messages",
    "load_veto_registry",
    "load_action_space",
    "load_runtime_invariants",
    "load_param_registry_ext20",
    "load_nutrient_classes",
    "load_supplement_registry",
    "load_equation_backbone",
    "load_datamap",
    "load_core_equations",
    "load_state_admission",
    "load_organ_registries",
    "load_bistability_guard",
    "load_verification_labs",
    "load_validation_battery",
    "load_scoped_builds",
    "load_onboarding_canonical",
    "load_onboarding_o1",
    "load_onboarding_o2",
    "load_tvmcd_pathways",
    "load_onboarding_o3",
    "load_onboarding_o4",
    "load_step_questions",
    "load_onboarding_o5",
    "load_onboarding_o6",
    "load_onboarding_o7",
    "load_onboarding_o8",
    "load_onboarding_o9",
    "load_onboarding_o10",
]


def load_all() -> int:
    for name in LOADERS:
        try:
            runpy.run_module(f"sahacore.data.{name}", run_name="__main__")
        except Exception:
            # Which loader, said before the traceback. A failure in the 31st
            # of 38 otherwise arrives as a traceback from a module nobody
            # named, several screens below the last line that printed.
            print(f"FAILED in sahacore.data.{name}", file=sys.stderr)
            raise
    return len(LOADERS)


if __name__ == "__main__":
    print(f"ran {load_all()} loaders")
