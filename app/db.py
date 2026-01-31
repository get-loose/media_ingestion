"""
SQLite database access layer for AutoMediaIngest (pre-project phase).

Responsibilities:
- Own the SQLite connection lifecycle.
- Create and migrate the schema explicitly.
- Provide small, explicit functions for ingestion-related operations.

This module intentionally avoids business logic. It only knows how to:
- open the database
- ensure the schema exists
- perform basic inserts/queries

The actual ingestion behavior and decisions live in higher-level modules.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional

# In the final container, this will typically be `/config/state/ingest.db`.
# For local development, this is relative to the project root unless overridden.
DEFAULT_DB_PATH = Path("state") / "ingest.db"


@dataclass(frozen=True)
class DatabaseConfig:
    """Configuration for locating the SQLite database file."""

    path: Path = DEFAULT_DB_PATH

    @classmethod
    def from_default(cls) -> "DatabaseConfig":
        return cls(path=DEFAULT_DB_PATH)


def _ensure_parent_directory(path: Path) -> None:
    """Ensure the parent directory for the database file exists."""
    parent = path.parent
    if not parent.exists():
        parent.mkdir(parents=True, exist_ok=True)


def _apply_pragma_settings(conn: sqlite3.Connection) -> None:
    """Apply SQLite PRAGMA settings appropriate for an embedded app-owned DB.

    These are conservative defaults aimed at correctness and durability.
    They can be revisited later if performance tuning is needed.
    """
    cursor = conn.cursor()
    # WAL mode improves concurrency and durability for append-heavy workloads.
    cursor.execute("PRAGMA journal_mode=WAL;")
    # Synchronous FULL is safest; can be relaxed later if needed.
    cursor.execute("PRAGMA synchronous=FULL;")
    cursor.close()


def _initialize_schema(conn: sqlite3.Connection) -> None:
    """Create the initial schema if it does not already exist.

    Schema is based on `SQLite_schema_design.md` and `PROJECT_SPEC.md`.
    """
    cursor = conn.cursor()

    # ingest_log: append-only ingestion history
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS ingest_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_path TEXT NOT NULL,
            original_filename TEXT NOT NULL,
            file_size INTEGER,
            detected_at TEXT NOT NULL,
            processed_flag INTEGER NOT NULL DEFAULT 0,
            group_id INTEGER,
            error_message TEXT
        );
        """
    )

    # library_items: current canonical media library state
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS library_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ingest_id INTEGER NOT NULL,
            current_path TEXT NOT NULL,
            title TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            metadata TEXT,
            fingerprint TEXT,
            FOREIGN KEY (ingest_id) REFERENCES ingest_log(id)
        );
        """
    )

    conn.commit()
    cursor.close()


@contextmanager
def get_connection(config: Optional[DatabaseConfig] = None) -> Iterator[sqlite3.Connection]:
    """Context manager that yields a SQLite connection.

    Ensures:
    - parent directory exists
    - PRAGMAs are applied
    - schema is initialized

    The caller is responsible for committing/rolling back as needed.
    """
    if config is None:
        config = DatabaseConfig.from_default()

    _ensure_parent_directory(config.path)

    conn = sqlite3.connect(config.path)
    try:
        _apply_pragma_settings(conn)
        _initialize_schema(conn)
        yield conn
    finally:
        conn.close()


def record_ingest_intent(
    conn: sqlite3.Connection,
    *,
    original_path: str,
    original_filename: str,
    file_size: Optional[int],
    detected_at: Optional[datetime] = None,
    error_message: Optional[str] = None,
) -> int:
    """Insert a new row into ingest_log and return its primary key.

    This function is intentionally minimal and does not enforce business rules.
    It assumes the caller has already validated inputs as needed.

    Args:
        conn: An open SQLite connection.
        original_path: Full path as seen by the container.
        original_filename: Basename of the file.
        file_size: File size in bytes, or None if unknown.
        detected_at: Timestamp of detection; if None, uses current UTC time.
        error_message: Optional error message to record.

    Returns:
        The auto-incremented primary key of the new ingest_log row.
    """
    if detected_at is None:
        detected_at = datetime.now(timezone.utc)

    detected_at_str = detected_at.isoformat()

    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO ingest_log (
            original_path,
            original_filename,
            file_size,
            detected_at,
            processed_flag,
            group_id,
            error_message
        )
        VALUES (?, ?, ?, ?, 0, NULL, ?);
        """,
        (
            original_path,
            original_filename,
            file_size,
            detected_at_str,
            error_message,
        ),
    )
    ingest_id = int(cursor.lastrowid)
    conn.commit()
    cursor.close()
    return ingest_id
