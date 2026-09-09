"""Every third-party module this repo imports must be pinned.

This exists because `openpyxl` was not in requirements.txt for two commits.
It is installed in the development container, so the suite passed locally
every time; CI installs only what requirements.txt names, so it failed there
every time, on two tests that import the workbook extractors for the alias
and gap tables declared in them.

Nothing about running the tests can catch that -- the module is present where
they run. So this checks the manifest against the source instead, by reading
the imports rather than executing them, and fails on the machine that has the
package installed.
"""
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
FIRST_PARTY = {"sahacore", "tests", "conftest"}


def _pinned() -> set[str]:
    """The distribution names in requirements.txt, normalised.

    'psycopg[binary]==3.3.5' -> 'psycopg'. Comment and blank lines are
    skipped; a package's import name and its distribution name are the same
    for everything this repo uses, and the test says so if that ever stops
    being true.
    """
    names = set()
    for line in (ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        names.add(re.split(r"[\[=<>!~;]", line, 1)[0].strip().lower())
    return names


def _imported() -> dict[str, set[str]]:
    """Top-level module name -> the files that import it."""
    found: dict[str, set[str]] = {}
    for path in sorted((*ROOT.glob("sahacore/**/*.py"), *ROOT.glob("tests/*.py"))):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                # A relative import has no module of its own to resolve.
                roots = [node.module.split(".")[0]] if node.level == 0 and node.module else []
            else:
                continue
            for root in roots:
                found.setdefault(root, set()).add(str(path.relative_to(ROOT)))
    return found


def test_every_third_party_import_is_pinned_in_requirements():
    pinned = _pinned()
    missing = {
        module: sorted(files)
        for module, files in _imported().items()
        if module not in sys.stdlib_module_names
        and module not in FIRST_PARTY
        and module.lower() not in pinned
    }
    assert not missing, (
        "these modules are imported but not pinned in requirements.txt, so "
        f"they will be absent in CI: {missing}"
    )


def test_the_check_actually_looks_at_third_party_imports():
    """A rule that finds nothing to check would pass just as quietly. These
    three are what it is scanning for, so an empty or broken scan fails here.

    `scipy` was on this list until the layer modules moved to archive/ and
    took the only imports of it with them. This test caught that, which is
    the behaviour wanted: the canary noticed the build's dependencies had
    actually changed rather than passing on a stale list.
    """
    imported = _imported()
    for module in ("psycopg", "pytest", "openpyxl"):
        assert imported.get(module), f"{module} should be imported somewhere"
        assert module in _pinned(), f"{module} should be pinned"


def test_nothing_is_pinned_that_no_longer_has_a_home():
    """The manifest and the source must agree in both directions. A pin left
    behind after its last import moved away is how a requirements file grows
    packages nobody can account for.

    archive/ is deliberately not scanned: parking a module must not keep its
    dependency alive on the engine's manifest. When one comes back to
    sahacore/, test_every_third_party_import_is_pinned_in_requirements
    demands the pin again.
    """
    imported = _imported()
    orphans = sorted(m for m in _pinned() if not imported.get(m))
    assert not orphans, (
        f"pinned but imported nowhere in sahacore/ or tests/: {orphans}")
