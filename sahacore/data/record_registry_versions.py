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
