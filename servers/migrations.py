"""
Schema migration helpers for HAN's SQLite brain database.
"""

import os
from typing import Dict, List

from servers import managed_connection


CURRENT_SCHEMA_VERSION = 2
MIGRATIONS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "migrations",
)

MIGRATIONS = [
    {"version": 1, "name": "base_schema", "path": None},
    {"version": 2, "name": "human_review_queue", "path": "002_human_review_queue.sql"},
]

SCHEMA = """
=== Migrations API ===

get_schema_version() -> int
    Return the latest applied schema migration version.

get_migration_history() -> List[Dict]
    Return applied migration records.

ensure_schema_version() -> Dict
    Ensure the schema_migrations table exists and base version is recorded.

apply_pending_migrations() -> Dict
    Apply numbered SQL migrations that have not been recorded yet.
"""


def ensure_schema_version() -> Dict:
    """Ensure migration metadata exists."""
    with managed_connection() as db:
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        db.execute(
            """
            INSERT OR IGNORE INTO schema_migrations (version, name)
            VALUES (?, ?)
            """,
            (1, "base_schema"),
        )
        db.commit()
    return {
        "current_version": get_schema_version(),
        "expected_version": CURRENT_SCHEMA_VERSION,
    }


def _migration_sql(path: str) -> str:
    with open(os.path.join(MIGRATIONS_DIR, path), "r", encoding="utf-8") as f:
        return f.read()


def apply_pending_migrations() -> Dict:
    """Apply unapplied numbered SQL migrations."""
    ensure_schema_version()
    applied = []
    with managed_connection() as db:
        existing = {
            int(row[0])
            for row in db.execute("SELECT version FROM schema_migrations").fetchall()
        }
        for migration in MIGRATIONS:
            version = migration["version"]
            if version in existing:
                continue
            if migration.get("path"):
                db.executescript(_migration_sql(migration["path"]))
            db.execute(
                """
                INSERT OR IGNORE INTO schema_migrations (version, name)
                VALUES (?, ?)
                """,
                (version, migration["name"]),
            )
            applied.append(migration)
        db.commit()
    return {
        "current_version": get_schema_version(),
        "expected_version": CURRENT_SCHEMA_VERSION,
        "applied": applied,
    }


def get_schema_version() -> int:
    """Return the latest applied schema version."""
    with managed_connection() as db:
        row = db.execute(
            "SELECT MAX(version) FROM schema_migrations"
        ).fetchone()
    return int(row[0] or 0)


def get_migration_history() -> List[Dict]:
    """Return migration records."""
    with managed_connection(row_factory=True) as db:
        rows = db.execute(
            """
            SELECT version, name, applied_at
            FROM schema_migrations
            ORDER BY version
            """
        ).fetchall()
    return [dict(row) for row in rows]


__all__ = [
    "SCHEMA",
    "CURRENT_SCHEMA_VERSION",
    "ensure_schema_version",
    "apply_pending_migrations",
    "get_schema_version",
    "get_migration_history",
]
