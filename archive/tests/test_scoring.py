"""Tests for sahacore/engine/scoring.py (Layer D, equations D1/D2/D4).

Source: v39sEng2.xlsx, sheet 'P1 Core Equations', rows D1/D2/D4; D4
cross-checked against 'EQ · Canonical Build Rows' row D-002 (BUILD_LOCKED).
"""
import json
import math
from pathlib import Path

import pytest

from sahacore.engine.scoring import (
    band_for_score,
    composite_health_score,
    disruption_score,
    wellness_score,
)

DATA_DIR = Path(__file__).parent.parent / "sahacore" / "data"


@pytest.fixture(scope="module")
def cluster_params() -> list[dict]:
    return json.loads((DATA_DIR / "cluster_scoring_params_12.json").read_text(encoding="utf-8"))


def test_disruption_score_at_zero_damage_matches_closed_form():
    """z_k=0 -> ln(1+0)=0 -> D_k = 100/(1+exp(-b_k)) exactly."""
    a_k, b_k = 1.4, -2.8
    expected = 100.0 / (1.0 + math.exp(-b_k))
    assert disruption_score(0.0, a_k, b_k) == pytest.approx(expected)


@pytest.mark.parametrize("z_k", [0, 1, 10, 100, 1000])
def test_disruption_score_is_bounded_0_100(z_k):
    d = disruption_score(z_k, a_k=1.4, b_k=-2.8)
    assert 0.0 < d < 100.0


def test_disruption_score_increases_with_damage_for_positive_a_k():
    a_k, b_k = 1.4, -2.8
    scores = [disruption_score(z, a_k, b_k) for z in [0, 1, 5, 20, 100]]
    assert scores == sorted(scores)


def test_wellness_score_is_100_minus_disruption():
    for d in [0, 25, 50, 75, 100]:
        assert wellness_score(d) == pytest.approx(100 - d)


@pytest.mark.parametrize(
    "score,expected_label",
    [
        (100, "Optimal"), (80, "Optimal"),
        (79.999, "Build"), (60, "Build"),
        (59.999, "Focus"), (40, "Focus"),
        (39.999, "Reach Out"), (0, "Reach Out"), (-10, "Reach Out"),
    ],
)
def test_band_boundaries_match_d2_exactly(score, expected_label):
    label, _color = band_for_score(score)
    assert label == expected_label


def test_band_colors_match_d2_hex_codes_exactly():
    assert band_for_score(90)[1] == "#5FC79A"
    assert band_for_score(70)[1] == "#325356"
    assert band_for_score(50)[1] == "#E0A05A"
    assert band_for_score(20)[1] == "#E8735A"


def test_lowest_band_is_never_red_and_never_clinically_framed():
    """Locks in decision D-Q1, which the source says v35.9 violated: the
    lowest band must render as supportive coral, never red, and its label
    must never read as clinical framing."""
    label, color = band_for_score(10)
    assert label == "Reach Out"
    assert color == "#E8735A"
    assert "red" not in color.lower()
    assert "clinical" not in label.lower()


def test_every_band_label_and_color_is_unique():
    from sahacore.engine.scoring import BANDS
    labels = [b[0] for b in BANDS]
    colors = [b[1] for b in BANDS]
    assert len(labels) == len(set(labels)) == 4
    assert len(colors) == len(set(colors)) == 4


def test_all_12_real_clusters_produce_valid_bounded_scores(cluster_params):
    for cluster in cluster_params:
        for z_k in [0, 1, 10, 100]:
            d = disruption_score(z_k, cluster["a_k"], cluster["b_k"])
            assert 0.0 < d < 100.0, f"{cluster['cluster_id']} at z_k={z_k}: D_k={d}"
            score = wellness_score(d)
            label, color = band_for_score(score)
            assert label in {"Optimal", "Build", "Focus", "Reach Out"}


# --- D4: composite health score --------------------------------------------

def test_composite_health_score_is_weighted_average_of_cluster_scores():
    scores = {"C1": 80.0, "C2": 60.0}
    weights = {"C1": 1.0, "C2": 3.0}
    expected = (1.0 * 80.0 + 3.0 * 60.0) / (1.0 + 3.0)
    assert composite_health_score(scores, weights) == pytest.approx(expected)


def test_composite_health_score_with_equal_weights_is_the_plain_mean():
    scores = {"C1": 90.0, "C2": 70.0, "C3": 50.0}
    weights = {"C1": 1.0, "C2": 1.0, "C3": 1.0}
    assert composite_health_score(scores, weights) == pytest.approx((90.0 + 70.0 + 50.0) / 3.0)


def test_composite_health_score_matches_the_100_minus_disruption_form():
    """Algebraic equivalence with the 'P1 Core Equations' D4 form: CHS =
    100 - SUM(w*D_k)/SUM(w), where D_k = 100 - Score_k."""
    scores = {"C1": 72.0, "C2": 55.0, "C3": 90.0}
    weights = {"C1": 2.0, "C2": 1.0, "C3": 4.0}
    disruptions = {cid: 100.0 - s for cid, s in scores.items()}
    via_scores = composite_health_score(scores, weights)
    total_weight = sum(weights.values())
    via_disruption = 100.0 - sum(weights[c] * disruptions[c] for c in disruptions) / total_weight
    assert via_scores == pytest.approx(via_disruption)


def test_composite_health_score_is_bounded_by_the_min_and_max_cluster_score():
    scores = {"C1": 30.0, "C2": 90.0, "C3": 60.0}
    weights = {"C1": 0.5, "C2": 0.2, "C3": 0.3}
    result = composite_health_score(scores, weights)
    assert min(scores.values()) <= result <= max(scores.values())


def test_composite_health_score_uses_all_12_real_cluster_ids_with_synthetic_weights(cluster_params):
    """Real fixed_weight_k values aren't populated in the source yet (see
    the module docstring's data-gap note), so this exercises the function
    against the real 12 cluster IDs with a synthetic-but-valid weighting to
    confirm it composes correctly end to end, not against invented physiology."""
    cluster_ids = [c["cluster_id"] for c in cluster_params]
    assert len(cluster_ids) == 12
    scores = {cid: 75.0 for cid in cluster_ids}
    weights = {cid: 1.0 for cid in cluster_ids}
    assert composite_health_score(scores, weights) == pytest.approx(75.0)
