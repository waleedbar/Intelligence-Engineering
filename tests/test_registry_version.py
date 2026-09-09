"""Registry versioning: what a derived packet's *_registry_version points at.

Source: v39sEng2.xlsx, sheet 'IO · Lineage DataMap'. exposure_state carries
`nutrient_registry_version`; posterior_state carries `state_registry_version`
and `model_version`; 'EQ · Canonical Build Rows' row LEDGER-002 makes it
general -- "Every packet carries parent_packet_ids, parent_versions,
lineage_hash, as_of_time, status", cadence "all downstream".

This has to work before any layer writes a packet. Without it a registry
reload silently overwrites the values a packet was computed against, and
replay mixes parameter generations without saying so -- which is exactly what
RT-01 and AUD-01 exist to catch.
"""
import json
import uuid
from pathlib import Path

import psycopg
import pytest

from sahacore.registry_version import active_version, content_hash, record_version

DATA_DIR = Path(__file__).parent.parent / "sahacore" / "data"


@pytest.fixture
def registry(ledger_db):
    """A registry name unique to this test, so cases never collide and none
    of them touches the versions the loaders recorded."""
    return f"test.registry_{uuid.uuid4().hex[:12]}"


# --- the hash -------------------------------------------------------------

def test_identical_content_hashes_identically():
    rows = [{"id": "a", "value": 1}, {"id": "b", "value": 2}]
    assert content_hash(rows) == content_hash([dict(r) for r in rows])


def test_a_changed_value_changes_the_hash():
    """The property the whole design rests on: if a gamma shape changes, the
    version must change too."""
    before = [{"id": "a", "value": 1}]
    after = [{"id": "a", "value": 1.0001}]
    assert content_hash(before) != content_hash(after)


def test_reordering_changes_the_hash():
    """Deliberately order-sensitive. The loaders read a sheet top to bottom,
    and a reordered sheet is a change worth a version even when the set of
    rows is the same -- row order is what `num`, `param_no` and `source_row`
    are keyed to elsewhere in this build."""
    rows = [{"id": "a"}, {"id": "b"}]
    assert content_hash(rows) != content_hash(list(reversed(rows)))


def test_the_hash_is_the_ledgers_own_format():
    """One digest format across the build, not two. The database CHECK
    constraint enforces this shape as well."""
    digest = content_hash([{"id": "a"}])
    assert digest.startswith("sha256:")
    assert len(digest) == len("sha256:") + 64


# --- recording ------------------------------------------------------------

def test_a_first_load_is_version_one(ledger_db, registry):
    rows = [{"id": "a", "value": 1}]
    version_no, digest, is_new = record_version(
        registry, rows, source_sheet="Sheet A", source_file="a.json", conn=ledger_db)
    assert (version_no, is_new) == (1, True)
    assert active_version(registry, conn=ledger_db) == (1, digest)


def test_reloading_unchanged_content_does_not_make_a_new_version(ledger_db, registry):
    """CI reloads every registry on every push. If that minted a version each
    time, the history would be noise and comparing two packets' version
    numbers would say nothing."""
    rows = [{"id": "a", "value": 1}]
    first, _, _ = record_version(registry, rows, source_sheet="S", source_file="f",
                                 conn=ledger_db)
    second, _, is_new = record_version(registry, rows, source_sheet="S",
                                       source_file="f", conn=ledger_db)
    assert (second, is_new) == (first, False)

    with ledger_db.cursor() as cur:
        cur.execute("SELECT count(*) AS n FROM engine_internal.registry_version "
                    "WHERE registry = %s", (registry,))
        assert cur.fetchone()["n"] == 1


def test_changed_content_supersedes_rather_than_overwrites(ledger_db, registry):
    """The point of the table. The old version stays readable, so a packet
    that cited v1 can still be told what v1 contained."""
    record_version(registry, [{"id": "a", "value": 1}],
                   source_sheet="S", source_file="f", conn=ledger_db)
    v2, hash2, is_new = record_version(registry, [{"id": "a", "value": 2}],
                                       source_sheet="S", source_file="f",
                                       conn=ledger_db)
    assert (v2, is_new) == (2, True)

    with ledger_db.cursor() as cur:
        cur.execute("SELECT version_no, status FROM engine_internal.registry_version "
                    "WHERE registry = %s ORDER BY version_no", (registry,))
        assert [(r["version_no"], r["status"]) for r in cur.fetchall()] == [
            (1, "SUPERSEDED"), (2, "ACTIVE")]
    assert active_version(registry, conn=ledger_db) == (2, hash2)


def test_only_one_version_can_be_active(ledger_db, registry):
    """Enforced by a partial unique index, not by the writer being careful.
    A consumer resolving nutrient_registry_version must never find two
    candidates."""
    record_version(registry, [{"id": "a"}], source_sheet="S", source_file="f",
                   conn=ledger_db)
    with pytest.raises(psycopg.errors.UniqueViolation), ledger_db.transaction():
        with ledger_db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO engine_internal.registry_version
                    (registry, version_no, content_hash, row_count,
                     source_sheet, source_file)
                VALUES (%s, 99, %s, 1, 'S', 'f')
                """,
                (registry, "sha256:" + "0" * 64),
            )


def test_reverting_to_an_older_content_is_refused_rather_than_silent(ledger_db, registry):
    """Putting yesterday's registry back is a real decision. Letting a reload
    do it silently would produce a v3 that is byte-identical to v1, and the
    UNIQUE (registry, content_hash) constraint is what makes 'has this content
    been active before?' answerable at all."""
    old = [{"id": "a", "value": 1}]
    record_version(registry, old, source_sheet="S", source_file="f", conn=ledger_db)
    record_version(registry, [{"id": "a", "value": 2}], source_sheet="S",
                   source_file="f", conn=ledger_db)
    with pytest.raises(ValueError, match="already version 1"):
        record_version(registry, old, source_sheet="S", source_file="f",
                       conn=ledger_db)


def test_an_empty_registry_is_refused(ledger_db, registry):
    """A registry that loaded nothing has no version to speak of, and a
    row_count of 0 would pass unnoticed as 'loaded'."""
    with pytest.raises(ValueError, match="empty"):
        record_version(registry, [], source_sheet="S", source_file="f", conn=ledger_db)


# --- the constraints bite --------------------------------------------------

def test_a_malformed_hash_is_refused_by_the_database(ledger_db, registry):
    with pytest.raises(psycopg.errors.CheckViolation), ledger_db.transaction():
        with ledger_db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO engine_internal.registry_version
                    (registry, version_no, content_hash, row_count,
                     source_sheet, source_file)
                VALUES (%s, 1, 'not-a-hash', 1, 'S', 'f')
                """,
                (registry,),
            )


def test_a_zero_row_version_is_refused_by_the_database(ledger_db, registry):
    with pytest.raises(psycopg.errors.CheckViolation), ledger_db.transaction():
        with ledger_db.cursor() as cur:
            cur.execute(
                """
                INSERT INTO engine_internal.registry_version
                    (registry, version_no, content_hash, row_count,
                     source_sheet, source_file)
                VALUES (%s, 1, %s, 0, 'S', 'f')
                """,
                (registry, "sha256:" + "a" * 64),
            )


# --- every registry is actually versioned ---------------------------------

def test_every_loaded_registry_has_an_active_version(ledger_db):
    """The reason versioning is one step rather than two lines copied into
    each loader: a new registry that forgets to register here fails this."""
    from sahacore.data.record_registry_versions import REGISTRIES

    with ledger_db.cursor() as cur:
        cur.execute("SELECT registry FROM engine_internal.registry_current")
        active = {r["registry"] for r in cur.fetchall()}
    missing = set(REGISTRIES) - active
    assert not missing, f"loaded but unversioned: {sorted(missing)}"


def test_the_recorded_row_counts_match_what_is_in_the_tables(ledger_db):
    """The cross-check that turns a version into evidence: it attests to what
    the loader WROTE, not merely to what it was given. Two loaders in this
    build have silently dropped rows -- 192 parameters loading as 73, and
    three FK rows lost to a non-unique key -- and both were found by hand."""
    from sahacore.data.record_registry_versions import REGISTRIES

    with ledger_db.cursor() as cur:
        for registry in REGISTRIES:
            cur.execute(
                "SELECT row_count FROM engine_internal.registry_version "
                "WHERE registry = %s AND status = 'ACTIVE'", (registry,))
            recorded = cur.fetchone()["row_count"]
            cur.execute(f"SELECT count(*) AS n FROM {registry}")
            assert cur.fetchone()["n"] == recorded, registry


def test_every_version_names_a_source_sheet_and_file(ledger_db):
    """A version that cannot say where its content came from is not
    auditable, which is the only reason to keep one."""
    with ledger_db.cursor() as cur:
        cur.execute("SELECT registry, source_sheet, source_file "
                    "FROM engine_internal.registry_current")
        for row in cur.fetchall():
            assert row["source_sheet"].strip(), row["registry"]
            assert row["source_file"].endswith(".json"), row["registry"]


def test_the_source_files_named_are_the_ones_that_exist():
    """The sheet names are transcription and cannot be checked mechanically;
    the file names can be, and a stale one would mean a version attesting to
    a file nobody reads."""
    from sahacore.data.record_registry_versions import REGISTRIES

    for registry, (filename, key, sheet) in REGISTRIES.items():
        path = DATA_DIR / filename
        assert path.exists(), f"{registry} names {filename}, which does not exist"
        data = json.loads(path.read_text(encoding="utf-8"))
        rows = data[key] if key else data
        assert isinstance(rows, list) and rows, f"{registry}: {filename} has no rows"
        assert sheet.strip()
