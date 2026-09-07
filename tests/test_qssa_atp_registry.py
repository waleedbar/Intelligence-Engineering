"""Pure-data tests for sahacore/data/qssa_atp_complexes_5.json.

Source: v39sEng2.xlsx, sheet 'P1 QSSA ATP-GSH-NAD', rows 13-18. No
database needed.
"""
import json
from pathlib import Path

import pytest

DATA_FILE = Path(__file__).parent.parent / "sahacore" / "data" / "qssa_atp_complexes_5.json"


@pytest.fixture(scope="module")
def registry() -> list[dict]:
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def test_has_exactly_5_complexes(registry):
    assert len(registry) == 5
    assert {r["complex_id"] for r in registry} == {"I", "II", "III", "IV", "V"}


def test_km_and_vmax_are_strictly_positive(registry):
    for r in registry:
        assert r["km_um"] > 0, r["complex_id"]
        assert r["vmax_relative"] > 0, r["complex_id"]


def test_every_complex_has_a_named_literature_source(registry):
    for r in registry:
        assert r["source"], r["complex_id"]
        assert r["substrate"], r["complex_id"]


def test_complex_i_is_the_vmax_reference_at_1_0(registry):
    """Source: 'F14: 1.0 (reference)' -- Complex I defines the relative
    Vmax scale everything else is expressed against."""
    complex_i = next(r for r in registry if r["complex_id"] == "I")
    assert complex_i["vmax_relative"] == 1.0
