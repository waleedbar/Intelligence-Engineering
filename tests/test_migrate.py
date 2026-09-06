"""Tests for the migration file discovery/ordering logic in sahacore/migrate.py
that don't require a database. Full apply/rollback behavior is exercised by
hand against a real Postgres instance (see the CI workflow), since it needs
an actual server to run migrations against.
"""
from sahacore.migrate import SQL_DIR, _migration_files


def test_sql_dir_exists_and_has_migrations():
    assert SQL_DIR.is_dir()
    assert len(_migration_files()) >= 1


def test_migration_files_are_sorted_by_filename():
    files = _migration_files()
    names = [f.name for f in files]
    assert names == sorted(names)


def test_all_migration_files_are_sql():
    for f in _migration_files():
        assert f.suffix == ".sql"
