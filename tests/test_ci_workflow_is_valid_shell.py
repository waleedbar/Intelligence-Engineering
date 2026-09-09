"""Every `run:` block in the CI workflow must be shell a machine can parse.

This exists because CI was red for three commits on a quoting bug that no
Python test could see. The 'Verify loaded row counts' step is a Python
program inside a double-quoted shell string:

    run: |
      python -c "
      ...
      cur.execute(\"SELECT ...\")
      "

An added line used a bare `"` instead of `\"`, which closes the shell string
early. The Python it contains is fine -- running those same assertions
directly passed every time, which is exactly why the bug survived three
pushes. The defect is in the shell layer, so it has to be checked there.

`bash -n` parses without executing, so this is safe to run anywhere.
"""
import shutil
import subprocess
from pathlib import Path

import pytest

WORKFLOW = Path(__file__).parent.parent / ".github" / "workflows" / "ci.yml"


def _run_blocks() -> list[tuple[str, str]]:
    import yaml

    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    blocks = []
    for job_name, job in workflow["jobs"].items():
        for step in job.get("steps", []):
            if "run" in step:
                blocks.append((step.get("name", f"{job_name}:unnamed"), step["run"]))
    return blocks


def test_the_workflow_parses_as_yaml():
    assert _run_blocks(), "no run: blocks found -- the workflow moved or broke"


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash not available")
def test_every_run_block_is_syntactically_valid_shell():
    """`bash -n` reads the script and reports syntax errors without running
    anything. An unterminated string fails here."""
    for name, script in _run_blocks():
        result = subprocess.run(
            ["bash", "-n"], input=script, text=True, capture_output=True)
        assert result.returncode == 0, (
            f"step {name!r} is not valid shell:\n{result.stderr}")


def test_the_python_inside_the_verify_step_has_balanced_quoting():
    """The specific shape that broke: a double-quoted shell string holding
    Python. Every double quote inside it must be escaped, or the string ends
    where nobody meant it to."""
    for name, script in _run_blocks():
        if 'python -c "' not in script:
            continue
        body = script.split('python -c "', 1)[1]
        for i, line in enumerate(body.splitlines(), start=1):
            stripped = line.strip()
            if stripped == '"':          # the closing quote of the -c string
                break
            unescaped = [
                pos for pos, ch in enumerate(line)
                if ch == '"' and (pos == 0 or line[pos - 1] != "\\")
            ]
            assert not unescaped, (
                f"step {name!r} line {i} has an unescaped double quote inside "
                f'the python -c string, which ends it early:\n    {stripped}'
            )
