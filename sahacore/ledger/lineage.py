"""Lineage hashes.

Source: v39sEng2.xlsx, sheet 'IO · Lineage DataMap', which puts a
`lineage_hash` on raw_events, controls_u, measurements_y, every derived
packet, checkpoint_state and the replay job, and sheet 'Replay Contract':

    step 4  (G10) "same inputs + versions produce identical posterior hashes"
    step 6  (G12) "Affected channels match clean rebuild; unrelated signature
                   hashes unchanged"
    step 9  (G15) "replay leaves served-event hash and timestamp unchanged"

Those three acceptance tests are all the same demand: the hash must be a pure
function of content and parentage, identical across processes, machines and
runs, and different the moment any parent changes. So:

  * canonical JSON -- keys sorted, no insignificant whitespace, UTF-8 -- so
    that dict ordering cannot change a hash;
  * datetimes normalised to UTC and rendered to a fixed precision, so that
    the same instant expressed in two zones hashes identically;
  * parent hashes folded in as a SORTED list, since parentage is a set, not
    an order;
  * SHA-256, and the digest carries its algorithm name, so that a future
    change of algorithm is visible in stored data rather than silently
    producing collisions against old rows;
  * an unencodable value raises instead of falling back to repr(), because a
    repr-based hash would be stable within one Python version and quietly
    wrong across an upgrade.

Python's built-in hash() is deliberately not used anywhere here: it is salted
per process (PYTHONHASHSEED), so it cannot satisfy G10 at all.
"""
import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

ALGORITHM = "sha256"


class UnhashableLineageValue(TypeError):
    """Raised when a value has no canonical serialisation. Falling back to
    repr() would make the hash depend on the Python runtime rather than on
    the content, breaking the 'same inputs produce identical hashes'
    acceptance test in a way no test run would catch."""


def _canonical(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        # repr() round-trips exactly for float and is stable across CPython
        # versions; format() would silently truncate.
        return repr(value)
    if isinstance(value, Decimal):
        return f"decimal:{value.normalize():f}"
    if isinstance(value, datetime):
        if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
            raise UnhashableLineageValue(
                "naive datetime in lineage payload: the same wall-clock time "
                "in two zones would hash identically"
            )
        return value.astimezone(timezone.utc).isoformat(timespec="microseconds")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, bytes):
        return "bytes:" + value.hex()
    if isinstance(value, Mapping):
        return {str(k): _canonical(v) for k, v in sorted(value.items(), key=lambda kv: str(kv[0]))}
    if isinstance(value, (list, tuple)):
        return [_canonical(v) for v in value]
    if isinstance(value, (set, frozenset)):
        # A set has no order, so canonicalise its members and sort the result.
        return sorted((json.dumps(_canonical(v), sort_keys=True) for v in value))
    raise UnhashableLineageValue(
        f"{type(value).__name__} has no canonical lineage serialisation"
    )


def canonical_json(payload: Mapping[str, Any]) -> str:
    """The exact byte-level input the digest is taken over. Exposed so a
    lineage mismatch can be debugged by diffing two canonical forms rather
    than by staring at two hex digests."""
    return json.dumps(
        _canonical(payload),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def lineage_hash(payload: Mapping[str, Any], parents: Sequence[str] = ()) -> str:
    """The lineage_hash of one ledger row or derived packet.

    `parents` are the lineage hashes this object descends from. They are
    folded in so that superseding a parent necessarily changes every
    descendant's hash -- which is what makes 'no active packet has a
    superseded parent' (Replay Contract step 7, G13) checkable by hash
    rather than by trusting the writer.
    """
    envelope = {
        "parents": sorted(str(p) for p in parents),
        "payload": _canonical(payload),
    }
    body = json.dumps(envelope, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.new(ALGORITHM, body.encode("utf-8")).hexdigest()
    return f"{ALGORITHM}:{digest}"
