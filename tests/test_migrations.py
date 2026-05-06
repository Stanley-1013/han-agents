"""
Tests for schema migration metadata.
"""


def test_schema_version_metadata(mock_db_path):
    from servers.migrations import (
        CURRENT_SCHEMA_VERSION,
        apply_pending_migrations,
        ensure_schema_version,
        get_migration_history,
        get_schema_version,
    )

    result = ensure_schema_version()
    assert result["expected_version"] == CURRENT_SCHEMA_VERSION
    applied = apply_pending_migrations()
    assert applied["current_version"] == CURRENT_SCHEMA_VERSION
    assert get_schema_version() == CURRENT_SCHEMA_VERSION

    history = get_migration_history()
    assert history
    assert history[-1]["version"] == CURRENT_SCHEMA_VERSION
