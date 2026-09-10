"""The fifteen TVMCD pathways, and the map an earlier commit said was missing.

Source: 'TVMCD · 15 Pathways Build' -- manifest order 131.

A CORRECTION LIVES HERE. This build reported the "canonical 15->12 bridge" as
absent from the workbook, and committed that. It is not absent: the Cluster
outputs column of this sheet gives two or three clusters for every one of the
fifteen pathways.

The search that concluded otherwise matched `C1..C12` and `D1..D15`. This
sheet writes them ZERO-PADDED -- `C02`, `D01` -- so most of them did not
match. Not all: C10, C11 and C12 need no padding, so the sheet scored 3
cluster ids and 6 pathway ids against a threshold of ten, and was passed over
for being under the bar rather than for scoring nothing. Re-run with padding
allowed it is the only sheet of the 205 carrying ten or more of each: the
conclusion "there is exactly one candidate" was right and the identification
was wrong.

What the map gives is membership. Three things are still missing, and those
are what keep ONB-011 and ONB-012 blocked.
"""
import json
import re
from pathlib import Path

import pytest

DATA_DIR = Path(__file__).parent.parent / "sahacore" / "data"


@pytest.fixture(scope="module")
def build() -> dict:
    return json.loads(
        (DATA_DIR / "tvmcd_pathways_build.json").read_text(encoding="utf-8"))


def test_fifteen_pathways_each_completely_specified(build):
    """The sheet calls itself a 'complete server implementation table'. An
    empty column would mean it is not."""
    pathways = build["pathways"]
    assert [p["pathway_id"] for p in pathways] == [f"D{n:02d}" for n in range(1, 16)]
    for pathway in pathways:
        for field in ("state_variable", "ode", "inputs", "parameters",
                      "integration_cadence", "numerical_method", "bounds",
                      "initialization"):
            assert pathway[field], (pathway["pathway_id"], field)


def test_every_pathway_holds_its_state_in_log_coordinates(build):
    """logZ_inflam, logZ_AGE, ... -- which is what keeps Z positive, and what
    battery test C3 ('Damage positivity (log-coordinates)', BLOCKING) is
    written against."""
    for pathway in build["pathways"]:
        assert pathway["state_variable"].startswith("logZ"), pathway["pathway_id"]
        assert "Z>=" in pathway["bounds"] or "log form" in pathway["bounds"]


def test_every_pathway_warm_starts_from_o11(build):
    """'from O·O11 warm-start or zero with prior covariance'. This column is
    what ties the sheet to ONB-011 -- and it points from O11 to the PATHWAY
    state, not to a cluster."""
    for pathway in build["pathways"]:
        assert "O·O11" in pathway["initialization"], pathway["pathway_id"]


# --- the map ---------------------------------------------------------------

def test_the_pathway_to_cluster_map_exists_for_all_fifteen(build):
    """THE CORRECTION. Two or three clusters per pathway, all fifteen."""
    for pathway in build["pathways"]:
        assert 2 <= len(pathway["cluster_outputs"]) <= 3, pathway["pathway_id"]
        for cluster in pathway["cluster_outputs"]:
            assert re.fullmatch(r"C(0[1-9]|1[0-2])", cluster), cluster


def test_the_ids_are_zero_padded_which_is_why_the_search_missed_it(build):
    """The mechanical reason for the wrong finding, pinned so the lesson is
    not just prose. A pattern written for `C2` and `D1` matches nothing here.
    """
    for pathway in build["pathways"]:
        assert re.fullmatch(r"D\d{2}", pathway["pathway_id"])
        assert not re.fullmatch(r"D[1-9]", pathway["pathway_id"])
    every_cluster = {c for p in build["pathways"] for c in p["cluster_outputs"]}
    assert all(re.fullmatch(r"C\d{2}", c) for c in every_cluster)

    # The search that failed, and the one that would have worked -- and the
    # failure is subtler than "it matched nothing". C10, C11 and C12 need no
    # padding, so the old pattern caught exactly those three and missed
    # C02..C09. Against a threshold of ten distinct ids the sheet scored 3,
    # which is why it was passed over: under the bar, not invisible. A rule
    # that had reported "0" would have been easier to notice.
    old = re.compile(r"\bC(1[0-2]|[1-9])\b")
    new = re.compile(r"\bC0?(1[0-2]|[1-9])\b")
    text = " ".join(p["cluster_outputs_verbatim"] for p in build["pathways"])
    assert sorted(set(old.findall(text)), key=int) == ["10", "11", "12"]
    assert len(set(new.findall(text))) == 11


# --- what still blocks ONB-011 --------------------------------------------

def test_no_weights_are_given(build):
    """C12 is fed by eight pathways and C11 by one. Turning fifteen pathway
    values into twelve cluster values needs a combination rule, and the sheet
    states none -- so an unweighted mean would not be a neutral choice, it
    would be a chosen one."""
    assert build["weights_given"] is False
    for pathway in build["pathways"]:
        # Strip the cluster ids themselves; anything numeric left over would
        # be a weight the sheet had started to supply.
        remainder = re.sub(r"C(?:0[1-9]|1[0-2])", "",
                           pathway["cluster_outputs_verbatim"])
        assert not re.search(r"[0-9]", remainder), (
            pathway["pathway_id"], pathway["cluster_outputs_verbatim"])

    fan_in = {}
    for pathway in build["pathways"]:
        for cluster in pathway["cluster_outputs"]:
            fan_in[cluster] = fan_in.get(cluster, 0) + 1
    assert fan_in["C12"] == 8
    assert fan_in["C11"] == 1


def test_c01_is_fed_by_no_pathway(build):
    """Membrane Integrity is not an output of any of the fifteen. A
    warm-start driven by this map leaves one of the twelve clusters with
    nothing, and no zero-fill is applied: a zero would be a claim."""
    assert build["clusters_with_no_pathway"] == ["C01"]
    assert build["cluster_fed_by"]["C01"] == []
    assert len(build["cluster_fed_by"]["C05"]) == 6


def test_no_hi_lo_split_is_given(build):
    """ONB-012 fills xi_hi[163:174] and xi_lo[175:186] -- twenty-four slots
    from fifteen values. Nothing in this sheet says how."""
    assert build["hi_lo_split_given"] is False
    for pathway in build["pathways"]:
        assert "hi" not in pathway["cluster_outputs_verbatim"].lower()


def test_the_list_position_is_kept_because_it_may_encode_dominance(build):
    """'Map · TVMCD→12→Hallmarks' uses a 'Dominant organ node(s)' column in
    the same comma-separated style, so the order here may carry the same
    meaning. Dropping it would destroy that reading before anyone can ask."""
    d03 = next(p for p in build["pathways"] if p["pathway_id"] == "D03")
    assert d03["cluster_outputs"] == ["C05", "C12", "C08"]
    assert d03["biological_meaning"].startswith("Inflammation")
