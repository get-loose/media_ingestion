from __future__ import annotations

import sqlite3
from pathlib import Path


DB_PATH = Path("state") / "ingest.db"


# Simple ANSI color helpers for readability in a terminal.
# If output is redirected to a file, colors will still be present; this is
# acceptable for a dev-only inspection tool.
class _Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    CYAN = "\033[36m"
    YELLOW = "\033[33m"
    GREEN = "\033[32m"
    MAGENTA = "\033[35m"


def _color(text: str, color: str) -> str:
    return f"{color}{text}{_Color.RESET}"


def _print_rows(cursor: sqlite3.Cursor, table: str, limit: int) -> None:
    """Print the last `limit` rows from `table`, showing all columns."""
    header = f"=== {table} (last {limit} rows) ==="
    print(_color(f"\n{header}", _Color.BOLD))

    try:
        cursor.execute(f"SELECT * FROM {table} ORDER BY id DESC LIMIT ?;", (limit,))
    except sqlite3.OperationalError as exc:
        print(_color(f"(table {table!r} not available: {exc})", _Color.YELLOW))
        return

    rows = cursor.fetchall()
    if not rows:
        print(_color("(no rows)", _Color.DIM))
        return

    col_names = [desc[0] for desc in cursor.description]
    # Colorize column headers
    print(_color(" | ".join(col_names), _Color.CYAN))
    print(_color("-" * 80, _Color.DIM))

    for idx, row in enumerate(rows, start=1):
        # Build a colored row: id in green, NULLs dimmed, others plain
        formatted_values: list[str] = []
        for col_name, value in zip(col_names, row):
            if value is None:
                formatted_values.append(_color("NULL", _Color.DIM))
            elif col_name == "id":
                formatted_values.append(_color(str(value), _Color.GREEN))
            else:
                formatted_values.append(str(value))

        print(" | ".join(formatted_values))

        # Add an empty line between entries for readability, except after last
        if idx != len(rows):
            print()


def main() -> int:
    if not DB_PATH.exists():
        print(_color(f"Database file not found at: {DB_PATH}", _Color.YELLOW))
        return 1

    try:
        limit_str = input("How many of the last entries should be shown? [default: 5] ").strip()
        limit = int(limit_str) if limit_str else 5
        if limit <= 0:
            print(_color("Please enter a positive integer.", _Color.YELLOW))
            return 1
    except ValueError:
        print(_color("Invalid number.", _Color.YELLOW))
        return 1

    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        _print_rows(cur, "ingest_log", limit)
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
