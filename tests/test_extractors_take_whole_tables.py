"""Every extractor must refuse a sheet that carries more than it reads.

An extractor's header check used to verify the labels it was given and say
nothing about the columns it was not. That is invisible by construction: a
sheet with seven columns and an extractor declaring six agree perfectly and
the seventh is lost.

It happened three times. 'O·O1 Anthropometrics' and 'O·O2 MVPA Prior' both
carry an "Engine Target" column -- where each equation's output goes -- and
both were imported without it. 'TVMCD · 15 Pathways Build' lost "Uncertainty
treatment" and "Validation scenario" to an extractor whose docstring called
the sheet a complete implementation table.

sahacore.data.sheet_header.check_header does both halves. This test makes
using it non-optional, and can run in CI because it reads source rather than
the workbook -- which is not in the repository.
"""
import ast
import pathlib

import pytest

DATA = pathlib.Path(__file__).parent.parent / "sahacore" / "data"

# Extractors whose sheet has no tabular header to check -- they read named
# cells or blocks rather than a table. Listed by hand so that "this one is
# different" is a decision on the record, not an omission.
NO_TABULAR_HEADER = {
    "build_eq_build_rows.py",
    "build_eq_param_fk.py",
    "build_nutrients.py",
    "build_state_vector.py",
}

# READ TABLES AND DO NOT USE THE SHARED CHECK. Not exceptions -- unaudited.
#
# The rule below used to trigger on a module-level HEADER_ROW, and these five
# keep their header rows somewhere else: inside a dict, a loop, or a local.
# So they SKIPPED, silently, for as long as they have existed -- which is the
# same shape of failure the whole file was written to stop. The test found
# nothing because it was asking the wrong question.
#
# Each of these reads at least one tabular sheet and could be dropping a
# trailing column exactly as build_onboarding_o1 and build_tvmcd_pathways did.
# They are pinned by name so a SIXTH cannot join them quietly; auditing the
# five against the workbook is its own job. See docs/parameter-gaps.md.
UNVERIFIED_HEADERS = {
    "build_organ_registries.py",
    "build_parameter_registry.py",
    "build_state_admission.py",
    "build_state_vector_219.py",
    "build_validation_battery.py",
}


def _extractors() -> list[pathlib.Path]:
    return sorted(p for p in DATA.glob("build_*.py")
                  if p.name not in NO_TABULAR_HEADER)


def test_there_are_extractors_to_check():
    """A rule that finds nothing passes quietly."""
    assert len(_extractors()) >= 20


def test_the_unverified_set_is_exactly_what_it_claims():
    """THE HOLE THIS FILE HAD. The rule below triggered on a module-level
    HEADER_ROW, so an extractor that kept its header row in a dict skipped
    the check entirely -- and five of them do. A skip is the one outcome a
    safety net must never produce quietly.

    So the set is pinned. A sixth extractor that reads a table without
    check_header fails here instead of joining them in silence, and each of
    the five stops being listed the moment it starts using the shared check.
    """
    unverified = set()
    for path in _extractors():
        source = path.read_text(encoding="utf-8")
        if "check_header(" not in source:
            unverified.add(path.name)

    assert unverified == UNVERIFIED_HEADERS, (
        "extractors reading tables without the shared header check are "
        f"{sorted(unverified)}, not {sorted(UNVERIFIED_HEADERS)}")


@pytest.mark.parametrize("path", _extractors(), ids=lambda p: p.name)
def test_an_extractor_that_reads_a_table_uses_the_shared_check(path):
    """Every extractor must call check_header, which refuses a header wider
    than the labels it was given. The trigger is no longer whether the module
    declares a HEADER_ROW -- that question let five through."""
    if path.name in UNVERIFIED_HEADERS:
        pytest.xfail(f"{path.name} has never used the shared check")

    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    imports_shared = any(
        isinstance(node, ast.ImportFrom)
        and node.module == "sahacore.data.sheet_header"
        for node in ast.walk(tree)
    )
    assert imports_shared, (
        f"{path.name} reads a table but does not import check_header from "
        "sahacore.data.sheet_header, so a column past the ones it declares "
        "would be dropped in silence")

    assert "check_header(" in source, path.name


@pytest.mark.parametrize("path", _extractors(), ids=lambda p: p.name)
def test_no_extractor_keeps_a_private_header_check(path):
    """A local copy would drift from the shared one, and the whole point is
    that the check is the same everywhere."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    private = [node.name for node in tree.body
               if isinstance(node, ast.FunctionDef)
               and "header" in node.name.lower()]
    assert not private, f"{path.name} defines {private}"
