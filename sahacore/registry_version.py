"""What version each registry is at, and what it contained at that version.

Source: v39sEng2.xlsx, sheet 'IO · Lineage DataMap'. Its rows require derived
packets to cite the registry they were computed against -- exposure_state
carries `nutrient_registry_version`, posterior_state carries
`state_registry_version` and `model_version` -- and 'EQ · Canonical Build
Rows' row LEDGER-002 generalises it: "Every packet carries parent_packet_ids,
parent_versions, lineage_hash, as_of_time, status", cadence "all downstream".

This module is what those numbers point at. Every loader in sahacore.data
calls `record_version` with the rows it just wrote, and the version it gets
back is the one a packet computed against those rows must cite.

WHY A RELOAD IS USUALLY NOT A NEW VERSION. CI reloads every registry on every
push, and the workbook has not changed, so handing out a version number per
load would produce a version history made almost entirely of noise -- and
would make "did the nutrients change between these two packets?" unanswerable
by comparing version numbers. So the content decides: the rows are hashed
with the ledger's own `lineage_hash`, and identical content returns the
existing version untouched. A load is idempotent in exactly the way
`python -m sahacore.migrate` is.

WHAT COUNTS AS CONTENT. The rows as the loader read them, in order, with
their keys -- not the database's rendering of them afterwards. Hashing what
was read keeps the version tied to the source file rather than to a
round-trip through Postgres, where a numeric column could come back as
Decimal and change a digest without anything having changed.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from sahacore.db import get_connection
from sahacore.ledger.lineage import lineage_hash


def content_hash(rows: Sequence[Mapping[str, Any]]) -> str:
    """The digest of a registry's contents.

    Order-sensitive on purpose: the loaders read a workbook sheet top to
    bottom, and a reordering of that sheet is a change worth a new version
    even when the set of rows is identical.
    """
    return lineage_hash({"rows": [dict(r) for r in rows]})


def record_version(registry: str, rows: Sequence[Mapping[str, Any]], *,
                   source_sheet: str, source_file: str,
                   conn=None) -> tuple[int, str, bool]:
    """Record what `registry` now contains. Returns (version_no, hash, is_new).

    Unchanged content returns the existing ACTIVE version and writes nothing.
    Changed content supersedes the previous ACTIVE row and inserts the next
    version number, so the history of what the engine believed is kept rather
    than overwritten -- the same shape event_quality and controls_u use.

    Content that has been seen before under this registry but is not the
    current ACTIVE one -- a revert -- is an error rather than a silent
    resurrection: the UNIQUE (registry, content_hash) constraint would refuse
    the insert, and it is raised here with an explanation instead of a
    constraint name.
    """
    if not rows:
        raise ValueError(f"{registry}: refusing to version an empty registry")

    digest = content_hash(rows)
    owns_connection = conn is None
    conn = conn or get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT version_no, content_hash FROM engine_internal.registry_version "
                "WHERE registry = %s AND status = 'ACTIVE'",
                (registry,),
            )
            active = cur.fetchone()
            if active and active["content_hash"] == digest:
                return active["version_no"], digest, False

            cur.execute(
                "SELECT version_no FROM engine_internal.registry_version "
                "WHERE registry = %s AND content_hash = %s",
                (registry, digest),
            )
            seen = cur.fetchone()
            if seen:
                raise ValueError(
                    f"{registry}: this exact content was already version "
                    f"{seen['version_no']}, which is no longer ACTIVE. Reverting a "
                    "registry is a real decision -- reactivate that version "
                    "deliberately rather than letting a reload do it silently."
                )

            cur.execute(
                "UPDATE engine_internal.registry_version SET status = 'SUPERSEDED' "
                "WHERE registry = %s AND status = 'ACTIVE'",
                (registry,),
            )
            cur.execute(
                "SELECT coalesce(max(version_no), 0) + 1 AS next "
                "FROM engine_internal.registry_version WHERE registry = %s",
                (registry,),
            )
            version_no = cur.fetchone()["next"]
            cur.execute(
                """
                INSERT INTO engine_internal.registry_version
                    (registry, version_no, content_hash, row_count,
                     source_sheet, source_file)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (registry, version_no, digest, len(rows), source_sheet, source_file),
            )
        if owns_connection:
            conn.commit()
        return version_no, digest, True
    finally:
        if owns_connection:
            conn.close()


def active_version(registry: str, conn=None) -> tuple[int, str] | None:
    """The version a packet written now must cite, or None if never loaded."""
    owns_connection = conn is None
    conn = conn or get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT version_no, content_hash FROM engine_internal.registry_version "
                "WHERE registry = %s AND status = 'ACTIVE'",
                (registry,),
            )
            row = cur.fetchone()
        return (row["version_no"], row["content_hash"]) if row else None
    finally:
        if owns_connection:
            conn.close()
