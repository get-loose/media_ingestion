from __future__ import annotations

import sys
from pathlib import Path

from app.ingest import main as ingest_main


def main(argv: list[str] | None = None) -> int:
    """Development helper: accept a path and delegate to app.ingest.main.

    This keeps the ingest boundary (app.ingest.main) unchanged while
    allowing experiments with different producer-style wrappers.
    """
    if argv is None:
        argv = sys.argv[1:]

    if not argv:
        print("Usage: path_ingest.py PATH", file=sys.stderr)
        return 1

    raw_path = argv[0]
    if not raw_path:
        print("Error: PATH must be a non-empty string", file=sys.stderr)
        return 1

    # Normalize to a string path; app.ingest.main expects a string argument.
    path = Path(raw_path)

    # Delegate to the existing ingest entry point.
    # Note: we pass a list of args, just like a CLI would.
    return ingest_main([str(path)])


if __name__ == "__main__":
    raise SystemExit(main())
