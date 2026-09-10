"""Layer 0's build contract, and the bridge that is not in the workbook.

Source: 'O · Onboarding Canonical' -- manifest order 128.

This is '★ Build Guide Python' step 3, one row per module. Twelve of the
fourteen steps can be written today. Two cannot, and these tests pin why, so
the blockage is a fact in the repository rather than something to be
rediscovered by whoever opens the sheet next.
"""
import json
from pathlib import Path

import pytest

DATA_DIR = Path(__file__).parent.parent / "sahacore" / "data"


@pytest.fixture(scope="module")
def canonical() -> dict:
    return json.loads(
        (DATA_DIR / "onboarding_canonical.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def state_vector() -> list[dict]:
    return json.loads(
        (DATA_DIR / "state_vector_219.json").read_text(encoding="utf-8"))


# --- the contract ----------------------------------------------------------

def test_fourteen_steps_each_naming_its_module(canonical):
    steps = canonical["steps"]
    assert [s["step_id"] for s in steps] == [f"ONB-{n:03d}" for n in range(1, 15)]
    functions = [s["python_function"] for s in steps]
    assert len(set(functions)) == 14
    assert all(f.startswith("sahacore.onboarding.") for f in functions)


def test_the_first_and_last_modules_are_what_the_build_guide_expects(canonical):
    """Step 3 of the build guide runs from anthropometrics to the control
    vector: questionnaire answers in, x0/P0/u0 out."""
    by_id = {s["step_id"]: s for s in canonical["steps"]}
    assert by_id["ONB-001"]["python_function"] == "sahacore.onboarding.anthropometrics"
    assert by_id["ONB-012"]["python_function"] == "sahacore.onboarding.state_init_219"
    assert by_id["ONB-013"]["python_function"] == "sahacore.onboarding.covariance_init"
    assert by_id["ONB-014"]["python_function"] == "sahacore.onboarding.control_input"


def test_every_step_carries_its_own_acceptance_test(canonical):
    """The QA column is what each module has to pass. A step without one
    could be written and never checked."""
    for step in canonical["steps"]:
        assert step["validation_qa"], step["step_id"]
    by_id = {s["step_id"]: s for s in canonical["steps"]}
    assert by_id["ONB-012"]["validation_qa"] == "length(x0)=219; no null locked states"
    assert by_id["ONB-013"]["validation_qa"].startswith("PSD")


def test_the_consolidated_sheet_defers_to_authorities(canonical):
    """This sheet holds one-line summaries. The real equations and parameter
    values live on the O·O* detail sheets it names, which is why every step
    carries an authority column and why ONB-011's summary alone is not enough
    to implement it -- see the bridge tests below."""
    for step in canonical["steps"]:
        assert step["authority_sheets"], step["step_id"]
        assert step["parameter_refs"], step["step_id"]


# --- the 219 layout, corroborated -----------------------------------------

def test_onb_012_slot_layout_matches_the_state_vector_registry(canonical, state_vector):
    """ONB-012 declares the layout; state_vector_219.json came from a
    different sheet, imported days earlier. They agree slot for slot.

    Two independent statements of the engine's own state agreeing is worth
    more than either one alone -- and a disagreement would be unsurvivable
    for everything downstream, so it is checked rather than assumed.
    """
    by_index = {row["idx"]: row for row in state_vector}
    assert len(by_index) == 219

    covered = 0
    for block in canonical["declared_blocks"]:
        for index in range(block["first_index"], block["last_index"] + 1):
            assert by_index[index]["block"] == block["registry_block"], index
            covered += 1
    assert covered == 219


def test_the_damage_slots_hold_the_log_coordinate_not_the_damage(canonical, state_vector):
    """The sheet writes slots 163-186 as Z_hi/Z_lo. The registry names them
    xi_hi/xi_lo with unit log(AU), and that is what the slot holds: Z is
    derived as exp(xi) - eps, never stored.

    Battery test C3, BLOCKING -- 'Damage positivity (log-coordinates)',
    criterion 'Z(t) = exp(xi) - eps >= 0' -- is what rests on the
    distinction. Writing Z into a xi slot would pass a length check and
    break positivity everywhere downstream.
    """
    blocks = {b["registry_block"]: b for b in canonical["declared_blocks"]}
    assert blocks["xi_hi"]["sheet_name"] == "Z_hi"
    assert blocks["xi_lo"]["sheet_name"] == "Z_lo"

    by_index = {row["idx"]: row for row in state_vector}
    for index in range(163, 187):
        row = by_index[index]
        assert row["unit"] == "log(AU)", index
        assert row["symbol"].startswith(("xi_hi_", "xi_lo_")), row["symbol"]
        assert row["is_nonlinear"] is True

    battery = json.loads(
        (DATA_DIR / "validation_battery.json").read_text(encoding="utf-8"))
    c3 = next(t for t in battery["tests"] if t["test_id"] == "C3")
    assert c3["gate"] == "BLOCKING"
    assert "log-coordinates" in c3["target"]


# --- the missing bridge ----------------------------------------------------

def test_twelve_of_fourteen_steps_are_buildable(canonical):
    buildable = [s["step_id"] for s in canonical["steps"] if not s["blocked_by"]]
    blocked = [s["step_id"] for s in canonical["steps"] if s["blocked_by"]]
    assert len(buildable) == 12
    assert blocked == ["ONB-011", "ONB-012"]


def test_the_two_blocked_steps_name_the_same_three_gaps(canonical):
    """ONB-011 produces fifteen pathway warm-start values. ONB-012 fills
    twelve cluster slots at 163-186 and twelve more at 175-186.

    A CORRECTION. This test used to assert that the map between them was not
    in the workbook. It is: 'TVMCD · 15 Pathways Build' gives cluster outputs
    for all fifteen pathways. The search that concluded otherwise matched
    C1..C12 and D1..D15, and that sheet writes them zero-padded -- C02, D01 --
    so it scored zero on both counts. See tests/test_tvmcd_pathways.py.

    What the map gives is membership. Three things are still missing, and
    they are what keeps these two steps blocked.
    """
    blocked = [s for s in canonical["steps"] if s["blocked_by"]]
    assert len(blocked) == 2
    reasons = {s["blocked_by"] for s in blocked}
    assert len(reasons) == 1
    reason = reasons.pop()

    assert "TVMCD · 15 Pathways Build" in reason
    assert "exists" in reason
    for gap in ("No weights", "C01 Membrane", "high and a low side"):
        assert gap in reason, gap


def test_the_organ_map_that_is_not_the_bridge_is_already_loaded(canonical):
    """'P1 Cluster Map 15-12' is titled as the bridge and is not it -- its
    rows are organ systems, as its own v35.9.3 banner says. What it holds is
    in the build already, under the name that describes it: 48 links over 13
    pathways and 12 organs, no D14 or D15, which is gate d14_d15_fail_closed
    agreeing with the data.

    That much of the earlier finding stands. What did not stand was the
    conclusion that no other sheet carried the map.
    """
    organs = json.loads(
        (DATA_DIR / "organ_registries.json").read_text(encoding="utf-8"))
    links = organs["organ_pathway"]
    assert len(links) == 48
    assert len({r["pathway_id"] for r in links}) == 13
    assert not {r["pathway_id"] for r in links} & {"D14", "D15"}


def test_pathway_ids_are_the_same_set_in_both_namespaces(canonical):
    """O·O11 numbers the fifteen pathways Z1..Z15; the rest of the workbook
    numbers them D1..D15. The names line up one for one across all fifteen,
    so the two are the same set under two spellings -- which is why the
    organ map's D-ids can be compared to O11's Z-ids at all.

    Pinned because it is the kind of identity that is obvious once seen and
    expensive to get wrong: a bridge built on the assumption that Z3 and D3
    differ would silently permute every cluster.
    """
    tvmcd = json.loads(
        (DATA_DIR / "tvmcd_pathways_15.json").read_text(encoding="utf-8"))
    assert [r["pathway_id"] for r in tvmcd] == [f"Z{n}" for n in range(1, 16)]
    assert tvmcd[0]["name"] == "Glycation/AGE"
    assert tvmcd[2]["name"] == "Inflammation"
    assert tvmcd[14]["name"] == "VitD Insufficiency"
