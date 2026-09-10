"""Records the version of every loaded registry, and cross-checks the loaders.

    python -m sahacore.data.record_registry_versions

Run after the loaders. For each registry it hashes the JSON the loader read,
counts what actually reached the database, refuses to record a version if the
two disagree, and otherwise writes (or confirms) the ACTIVE version that
derived packets must cite -- see sahacore/registry_version.py and
'IO · Lineage DataMap'.

WHY THE CROSS-CHECK IS HERE. A version recorded from the source file alone
would attest to what the loader was *given*, not to what it *wrote*. Those
differ whenever a loader silently drops rows -- which has happened twice in
this build: the parameter registry loaded 73 of 192 rows because parameter
numbers were stored as text, and the FK registry dropped 3 rows because eq_id
was used as a key when it is not unique. Both were found by hand. Comparing
the row count in the file against the row count in the table makes that class
of defect fail the load instead.

WHY VERSIONING IS ONE STEP RATHER THAN A LINE IN EACH LOADER. Every registry
is then versioned by the same code, and a new registry that forgets to call
it fails a test that iterates this table -- rather than being versioned
correctly by eleven independent copies of two lines until the twelfth is
written differently.
"""
import json
from pathlib import Path

from sahacore.db import get_connection
from sahacore.registry_version import record_version

DATA_DIR = Path(__file__).parent

# registry table -> (json file, how to get the rows out of it, source sheet).
#
# The source sheet is the one the extractor's own module docstring names, so
# a version can always be traced back to a place in the workbook.
REGISTRIES: dict[str, tuple[str, str | None, str]] = {
    "engine_internal.nutrients":
        ("nutrients_81.json", None, "P1 Nutrients 81"),
    "engine_internal.state_vector":
        ("state_vector_219.json", None, "★ State Vector v33 (219); P1 Variables 219"),
    "engine_internal.cluster_scoring_params":
        ("cluster_scoring_params_12.json", None, "P1 Clusters 81x12"),
    "engine_internal.nutrient_cluster_weights":
        ("nutrient_cluster_weights.json", None, "REG · Nutrient×Cluster Long"),
    "engine_internal.damage_registry_canonical":
        ("damage_registry_canonical.json", None, "★ Damage Registry — Canonical"),
    "engine_internal.layer_m_scarring_params":
        ("layer_m_scarring_params_12.json", None, "M-PARAM Registry"),
    "engine_internal.qssa_atp_complexes":
        ("qssa_atp_complexes_5.json", None, "P1 QSSA ATP-GSH-NAD"),
    "engine_internal.replay_lag_policy":
        ("ledger_replay_policy.json", None, "Replay Contract"),
    "engine_internal.parameter_registry":
        ("parameter_registry_192.json", None, "P1 Parameters 134+"),
    "engine_internal.eq_param_fk":
        ("eq_param_fk.json", None, "PARAM · Eq Param FK"),
    "engine_internal.eq_build_rows":
        ("eq_build_rows.json", None, "EQ · Canonical Build Rows"),
    "engine_internal.veto_message":
        ("veto_messages.json", None, "MERGE·VETO FDA Messages"),
    "engine_internal.veto_drug_nutrient":
        ("veto_drug_nutrient_339.json", None, "MERGE·VETO Drug-Nutrient 339"),
    "engine_internal.action_space":
        ("action_space_127.json", "actions", "Action_Space"),
    "engine_internal.action_space_info":
        ("action_space_127.json", "info_actions", "Action_Space"),
    "engine_internal.action_space_phase":
        ("action_space_127.json", "phases", "Action_Space"),
    "engine_internal.runtime_invariant":
        ("runtime_invariants.json", None, "00_ENGINEER_START"),
    "engine_internal.parameter_registry_ext20":
        ("param_registry_ext20.json", None, "★ Param Registry +20"),
    "engine_internal.nutrient_class":
        ("nutrient_classes.json", "classes", "★ Nutrient Class Registry"),
    "engine_internal.nutrient_class_assignment":
        ("nutrient_classes.json", "nutrients", "★ Nutrient Class Registry"),
    "engine_internal.supplement_registry":
        ("supplement_registry.json", None, "★ Supplement Registry"),
    "engine_internal.equation_backbone":
        ("equation_backbone.json", None, "★ Equation Backbone"),
    "engine_internal.datamap_variable":
        ("datamap.json", "variables", "P1 DataMap section A"),
    "engine_internal.datamap_onboarding_field":
        ("datamap.json", "onboarding_fields", "P1 DataMap section B"),
    "engine_internal.organ_system":
        ("organ_registries.json", "sys_registry", "★ SYS Registry (organs)"),
    "engine_internal.organ_pathway_weight":
        ("organ_registries.json", "organ_pathway", "REG · Organ×Pathway Long"),
    "engine_internal.nutrient_target":
        ("organ_registries.json", "targets", "★ Target Registry (versioned)"),
    "engine_internal.core_equation":
        ("core_equations.json", None, "P1 Core Equations"),
    "engine_internal.state_admission_constant":
        ("state_admission.json", "gate_constants", "03_STATE_ADMISSION_GATES"),
    "engine_internal.state_admission_candidate":
        ("state_admission.json", "candidates", "03_STATE_ADMISSION_GATES"),
    "engine_internal.state_admission_rule":
        ("state_admission.json", "admission_rules", "03_STATE_ADMISSION_GATES"),
    "engine_internal.behavior_sidecar_constant":
        ("state_admission.json", "sidecar_constants", "04_BEHAVIOR_SIDECAR"),
    "engine_internal.behavior_sidecar_routing":
        ("state_admission.json", "routing", "04_BEHAVIOR_SIDECAR"),
    "engine_internal.behavior_sidecar_feature":
        ("state_admission.json", "derived_features", "04_BEHAVIOR_SIDECAR"),
    "engine_internal.bistability_cap":
        ("bistability_guard.json", "caps", "★ Scarring Bistability Guard"),
    "engine_internal.bistability_probabilistic_guard":
        ("bistability_guard.json", "probabilistic_guards",
         "★ Scarring Bistability Guard"),
    "engine_internal.verification_lab":
        ("verification_labs.json", "labs", "Live Verification Lab"),
    "engine_internal.verification_zoh_gain":
        ("verification_labs.json", "zoh_grid", "Live Verification Lab"),
    "engine_internal.verification_topology_vector":
        ("verification_labs.json", "topology_vectors", "Live Verification Lab"),
    "engine_internal.layer_m_rule":
        ("verification_labs.json", "layer_m_rules", "Live Verification Lab"),
    "engine_internal.validation_test":
        ("validation_battery.json", "tests", "★ Validation Test Battery"),
    "engine_internal.validation_section":
        ("validation_battery.json", "sections", "★ Validation Test Battery"),
    "engine_internal.scoped_build_prerequisite":
        ("scoped_builds.json", "prerequisites", "★ Scoped Builds — LTMLE Bandit"),
    "engine_internal.founder_decision":
        ("scoped_builds.json", "open_decisions", "★ Scoped Builds — LTMLE Bandit"),
    "engine_internal.onboarding_step":
        ("onboarding_canonical.json", "steps", "O · Onboarding Canonical"),
    "engine_internal.onboarding_state_block":
        ("onboarding_canonical.json", "declared_blocks", "O · Onboarding Canonical"),
    "engine_internal.onboarding_o1_equation":
        ("onboarding_o1.json", "equations", "O·O1 Anthropometrics"),
    "engine_internal.onboarding_o1_parameter":
        ("onboarding_o1.json", "parameters", "O·O1 Anthropometrics"),
    "engine_internal.onboarding_o2_equation":
        ("onboarding_o2.json", "equations", "O·O2 MVPA Prior"),
    "engine_internal.onboarding_o2_encoding":
        ("onboarding_o2.json", "input_encoding", "O·O2 MVPA Prior"),
    "engine_internal.activity_catalogue":
        ("activities_50.json", "activities", "P1 Activities 50"),
    "engine_internal.tvmcd_pathway":
        ("tvmcd_pathways_build.json", "pathways", "TVMCD · 15 Pathways Build"),
    "engine_internal.onboarding_o3_equation":
        ("onboarding_o3.json", "equations", "O·O3 Sleep Deficit"),
    "engine_internal.onboarding_o4_item":
        ("onboarding_o4.json", "items", "O·O4 Stress Index"),
    "engine_internal.onboarding_o4_equation":
        ("onboarding_o4.json", "equations", "O·O4 Stress Index"),
    "engine_internal.onboarding_o4_band":
        ("onboarding_o4.json", "bands", "O·O4 Stress Index"),
    "engine_internal.onboarding_step_question_step":
        ("step_questions.json", "steps", "O·Step-by-Step Questions"),
    "engine_internal.onboarding_step_question":
        ("step_questions.json", "questions", "O·Step-by-Step Questions"),
    "engine_internal.onboarding_o5_equation":
        ("onboarding_o5.json", "equations", "O·O5 Substance Exposure"),
    "engine_internal.onboarding_o5_encoding":
        ("onboarding_o5.json", "encodings", "O·O5 Substance Exposure"),
    "engine_internal.onboarding_o6_equation":
        ("onboarding_o6.json", "equations", "O·O6 Family History"),
    "engine_internal.onboarding_o6_condition":
        ("onboarding_o6.json", "conditions", "O·O6 Family History"),
    "engine_internal.onboarding_o7_equation":
        ("onboarding_o7.json", "equations", "O·O7 Diet Pattern Priors"),
    "engine_internal.onboarding_o7_pattern":
        ("onboarding_o7.json", "patterns", "O·O7 Diet Pattern Priors"),
    "engine_internal.onboarding_o8_condition":
        ("onboarding_o8.json", "conditions", "O·O8 Condition Modifiers"),
    "engine_internal.onboarding_o9_interaction":
        ("onboarding_o9.json", "interactions", "O·O9 Drug-Nutrient Mods"),
}


def _rows(filename: str, key: str | None) -> list[dict]:
    data = json.loads((DATA_DIR / filename).read_text(encoding="utf-8"))
    return data[key] if key else data


def record_all() -> list[tuple[str, int, bool]]:
    conn = get_connection()
    results = []
    try:
        for registry, (filename, key, sheet) in REGISTRIES.items():
            rows = _rows(filename, key)
            with conn.cursor() as cur:
                cur.execute(f"SELECT count(*) AS n FROM {registry}")
                in_db = cur.fetchone()["n"]
            if in_db != len(rows):
                raise SystemExit(
                    f"{registry}: {len(rows)} rows in {filename} but {in_db} in the "
                    "database. Refusing to record a version for content that was "
                    "not loaded -- run the loader, and if it already ran, it "
                    "dropped rows."
                )
            version_no, _, is_new = record_version(
                registry, rows, source_sheet=sheet, source_file=filename, conn=conn)
            results.append((registry, version_no, is_new))
        conn.commit()
    finally:
        conn.close()
    return results


if __name__ == "__main__":
    results = record_all()
    new = sum(1 for _, _, is_new in results if is_new)
    for registry, version_no, is_new in results:
        print(f"   {'NEW ' if is_new else '    '}v{version_no}  {registry}")
    print(f"versioned {len(results)} registries ({new} new, "
          f"{len(results) - new} unchanged)")
