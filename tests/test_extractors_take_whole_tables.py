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


def _extractors() -> list[pathlib.Path]:
    return sorted(p for p in DATA.glob("build_*.py")
                  if p.name not in NO_TABULAR_HEADER)


def test_there_are_extractors_to_check():
    """A rule that finds nothing passes quietly."""
    assert len(_extractors()) >= 20


@pytest.mark.parametrize("path", _extractors(), ids=lambda p: p.name)
def test_an_extractor_with_a_header_row_uses_the_shared_check(path):
    """If a module declares a HEADER_ROW it is reading a table, and it must
    use check_header -- which refuses a header wider than the labels given."""
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    declares_header = any(
        isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id.endswith("HEADER_ROW")
                for t in node.targets)
        for node in tree.body
    )
    if not declares_header:
        pytest.skip(f"{path.name} declares no HEADER_ROW")

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
