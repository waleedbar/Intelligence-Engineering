"""Pure-data tests for the Layer C/D registries added in
cluster_scoring_params_12.json, nutrient_cluster_weights.json, and
damage_registry_canonical.json. No database needed.

Sources: v39sEng2.xlsx sheets 'P1 Clusters 81x12' (Section B, cluster
scoring params), 'REG · Nutrient×Cluster Long' (357 weight rows), and
'★ Damage Registry — Canonical' (108 rows, explicitly supersedes the older
Section C of 'P1 Clusters 81x12').
"""
import json
from collections import defaultdict
from pathlib import Path

import pytest

DATA_DIR = Path(__file__).parent.parent / "sahacore" / "data"
VALID_CLUSTERS = {f"C{i}" for i in range(1, 13)}


@pytest.fixture(scope="module")
def nutrient_ids() -> set[str]:
    nutrients = json.loads((DATA_DIR / "nutrients_81.json").read_text(encoding="utf-8"))
    return {n["id"] for n in nutrients}


@pytest.fixture(scope="module")
def cluster_scoring_params() -> list[dict]:
    return json.loads((DATA_DIR / "cluster_scoring_params_12.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def nutrient_cluster_weights() -> list[dict]:
    return json.loads((DATA_DIR / "nutrient_cluster_weights.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def damage_registry() -> list[dict]:
    return json.loads((DATA_DIR / "damage_registry_canonical.json").read_text(encoding="utf-8"))


# --- cluster_scoring_params_12.json ---

def test_has_exactly_12_clusters(cluster_scoring_params):
    assert len(cluster_scoring_params) == 12
    assert {c["cluster_id"] for c in cluster_scoring_params} == VALID_CLUSTERS


def test_rho_k_is_a_valid_decay_factor(cluster_scoring_params):
    for c in cluster_scoring_params:
        assert 0 < c["rho_k"] <= 1
        assert c["tau_dam_days"] > 0


# --- nutrient_cluster_weights.json ---

def test_has_exactly_357_nonzero_weights(nutrient_cluster_weights):
    assert len(nutrient_cluster_weights) == 357


def test_weight_rows_reference_known_nutrients_and_clusters(nutrient_cluster_weights, nutrient_ids):
    for row in nutrient_cluster_weights:
        assert row["nutrient_id"] in nutrient_ids
        assert row["cluster_id"] in VALID_CLUSTERS
        assert 0 < row["weight"] <= 1


def test_no_duplicate_nutrient_cluster_pairs(nutrient_cluster_weights):
    pairs = [(r["nutrient_id"], r["cluster_id"]) for r in nutrient_cluster_weights]
    assert len(pairs) == len(set(pairs))


def test_each_cluster_column_sums_to_one(nutrient_cluster_weights):
    """Battery test I8, 'REG column simplex after nitrate', BLOCKING:
    'Sum each cluster column of REG · Nutrient×Cluster Long. All twelve
    columns sum to 1.000000.'

    This was written at abs=1e-4 before '★ Validation Test Battery' was
    imported. The battery asks for six decimal places, and the data has
    always met it -- the twelve sums differ from 1.0 by at most 4e-16, which
    is float addition order, not a data error. Held to the battery now.
    """
    sums = defaultdict(float)
    for row in nutrient_cluster_weights:
        sums[row["cluster_id"]] += row["weight"]
    for cluster in VALID_CLUSTERS:
        assert sums[cluster] == pytest.approx(1.0, abs=1e-9), f"{cluster}: sum={sums[cluster]}"


# --- damage_registry_canonical.json ---

def test_has_exactly_108_rows(damage_registry):
    assert len(damage_registry) == 108


def test_rows_reference_known_nutrients_and_clusters(damage_registry, nutrient_ids):
    for row in damage_registry:
        assert row["nutrient_id"] in nutrient_ids
        assert row["cluster_id"] in VALID_CLUSTERS


def test_no_duplicate_cluster_nutrient_pairs(damage_registry):
    pairs = [(r["cluster_id"], r["nutrient_id"]) for r in damage_registry]
    assert len(pairs) == len(set(pairs))


def test_each_cluster_weight_pct_sums_to_100(damage_registry):
    """Battery test I7, '81×12 column simplex', BLOCKING: 'Sum each cluster
    column of the canonical damage registry. All twelve columns sum to 100.0
    exactly.'

    This was written at abs=1e-2 before '★ Validation Test Battery' was
    imported. The battery says exactly, and all twelve do -- each sum is the
    float 100.0, not merely close to it. A tolerance of 1e-2 would have
    accepted a column that was 0.5% wrong.
    """
    sums = defaultdict(float)
    for row in damage_registry:
        sums[row["cluster_id"]] += row["weight_pct"]
    for cluster in VALID_CLUSTERS:
        assert sums[cluster] == 100.0, f"{cluster}: sum={sums[cluster]!r}"


def test_theta_hi_and_theta_lo_are_null_together_only_for_c7_and_c9(damage_registry):
    """Per the source sheet's own note: C7 (Methylation) and C9 (Neuro-Hormonal)
    were newly authored and their thresholds are derived from a dynamic
    mechanistic sub-model rather than a fixed constant -- not a data gap."""
    for row in damage_registry:
        is_null = row["theta_hi"] is None
        assert is_null == (row["theta_lo"] is None)
        if is_null:
            assert row["cluster_id"] in ("C7", "C9")


def test_positive_persistence_and_sensitivity_params(damage_registry):
    for row in damage_registry:
        assert row["tau_damage_days"] > 0
        assert row["tau_heal_days"] > 0
        assert row["eta_hi"] >= 0
        assert row["eta_lo"] >= 0
