"""Pure-data tests for sahacore/data/layer_m_scarring_params_12.json.

Source: v39sEng2.xlsx, sheet 'M-PARAM Registry', rows 47-60 (theta_elastic,
RATIFIED) and rows 30-43 (per-cluster bistability caps: gamma_scar,
max_alpha_beta_ratio, bound_gamma_r). No database needed.
"""
import json
from pathlib import Path

import pytest

DATA_FILE = Path(__file__).parent.parent / "sahacore" / "data" / "layer_m_scarring_params_12.json"
VALID_CLUSTERS = {f"C{i}" for i in range(1, 13)}
VALID_TIERS = {"STRONG", "MOD-STRONG", "MODERATE"}


@pytest.fixture(scope="module")
def registry() -> list[dict]:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def test_has_exactly_12_clusters(registry):
    assert len(registry) == 12
    assert {r["cluster_id"] for r in registry} == VALID_CLUSTERS


def test_theta_elastic_is_positive_and_within_the_ratified_band(registry):
    """Source states the ratified band is 40-70 AU."""
    for r in registry:
        assert 40 <= r["theta_elastic_au"] <= 70, r["cluster_id"]


def test_theta_elastic_evidence_tiers_are_known(registry):
    for r in registry:
        assert r["theta_elastic_evidence_tier"] in VALID_TIERS, r["cluster_id"]


def test_gamma_scar_is_one_of_the_two_documented_values(registry):
    """Source: 'gamma_scar,k: 0.4-1.6 (metab~0.6, hep~1.2)' -- every real
    cluster in the bistability table uses exactly 0.6 or 1.2."""
    for r in registry:
        assert r["gamma_scar"] in (0.6, 1.2), r["cluster_id"]


def test_max_alpha_beta_ratio_and_bound_gamma_r_are_positive(registry):
    for r in registry:
        assert r["max_alpha_beta_ratio"] > 0, r["cluster_id"]
        assert r["bound_gamma_r"] > 0, r["cluster_id"]


def test_bound_gamma_r_equals_gamma_scar_times_max_alpha_beta_ratio(registry):
    """The source's own relationship: 'bound on gamma*r' = gamma_scar *
    max_alpha_beta_ratio -- verified here to catch a future transcription
    slip rather than trusting it silently. abs tolerance because the source
    itself rounds both factors and the product to 2 decimal places."""
    for r in registry:
        assert r["bound_gamma_r"] == pytest.approx(
            r["gamma_scar"] * r["max_alpha_beta_ratio"], abs=0.01
        ), r["cluster_id"]
