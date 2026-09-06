"""Pure-data tests for sahacore/data/state_vector_219.json.

These lock in the block map from Dr. Ali's v39sEng2 workbook, sheet
'★ State Vector v33 (219)' (section 1, BLOCK MAP), so a future edit to the
seed files can't silently drift from the authoritative source. No database
is needed to run these.
"""
import json
from pathlib import Path

import pytest

DATA_DIR = Path(__file__).parent.parent / "sahacore" / "data"

# (block, first_index, last_index, is_nonlinear) -- verbatim from the source sheet.
BLOCK_MAP = [
    ("C_fast",    1,   81,  False),
    ("C_slow",    82,  162, False),
    ("xi_hi",     163, 174, True),
    ("xi_lo",     175, 186, True),
    ("lifestyle", 187, 210, True),
    ("N1",        211, 213, True),
    ("N2",        214, 214, False),
    ("N3",        215, 216, True),
    ("N4",        217, 218, True),
    ("N5",        219, 219, False),
]


@pytest.fixture(scope="module")
def states() -> list[dict]:
    return json.loads((DATA_DIR / "state_vector_219.json").read_text(encoding="utf-8"))


def test_has_exactly_219_entries(states):
    assert len(states) == 219


def test_indices_are_1_to_219_with_no_gaps_or_duplicates(states):
    assert sorted(s["idx"] for s in states) == list(range(1, 220))


def test_linear_and_nonlinear_totals_match_source(states):
    """The source sheet states 164 linear + 55 nonlinear = 219 total."""
    linear = sum(1 for s in states if not s["is_nonlinear"])
    nonlinear = sum(1 for s in states if s["is_nonlinear"])
    assert linear == 164
    assert nonlinear == 55


@pytest.mark.parametrize("block,lo,hi,is_nonlinear", BLOCK_MAP)
def test_block_occupies_its_declared_index_range(states, block, lo, hi, is_nonlinear):
    block_states = [s for s in states if s["block"] == block]
    assert len(block_states) == hi - lo + 1
    assert {s["idx"] for s in block_states} == set(range(lo, hi + 1))
    assert all(s["is_nonlinear"] == is_nonlinear for s in block_states)


def test_nitrate_is_the_81st_fast_and_162nd_slow_state(states):
    """Source note: 'nitrate_mg added at index 81' in the C_fast block."""
    idx_81 = next(s for s in states if s["idx"] == 81)
    idx_162 = next(s for s in states if s["idx"] == 162)
    assert idx_81["symbol"] == "nitrate_mg"
    assert idx_162["symbol"] == "nitrate_mg"


def test_c_fast_and_c_slow_carry_the_same_81_nutrients_in_the_same_order(states):
    fast = [s["symbol"] for s in states if s["block"] == "C_fast"]
    slow = [s["symbol"] for s in states if s["block"] == "C_slow"]
    assert fast == slow
    assert len(set(fast)) == 81


def test_nutrient_code_set_only_for_exposure_blocks(states):
    for s in states:
        if s["block"] in ("C_fast", "C_slow"):
            assert s["nutrient_code"] is not None
        else:
            assert s["nutrient_code"] is None


def test_cluster_and_side_set_only_for_damage_blocks(states):
    for s in states:
        if s["block"] in ("xi_hi", "xi_lo"):
            assert s["cluster_id"] is not None
            assert s["side"] == ("hi" if s["block"] == "xi_hi" else "lo")
        else:
            assert s["cluster_id"] is None
            assert s["side"] is None


def test_xi_hi_and_xi_lo_each_cover_all_12_clusters_exactly_once(states):
    clusters = {f"C{i}" for i in range(1, 13)}
    for block in ("xi_hi", "xi_lo"):
        block_clusters = [s["cluster_id"] for s in states if s["block"] == block]
        assert sorted(block_clusters, key=lambda c: int(c[1:])) == sorted(clusters, key=lambda c: int(c[1:]))
        assert len(block_clusters) == len(set(block_clusters)) == 12
