"""Tests for sahacore/engine/absorption.py (Layer A, equation A1).

Includes a golden-value regression test transcribed directly from Dr.
Ali's own workbook ('Live Verification Lab', LAB 1), so our implementation
is checked against a number the source itself already verified -- not just
against our own derivation.
"""
import json
import math
from pathlib import Path

import pytest
from scipy.stats import gamma as scipy_gamma

from sahacore.engine.absorption import absorption_kernel, gamma_pdf

NUTRIENTS_FILE = Path(__file__).parent.parent / "sahacore" / "data" / "nutrients_81.json"


@pytest.fixture(scope="module")
def nutrients() -> list[dict]:
    return json.loads(NUTRIENTS_FILE.read_text(encoding="utf-8"))


def test_matches_live_verification_lab_worked_example():
    """Source: v39sEng2.xlsx, sheet 'Live Verification Lab', LAB 1, row 16
    (t=10, k1 fast shape=2.5, lambda1 fast rate=0.04 -> f_fast=0.005102652414604033).
    This is the source workbook's OWN pre-computed reference value."""
    value = gamma_pdf(10, k=2.5, lam=0.04)
    assert value == pytest.approx(0.005102652414604033, rel=1e-9)


@pytest.mark.parametrize(
    "t,expected",
    [
        (10, 0.005102652414604033),
        (50, 0.011518072856146798),
        (100, 0.004408956875539648),
        (250, 4.319952509914196e-05),
    ],
)
def test_matches_live_verification_lab_at_several_timepoints(t, expected):
    """Cross-checks our f_fast column against several rows of the same LAB 1 table."""
    assert gamma_pdf(t, k=2.5, lam=0.04) == pytest.approx(expected, rel=1e-9)


def test_zero_or_negative_time_gives_zero_density():
    assert gamma_pdf(0, k=2.5, lam=0.04) == 0.0
    assert gamma_pdf(-5, k=2.5, lam=0.04) == 0.0


def test_lambda_equals_inverse_theta_for_every_real_nutrient(nutrients):
    """Source: v39sEng2.xlsx, sheet 'P1 MC Engine', section D audit row
    'lambda = 1/theta for all 81 nutrients | 81/81 | PASS' -- this is the
    workbook's own record of the corrected single-gamma parameterization
    (section F, correction #1: shape-scale -> shape-rate, lambda = 1/theta),
    re-verified here against our own registry copy.

    Five nutrients are documented exceptions, all confirmed by direct
    re-read of the raw 'P1 Nutrients 81' sheet (not an extraction error
    here) despite the audit log's 81/81 claim:
      - nitrate_mg: lambda=0.0333 vs 1/theta=0.033333... -- a truncated-
        digits rounding artifact (theta=30), not a parameterization error.
      - fat_total_g, aa_tryptophan_mg, aa_aspartate_mg, aa_glutamate_mg:
        lambda doesn't correspond to 1/theta by any consistent ratio --
        genuine, isolated data inconsistencies in the source.
    Flagged explicitly rather than silently excluded."""
    exceptions = {"fat_total_g", "aa_tryptophan_mg", "aa_aspartate_mg", "aa_glutamate_mg", "nitrate_mg"}
    for nut in nutrients:
        if nut["id"] in exceptions:
            continue
        assert nut["lambda_per_min"] == pytest.approx(1.0 / nut["gamma_theta_min"], rel=1e-9), (
            f"{nut['id']}: lambda={nut['lambda_per_min']}, 1/theta={1.0 / nut['gamma_theta_min']}"
        )


def test_lambda_theta_mismatches_are_exactly_the_five_documented_nutrients(nutrients):
    """Locks in the exact shape of the known source-data inconsistencies
    (see test above) so a future registry update either fixes one (this
    test then fails, prompting removal of that exception) or the set stays
    intentional and documented -- it can't silently drift unnoticed."""
    mismatches = {
        nut["id"] for nut in nutrients
        if nut["lambda_per_min"] != pytest.approx(1.0 / nut["gamma_theta_min"], rel=1e-9)
    }
    assert mismatches == {"fat_total_g", "aa_tryptophan_mg", "aa_aspartate_mg", "aa_glutamate_mg", "nitrate_mg"}


def test_matches_scipy_reference_for_every_real_nutrient(nutrients):
    """Our hand-written log-space gamma PDF must agree with scipy's
    battle-tested implementation, for every one of the 81 real (k, lambda)
    pairs actually in the registry -- not just the demo values."""
    sample_times = [1, 10, 60, 240, 720]
    for nut in nutrients:
        k, lam = nut["gamma_k_shape"], nut["lambda_per_min"]
        for t in sample_times:
            ours = absorption_kernel(t, k, lam)
            reference = scipy_gamma.pdf(t, a=k, scale=1.0 / lam)
            assert ours == pytest.approx(reference, rel=1e-9, abs=1e-300), (
                f"{nut['id']} at t={t}: ours={ours}, scipy={reference}"
            )


def test_kernel_mass_over_full_domain_is_one_for_every_real_nutrient(nutrients):
    """A valid gamma PDF integrates to exactly 1 over (0, infinity); this
    confirms every nutrient's (k, lambda) pair is a well-formed distribution
    (using scipy's regularized incomplete gamma, i.e. the exact CDF -- no
    numerical quadrature truncation error, unlike the workbook's own
    trapezoid demo grid)."""
    for nut in nutrients:
        k, lam = nut["gamma_k_shape"], nut["lambda_per_min"]
        mass = scipy_gamma.cdf(math.inf, a=k, scale=1.0 / lam)
        assert mass == pytest.approx(1.0, abs=1e-9), f"{nut['id']}: mass={mass}"
