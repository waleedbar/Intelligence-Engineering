"""Supplements and the NULL-CAP rule.

Source: v39sEng2.xlsx, sheet '★ Supplement Registry',
'01_IMPORT_MANIFEST' order 42.

The rule these tests protect is a safety rule, stated by the sheet: where the
randomised trials of a supplement are null, the engine caps its modelled
effect at zero no matter how strong the dietary evidence for the same
nutrient is. Without it, a vitamin D capsule inherits the cardiovascular
weight of the vitamin D dietary pattern -- a claim the trials do not support,
made by accident rather than by decision.
"""
import json
from pathlib import Path

import pytest

DATA_DIR = Path(__file__).parent.parent / "sahacore" / "data"


@pytest.fixture(scope="module")
def supplements() -> list[dict]:
    return json.loads((DATA_DIR / "supplement_registry.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def by_name(supplements) -> dict[str, dict]:
    return {s["supplement"]: s for s in supplements}


# --- extraction fidelity ---------------------------------------------------

def test_all_13_supplements_are_extracted(supplements):
    assert len(supplements) == 13
    assert len({s["supplement"] for s in supplements}) == 13


def test_the_build_note_is_not_read_as_a_supplement(supplements):
    """The sheet ends with a BUILD NOTE paragraph in the same column the
    supplement names occupy. Reading it as a row would add a supplement
    called "BUILD NOTE. Supplements enter the engine..."."""
    assert not any(s["supplement"].startswith("BUILD NOTE") for s in supplements)


# --- the NULL-CAP rule -----------------------------------------------------

def test_exactly_four_supplements_are_null_capped(supplements):
    """Pinned by name. Adding or removing a null cap is a safety decision,
    and a count alone would not say which one moved."""
    capped = {s["supplement"] for s in supplements
              if s["effect_cap"] and "NULL CAP" in s["effect_cap"].upper()}
    assert capped == {"CoQ10 (ubiquinone / ubiquinol)", "Vitamin D",
                      "EPA + DHA", "Curcumin"}


def test_vitamin_d_is_capped_even_though_it_maps_to_a_real_nutrient(by_name):
    """The case the whole registry exists for. Vitamin D supplementation maps
    cleanly onto vit_d_iu, so a single registry would let it inherit the
    dietary pattern's cardiovascular weight. VITAL was null, so the cap
    applies to the supplement while the nutrient keeps its adequacy role."""
    d = by_name["Vitamin D"]
    assert d["mapping_kind"] == "YES"
    assert d["maps_to_nutrients"] == ["vit_d_iu"]
    assert "NULL CAP" in d["effect_cap"]
    assert "cardiovascular" in d["effect_cap"]
    assert "Adequacy only" in d["cluster_effect_permitted"]


def test_epa_dha_is_capped_in_the_combined_form(by_name):
    epa = by_name["EPA + DHA"]
    assert set(epa["maps_to_nutrients"]) == {"omega3_epa_g", "omega3_dha_g"}
    assert "NULL CAP" in epa["effect_cap"]


def test_the_builder_refuses_a_change_to_the_null_cap_set(supplements):
    """Proven, not assumed: quietly un-capping a supplement must fail the
    build rather than change what the engine will claim."""
    from sahacore.data.build_supplement_registry import check

    rows = [dict(s) for s in supplements]
    d = next(r for r in rows if r["supplement"] == "Vitamin D")
    d["effect_cap"] = "Adequacy + repletion"
    with pytest.raises(SystemExit, match="NULL CAP set"):
        check(rows)


# --- the mapping column is classified, not parsed --------------------------

def test_every_mapped_nutrient_id_is_a_real_nutrient(supplements):
    known = {n["id"] for n in json.loads(
        (DATA_DIR / "nutrients_81.json").read_text(encoding="utf-8"))}
    for s in supplements:
        for code in s["maps_to_nutrients"]:
            assert code in known, f"{s['supplement']} maps to unknown {code!r}"


def test_a_vague_mapping_yields_no_keys_rather_than_a_guess(by_name):
    """'YES → several' says a multivitamin tops up more than one nutrient and
    does not say which. An empty list is the honest reading; picking a
    plausible set would be invention."""
    multi = by_name["Multivitamin"]
    assert multi["mapping_kind"] == "YES"
    assert multi["maps_to_nutrients"] == []
    assert "several" in multi["maps_to_canonical"]


def test_collagens_amino_acids_are_left_unlinked_and_that_is_deliberate(by_name):
    """'Partial → glycine, proline'. The nutrient registry spells these
    aa_glycine_mg and aa_proline_mg, so linking them would require an alias
    this build has not declared. The verbatim cell is kept so the link can be
    made deliberately later."""
    c = by_name["Collagen peptides"]
    assert c["mapping_kind"] == "PARTIAL"
    assert c["maps_to_nutrients"] == []
    assert "glycine" in c["maps_to_canonical"]


# --- the row the source has not finished -----------------------------------

def test_betaine_is_incomplete_in_the_source_and_is_kept_as_such(by_name):
    """One row carries a name and nothing else -- no cap, no evidence
    position, no cluster permission. Dropping it would hide a supplement the
    sheet means to cover; filling it in would invent a safety position. It is
    loaded incomplete and reported by
    engine_internal.supplement_incomplete."""
    b = by_name["Betaine (trimethylglycine / TMG)"]
    assert b["is_complete"] is False
    assert b["effect_cap"] is None
    assert b["evidence_position"] is None
    assert b["cluster_effect_permitted"] is None


def test_exactly_one_row_is_incomplete(supplements):
    """A second incomplete row would be a new gap in the source, and must
    surface rather than blend in with the known one."""
    incomplete = [s["supplement"] for s in supplements if not s["is_complete"]]
    assert incomplete == ["Betaine (trimethylglycine / TMG)"]


def test_every_complete_row_states_all_four_positions(supplements):
    for s in supplements:
        if s["is_complete"]:
            assert s["maps_to_canonical"] and s["effect_cap"]
            assert s["evidence_position"] and s["cluster_effect_permitted"]
