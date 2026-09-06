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


def test_absorption_kernel_is_flagged_as_phase1_approximation():
    """See sahacore/engine/absorption.py module docstring: this is a known,
    documented approximation pending Dr. Ali's confirmation of the missing
    k2/lambda2/w_i values for the full two-component A1 mixture."""
    from sahacore.engine.absorption import PHASE_1_ABSORPTION_KERNEL_IS_SINGLE_GAMMA_APPROXIMATION
    assert PHASE_1_ABSORPTION_KERNEL_IS_SINGLE_GAMMA_APPROXIMATION is True


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
