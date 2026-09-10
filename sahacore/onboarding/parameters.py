"""Reads Layer 0's parameter tables out of the extracted registries.

The onboarding modules are pure functions over a parameter object. This is
where that object comes from, and it is the only place in the package that
touches a file: a module that read its own constants would be a module whose
constants nobody else could see.

Reading from the JSON rather than the database is deliberate. Layer 0's
equations are pure functions and the CI proves it by running the whole suite
with no DATABASE_URL configured at all. The same values reach PostgreSQL
through sahacore.data.load_onboarding_o1, and record_registry_versions
refuses to version either copy unless the two agree.
"""
import json
from functools import lru_cache
from pathlib import Path

from sahacore.onboarding.anthropometrics import O1Parameters

DATA_DIR = Path(__file__).parent.parent / "data"


@lru_cache(maxsize=1)
def load_o1() -> O1Parameters:
    """The twelve parameters of 'O·O1 Anthropometrics'.

    Constructed by keyword, so a parameter that disappears from the sheet
    raises here rather than silently defaulting inside an equation.
    """
    data = json.loads((DATA_DIR / "onboarding_o1.json").read_text(encoding="utf-8"))
    return O1Parameters(**{p["key"]: p["value"] for p in data["parameters"]})


@lru_cache(maxsize=1)
def load_o2_encoding() -> dict[tuple[str, str], float]:
    """'O·O2 MVPA Prior' input encoding, keyed (field, option).

    'Frequency: 3-4' -> 3.5; 'Duration: <30 min' -> 20. The sheet calls the
    duration mappings conservative midpoints rather than arithmetic ones, so
    they are read rather than derived.
    """
    data = json.loads((DATA_DIR / "onboarding_o2.json").read_text(encoding="utf-8"))
    return {(row["field"], row["option"]): row["numeric_value"]
            for row in data["input_encoding"]}


@lru_cache(maxsize=1)
def load_activity_mets() -> dict[str, float]:
    """Activity id -> MET, from 'P1 Activities 50'."""
    data = json.loads((DATA_DIR / "activities_50.json").read_text(encoding="utf-8"))
    return {row["activity_id"]: row["met"] for row in data["activities"]}


@lru_cache(maxsize=1)
def load_o3_consistency() -> dict[str, float]:
    """O3.6's schedule-consistency scale, option -> score.

    'Very Inconsistent' is 1 and 'Very Consistent' is 4, written inline in
    O3.6's own formula cell rather than in a separate encoding table as O2
    does. Read rather than retyped: what a user's answer is worth is the
    sheet's decision.
    """
    data = json.loads((DATA_DIR / "onboarding_o3.json").read_text(encoding="utf-8"))
    o3_6 = next(e for e in data["equations"] if e["equation_id"] == "O3.6")
    return {option["option"]: option["value"] for option in o3_6["ordinal_scale"]}


@lru_cache(maxsize=1)
def load_o4_reverse_items() -> frozenset[int]:
    """The PSS-10 items O4.1 reverse-scores, as 1-based item numbers.

    Read rather than written into the module. 'O·O4 Stress Index' states them
    twice -- a Reverse? column and O4.1's own formula -- and its header calls
    the change from PSS-4 to PSS-10 a correction, so this is exactly the kind
    of decision the sheet owns. The extractor refuses to import a sheet whose
    two statements disagree.
    """
    data = json.loads((DATA_DIR / "onboarding_o4.json").read_text(encoding="utf-8"))
    return frozenset(item["item_number"] for item in data["items"]
                     if item["reverse_scored"])


@lru_cache(maxsize=1)
def load_o4_bands() -> tuple[dict, ...]:
    """The three PSS-10 interpretation bands, in ascending score order.

    Where 'Moderate' ends is a clinical judgement, so the boundaries are read.
    The extractor checks they tile 0-40 with no gap and no overlap.
    """
    data = json.loads((DATA_DIR / "onboarding_o4.json").read_text(encoding="utf-8"))
    return tuple(sorted(data["bands"], key=lambda band: band["score_min"]))


@lru_cache(maxsize=1)
def _o5_encodings() -> dict[str, dict[str, float]]:
    data = json.loads((DATA_DIR / "onboarding_o5.json").read_text(encoding="utf-8"))
    encodings: dict[str, dict[str, float]] = {}
    for row in data["encodings"]:
        if row["option"] is None:
            continue
        encodings.setdefault(row["encodes"], {})[row["option"]] = row["value"]
    return encodings


def load_o5_encoding(encodes: str) -> dict[str, float]:
    """One of 'O·O5 Substance Exposure''s labelled answer encodings.

    'pack_years' and 'tobacco_idx' turn the same smoking answer into two
    different numbers on two different scales; 'units_week' turns Step 10's
    alcohol band into its midpoint. What an answer is worth is the sheet's
    judgement in all three cases, so all three are read.

    O5.5's SSB midpoints are NOT here: they carry no labels and are keyed by
    position instead -- see load_o5_ssb_midpoints.
    """
    encodings = _o5_encodings()
    if encodes not in encodings:
        raise KeyError(
            f"{encodes!r} is not one of O5's labelled encodings "
            f"({sorted(encodings)}).")
    return encodings[encodes]


@lru_cache(maxsize=1)
def load_o5_ssb_midpoints() -> tuple[float, ...]:
    """O5.5's SSB servings, in the order the sheet writes them.

    A tuple rather than a mapping because the sheet gives four numbers and no
    labels -- "(midpoint: 0/0.5/1.75/3)". Pairing them with Step 3's bands
    would be this build deciding which number means which answer, and the
    numbers do not match those bands' midpoints anyway. See
    docs/parameter-gaps.md.
    """
    data = json.loads((DATA_DIR / "onboarding_o5.json").read_text(encoding="utf-8"))
    rows = [row for row in data["encodings"]
            if row["encodes"] == "SSB_serv_day"]
    return tuple(row["value"]
                 for row in sorted(rows, key=lambda r: r["ordinal_position"]))


@lru_cache(maxsize=1)
def load_o7_patterns() -> tuple[dict, ...]:
    """The eight dietary patterns of 'O·O7 Diet Pattern Priors'.

    Descriptions, not measurements: each carries its nutrient shifts and
    typical deficiencies as prose, because that is all the sheet gives. The
    means and variances O7.1 needs -- 8 x 81 x 2 of them -- are absent, so
    sahacore.onboarding.diet_priors.nutrient_prior raises rather than
    inventing one.

    `ui_status` records how each pattern's declared label relates to what the
    interface actually offers, which is how the Intermittent Fasting gap was
    found.
    """
    data = json.loads((DATA_DIR / "onboarding_o7.json").read_text(encoding="utf-8"))
    return tuple({k: pattern[k] for k in
                  ("pattern", "key_nutrient_shifts", "typical_deficiencies",
                   "ui_label", "ui_status")}
                 for pattern in data["patterns"])


@lru_cache(maxsize=1)
def _o6() -> dict:
    return json.loads((DATA_DIR / "onboarding_o6.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_o6_shifts() -> dict[str, float]:
    """Each family history's log-hazard shift, keyed by its FH_ variable.

    The value is the log the SHEET pre-computes in O6.2-O6.7 ("* 1.000"), not
    ln(RR) recomputed. They agree to 1e-3, and the sheet's is the one its
    declared ranges were written against -- for T2D the relative risk is *e*
    rounded to 2.72 for display, so 1.000 is the exact figure and
    ln(2.72) = 1.000632 is the rounded one.
    """
    return {equation["indicator"]: equation["log_in_formula"]
            for equation in _o6()["equations"]
            if equation["indicator"] is not None}


@lru_cache(maxsize=1)
def load_o6_relative_risks() -> dict[str, float]:
    """Each family history's relative risk, keyed by its FH_ variable."""
    return {equation["indicator"]: equation["rr_in_formula"]
            for equation in _o6()["equations"]
            if equation["indicator"] is not None}


@lru_cache(maxsize=1)
def load_o6_pathways() -> dict[str, tuple[str, ...]]:
    """Which Z-pathways each family history moves, keyed by its FH_ variable.

    O6.10 reads "FH_relevant per pathway" and does not give the mapping; the
    RR reference table's Z-Pathway Affected column is the only place in the
    workbook that does.
    """
    data = _o6()
    # Joined on the CONDITION NAME, not the log-hazard: CVD, colon cancer and
    # breast cancer all carry ln(2.0) = 0.693, so a join on the number
    # collapses three conditions into one. It did, and gave CVD the
    # breast-cancer pathway until a test caught it.
    by_condition = {condition["condition"]: condition["z_pathway_codes"]
                    for condition in data["conditions"]}
    return {equation["indicator"]: tuple(by_condition[equation["condition"]])
            for equation in data["equations"]
            if equation["indicator"] is not None}
