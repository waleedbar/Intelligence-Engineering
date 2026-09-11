"""The loader sequence, and the two lists that must not drift from it.

A missing loader does not fail a load. It leaves a table empty, and the first
thing that notices is a test several steps later complaining about a count --
which is how CI run 66 reported it: the `docker` job applied migrations,
loaded nothing, and failed in test_registry_version.py with 67 registries
"loaded but unversioned".

So the order lives in sahacore/data/load_all.py, and these keep it complete.
"""
import re
from pathlib import Path

import pytest

from sahacore.data.load_all import LOADERS

ROOT = Path(__file__).parent.parent
DATA_DIR = ROOT / "sahacore" / "data"
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"

# Same rule as tests/test_ci_workflow_is_valid_shell.py: the workflow is a
# repository file and .dockerignore keeps it out of the image, so the check
# below skips on the absence of a CHECKOUT rather than of the workflow.
IN_A_CHECKOUT = (ROOT / ".git").exists()


def test_every_loader_module_on_disk_is_in_the_sequence():
    """The one that would have caught this. A new extractor ships a JSON seed,
    a migration and a load_*.py; if the last is never called, every test that
    reads the table it fills is testing an empty table."""
    on_disk = {p.stem for p in DATA_DIR.glob("load_*.py")} - {"load_all"}
    listed = set(LOADERS)

    assert not on_disk - listed, f"loaders never run: {sorted(on_disk - listed)}"
    assert not listed - on_disk, f"listed but no such module: {sorted(listed - on_disk)}"


def test_the_sequence_has_no_duplicates():
    """Running a loader twice is usually harmless -- they upsert -- which is
    exactly why a duplicate would go unnoticed while hiding a typo for the
    loader it was meant to be."""
    assert len(LOADERS) == len(set(LOADERS))


def test_the_order_is_not_alphabetical():
    """A guard against someone tidying it. Nutrients must precede the cluster
    weights that reference them, the message templates must precede the VETO
    rules whose message_id is a foreign key into them, and sorting this list
    would break both."""
    assert LOADERS != sorted(LOADERS)
    assert LOADERS.index("load_veto_messages") < LOADERS.index("load_veto_registry")
    assert LOADERS.index("load_nutrients") < LOADERS.index("load_layer_c_d")
    assert LOADERS.index("load_onboarding_canonical") < LOADERS.index("load_onboarding_o1")


@pytest.mark.skipif(
    not IN_A_CHECKOUT and not WORKFLOW.exists(),
    reason="not a checkout -- the workflow is not shipped in the image")
def test_ci_calls_the_sequence_rather_than_repeating_it():
    """The duplication that bit: the loader order lived in the workflow, and
    the second job that needed it did not get a copy. CI must now call
    load_all -- and must not go back to listing the loaders itself."""
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "python -m sahacore.data.load_all" in workflow

    individually = set(re.findall(r"sahacore\.data\.(load_[a-z0-9_]+)", workflow))
    assert individually == {"load_all"}, (
        f"the workflow calls loaders directly again: {sorted(individually - {'load_all'})}")
