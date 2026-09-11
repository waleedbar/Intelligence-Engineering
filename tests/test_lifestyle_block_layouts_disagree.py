"""The v12 and v33 lifestyle layouts, and why one sheet's numbers cannot be
joined to the other's state indices.

'P1 UKF State Detail' (manifest order 34, not yet imported) carries Layer E's
tuning constants, including a Q_diag per lifestyle state. Those numbers are
keyed to a v12 layout. The canonical state vector this build loads is v33.
The pair CATEGORIES agree -- activity, sleep, stress, hydration, meal timing,
supplements, medication, alcohol, smoking, caffeine, fasting, mood, in that
order -- and the units do not.

Hydration is the one that would hurt: Section D's Q_diag is 10000 for a state
measured in mL, so sigma = 100 mL. The canonical state is in L/day. Attaching
one to the other is an error of 10^6, in the direction that makes the filter
ignore every hydration measurement it ever sees.

These tests pin the canonical side only. The v12 numbers are quoted as
literals here rather than read from the sheet, because the sheet is not
imported -- when it is, this file should read them and the comparison becomes
real. See docs/parameter-gaps.md.
"""
import json
from pathlib import Path

import pytest

DATA_DIR = Path(__file__).parent.parent / "sahacore" / "data"


@pytest.fixture(scope="module")
def lifestyle():
    states = json.loads(
        (DATA_DIR / "state_vector_219.json").read_text(encoding="utf-8"))
    return {s["idx"]: s for s in states if 187 <= s["idx"] <= 210}


def test_the_lifestyle_block_is_twenty_four_states_in_twelve_pairs(lifestyle):
    assert len(lifestyle) == 24
    assert all(s["block"] == "lifestyle" for s in lifestyle.values())


# What the canonical v33 layout says, against what 'P1 UKF State Detail'
# Section D says the same slot holds. Second column is the v12 reading.
DISAGREEMENTS = [
    (187, "MVPA_smooth",      "min/wk",  "MET-minutes daily",   "MET·min"),
    (188, "SED_smooth",       "min/day", "MVPA minutes/day",    "min"),
    (193, "hydration_smooth", "L/day",   "Intake volume",       "mL"),
    (201, "alcohol_smooth",   "g/day",   "Units per week",      "units"),
    (203, "smoking_status",   "pack-yr", "Cigarettes per day",  "count"),
]


@pytest.mark.parametrize("idx,symbol,unit,v12_name,v12_unit", DISAGREEMENTS)
def test_the_canonical_slot_is_not_what_the_v12_table_calls_it(
        lifestyle, idx, symbol, unit, v12_name, v12_unit):
    """If any of these ever starts matching, the layouts have been reconciled
    and the warning in docs/parameter-gaps.md needs rewriting -- which is a
    better failure than a silent unit error."""
    state = lifestyle[idx]
    assert state["symbol"] == symbol
    assert state["unit"] == unit
    assert unit != v12_unit, (
        f"slot {idx} now agrees with the v12 table; re-read the finding")


def test_hydration_is_the_dangerous_one(lifestyle):
    """Named on its own because the magnitude is what makes it dangerous.
    Section D's Q_diag 10000 is (100 mL)^2. The canonical state is L/day, so
    the same number read there is (100 L/day)^2 -- 10^6 too large, which does
    not make the filter noisy, it makes it deaf."""
    assert lifestyle[193]["unit"] == "L/day"
    v12_sigma_ml = 10000 ** 0.5
    assert v12_sigma_ml == 100
    assert (v12_sigma_ml / 1000) == 0.1          # the same width, in L
    # A litre-denominated state given the millilitre variance is out by 10^6.
    assert (v12_sigma_ml / (v12_sigma_ml / 1000)) ** 2 == 10 ** 6
