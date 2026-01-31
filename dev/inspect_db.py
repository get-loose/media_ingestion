from __future__ import annotations

import sqlite3
from pathlib import Path


DB_PATH = Path("state") / "ingest.db"


def _print_rows(cursor: sqlite3.Cursor, table: str, limit: int) -> None:
    """Print the last `limit` rows from `table`, showing all columns."""
    print(f"\n=== {table} (last {limit} rows) ===")
    try:
        cursor.execute(f"SELECT * FROM {table} ORDER BY id DESC LIMIT ?;", (limit,))
    except sqlite3.OperationalError as exc:
        print(f"(table {table!r} not available: {exc})")
        return

    rows = cursor.fetchall()
    if not rows:
        print("(no rows)")
        return

    col_names = [desc[0] for desc in cursor.description]
    print(" | ".join(col_names))
    print("-" * 80)
    for row in rows:
        print(" | ".join(str(value) if value is not None else "NULL" for value in row))


def main() -> int:
    if not DB_PATH.exists():
        print(f"Database file not found at: {DB_PATH}")
        return 1

    try:
        limit_str = input("How many of the last entries should be shown? [default: 5] ").strip()
        limit = int(limit_str) if limit_str else 5
        if limit <= 0:
            print("Please enter a positive integer.")
            return 1
    except ValueError:
        print("Invalid number.")
        return 1

    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        _print_rows(cur, "ingest_log", limit)
        _print_rows(cur, "library_items", limit)
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
