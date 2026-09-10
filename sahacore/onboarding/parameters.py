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
