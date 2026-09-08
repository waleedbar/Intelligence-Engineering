"""Lineage hashes, against the three acceptance tests that constrain them.

    Replay Contract step 4  (G10): "same inputs + versions produce identical
                                    posterior hashes"
    Replay Contract step 6  (G12): "unrelated signature hashes unchanged"
    Replay Contract step 9  (G15): "replay leaves served-event hash and
                                    timestamp unchanged"
"""
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

import pytest

from sahacore.ledger.lineage import (
    ALGORITHM,
    UnhashableLineageValue,
    canonical_json,
    lineage_hash,
)

UTC = timezone.utc


def test_the_same_content_hashes_identically_whatever_the_key_order():
    """G10's "same inputs produce identical hashes" -- a dict literal's
    insertion order is not part of the content."""
    a = lineage_hash({"user_id": 7, "value": 4.2, "type": "hba1c"})
    b = lineage_hash({"type": "hba1c", "value": 4.2, "user_id": 7})
    assert a == b


def test_the_same_instant_in_two_timezones_hashes_identically():
    """Timestamps are canonicalised to UTC before hashing, so an adapter's
    choice of representation cannot fork a lineage."""
    amman = timezone(timedelta(hours=3))
    assert lineage_hash({"t": datetime(2026, 9, 8, 15, 0, tzinfo=amman)}) == lineage_hash(
        {"t": datetime(2026, 9, 8, 12, 0, tzinfo=UTC)}
    )


def test_a_naive_datetime_is_refused():
    """Two different instants would otherwise hash the same."""
    with pytest.raises(UnhashableLineageValue, match="naive datetime"):
        lineage_hash({"t": datetime(2026, 9, 8, 12, 0)})


def test_an_unserialisable_value_raises_instead_of_falling_back_to_repr():
    """A repr-based hash is stable within one Python version and quietly
    wrong across an upgrade -- a failure no test run would catch."""

    class Opaque:
        pass

    with pytest.raises(UnhashableLineageValue, match="Opaque"):
        lineage_hash({"x": Opaque()})


def test_changing_any_field_changes_the_hash():
    base = {"value": 4.2, "unit": "%"}
    assert lineage_hash(base) != lineage_hash({**base, "value": 4.3})
    assert lineage_hash(base) != lineage_hash({**base, "unit": "mmol/mol"})


def test_parentage_is_a_set_not_an_order():
    """A packet's parents are unordered; listing them differently must not
    fork the lineage."""
    payload = {"quantity": "hba1c"}
    p1, p2 = "sha256:aa", "sha256:bb"
    assert lineage_hash(payload, parents=[p1, p2]) == lineage_hash(payload, parents=[p2, p1])


def test_superseding_a_parent_changes_every_descendant_hash():
    """G13's "no active packet has a superseded parent" is checkable by hash
    precisely because a changed parent cannot leave a descendant's hash
    intact."""
    payload = {"quantity": "posterior"}
    assert lineage_hash(payload, parents=["sha256:old"]) != lineage_hash(
        payload, parents=["sha256:new"]
    )


def test_parentage_and_payload_cannot_be_confused_for_one_another():
    """A hash that merely concatenated its inputs could be forged by moving
    content between the two positions."""
    assert lineage_hash({"a": "b"}, parents=[]) != lineage_hash({}, parents=["a", "b"])


def test_the_digest_names_its_own_algorithm():
    """So that a future change of algorithm is visible in stored rows rather
    than silently colliding with hashes written under the old one."""
    digest = lineage_hash({"x": 1})
    algorithm, _, hexdigest = digest.partition(":")
    assert algorithm == ALGORITHM == "sha256"
    assert len(hexdigest) == 64
    assert set(hexdigest) <= set("0123456789abcdef")


def test_uuids_and_nested_structures_are_canonicalised():
    payload = {
        "event_uuid": UUID("12345678-1234-5678-1234-567812345678"),
        "parents": [{"b": 2, "a": 1}],
        "flags": {"z", "a"},
    }
    assert lineage_hash(payload) == lineage_hash(
        {
            "flags": {"a", "z"},
            "parents": [{"a": 1, "b": 2}],
            "event_uuid": UUID("12345678-1234-5678-1234-567812345678"),
        }
    )


def test_canonical_json_is_stable_and_diffable():
    """Exposed so a lineage mismatch is debugged by diffing two canonical
    forms rather than by staring at two hex digests."""
    assert canonical_json({"b": 1, "a": 2}) == '{"a":2,"b":1}'


def test_the_hash_is_identical_across_processes():
    """G10 in its strongest form. Python's built-in hash() is salted per
    process (PYTHONHASHSEED), so this test would fail outright if it had
    been used anywhere in the digest -- which is exactly why it is not.
    Two fresh interpreters with deliberately different hash seeds must
    produce the same lineage_hash."""
    program = (
        "from sahacore.ledger.lineage import lineage_hash;"
        "print(lineage_hash({'a': 1, 'b': [2, 3], 'c': 'x'}, parents=['sha256:p']))"
    )
    repo_root = Path(__file__).parent.parent
    digests = set()
    for seed in ("0", "1", "12345"):
        result = subprocess.run(
            [sys.executable, "-c", program],
            capture_output=True,
            text=True,
            check=True,
            cwd=repo_root,
            env={"PYTHONHASHSEED": seed, "PYTHONPATH": str(repo_root), "PATH": "/usr/bin:/bin"},
        )
        digests.add(result.stdout.strip())
    assert len(digests) == 1
