"""Tests for sahacore/engine/damage.py (Layer C, equation C1).

Source: v39sEng2.xlsx, sheet 'P1 Core Equations', row C1.
"""
import json
import math
from pathlib import Path

import pytest

from sahacore.engine.damage import (
    cluster_exposure,
    combined_concentration,
    deficiency_deviation,
    excess_deviation,
    softplus_deviation,
)

DATA_DIR = Path(__file__).parent.parent / "sahacore" / "data"

# Documented defaults from 'P1 Parameters 134+': s_hi,i / s_lo,i default 0.25
# (matches every nutrient's s_hi_log/s_lo_log in nutrients_81.json), tau_soft
# default 1.0. eps has no fixed default in the source (data-dependent), so
# tests use a representative small value.
TAU = 1.0
EPS = 1e-6


def test_softplus_deviation_at_zero_is_tau_ln2():
    for tau in (0.25, 0.5, 1.0):
        assert softplus_deviation(0.0, tau) == pytest.approx(tau * math.log(2), rel=1e-12)


def test_softplus_deviation_is_monotonically_increasing():
    tau = 1.0
    zs = [-5, -1, -0.1, 0, 0.1, 1, 5]
    values = [softplus_deviation(z, tau) for z in zs]
    assert values == sorted(values)


@pytest.mark.parametrize("cbar,theta", [(50, 100), (99.9, 100), (1, 100)])
def test_excess_deviation_is_exactly_zero_at_or_below_threshold(cbar, theta):
    """When Cbar <= theta_hi, z = (ln(Cbar+eps)-ln(theta_hi+eps))/s <= 0, and
    since softplus is monotonic, sp_tau(z) <= sp_tau(0), so max(0, ...) = 0
    exactly -- not approximately."""
    assert excess_deviation(cbar, theta, s_hi=0.25, tau=TAU, eps=EPS) == 0.0


@pytest.mark.parametrize("cbar,theta", [(150, 100), (100.1, 100), (1000, 100)])
def test_excess_deviation_is_positive_above_threshold(cbar, theta):
    assert excess_deviation(cbar, theta, s_hi=0.25, tau=TAU, eps=EPS) > 0.0


@pytest.mark.parametrize("cbar,theta", [(150, 100), (100.1, 100)])
def test_deficiency_deviation_is_exactly_zero_at_or_above_threshold(cbar, theta):
    assert deficiency_deviation(cbar, theta, s_lo=0.25, tau=TAU, eps=EPS) == 0.0


@pytest.mark.parametrize("cbar,theta", [(50, 100), (1, 100)])
def test_deficiency_deviation_is_positive_below_threshold(cbar, theta):
    assert deficiency_deviation(cbar, theta, s_lo=0.25, tau=TAU, eps=EPS) > 0.0


def test_excess_and_deficiency_deviation_share_the_same_shape_by_symmetry():
    """r_lo,i(Cbar=b, theta_lo=a) is defined as the same function as
    r_hi,i(Cbar=a, theta_hi=b) with arguments swapped -- verify that holds."""
    a, b, s = 120.0, 80.0, 0.25
    assert deficiency_deviation(b, a, s_lo=s, tau=TAU, eps=EPS) == pytest.approx(
        excess_deviation(a, b, s_hi=s, tau=TAU, eps=EPS)
    )


@pytest.mark.parametrize("w_fast", [0.0, 0.3, 0.5, 1.0])
def test_combined_concentration_is_the_w_fast_weighted_blend(w_fast):
    c_fast, c_slow = 10.0, 4.0
    expected = w_fast * c_fast + (1 - w_fast) * c_slow
    assert combined_concentration(c_fast, c_slow, w_fast) == pytest.approx(expected)


def test_combined_concentration_at_extremes():
    assert combined_concentration(c_fast=10.0, c_slow=4.0, w_fast=1.0) == pytest.approx(10.0)
    assert combined_concentration(c_fast=10.0, c_slow=4.0, w_fast=0.0) == pytest.approx(4.0)


def test_cluster_exposure_is_the_weighted_sum():
    deviations = {"a": 1.0, "b": 2.0, "c": 3.0}
    weights = {"a": 0.5, "b": 0.3, "c": 0.2}
    assert cluster_exposure(deviations, weights) == pytest.approx(0.5 * 1 + 0.3 * 2 + 0.2 * 3)


def test_cluster_exposure_with_real_cluster_weights_and_uniform_deviation():
    """Uses the real nutrient_cluster_weights.json for cluster C12: since
    those weights sum to exactly 1.0 (verified in
    test_layer_c_d_registries.py), giving every nutrient the same deviation
    X must yield exactly X back."""
    weights_rows = json.loads((DATA_DIR / "nutrient_cluster_weights.json").read_text(encoding="utf-8"))
    c12 = {r["nutrient_id"]: r["weight"] for r in weights_rows if r["cluster_id"] == "C12"}
    uniform_deviations = {nid: 2.5 for nid in c12}
    assert cluster_exposure(uniform_deviations, c12) == pytest.approx(2.5, rel=1e-6)
