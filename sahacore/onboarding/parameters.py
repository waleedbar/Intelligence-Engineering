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
