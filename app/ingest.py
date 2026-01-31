"""
Fast ingestion entry point for AutoMediaIngest.

This module is intentionally lightweight. It is responsible for:

- Accepting a single file path from the command line.
- Performing minimal validation.
- Recording that an ingestion *would* occur (for now, via stdout logging).
- Exiting quickly with an appropriate status code.

In the pre-project phase, this stub does not yet talk to the real SQLite
database. That integration will be added once db.py and the schema are in
place. The CLI contract, however, is already aligned with the project spec.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path


def _build_parser() -> argparse.ArgumentParser:
    """Build and return the argument parser for the ingest entry point."""
    parser = argparse.ArgumentParser(
        description=(
            "Record ingestion intent for a single filesystem path. "
            "This is a fast, fire-and-forget style entry point."
        )
    )
    parser.add_argument(
        "path",
        metavar="PATH",
        help="Container-visible path to the file that triggered ingestion.",
    )
    return parser


def _log(message: str) -> None:
    """Log a simple, structured message to stdout.

    In this pre-project phase we keep logging minimal and stdout-only.
    A future version will likely use the standard logging module and
    write to a dedicated log file.
    """
    timestamp = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    sys.stdout.write(f"{timestamp} ingest.py {message}\n")
    sys.stdout.flush()


def main(argv: list[str] | None = None) -> int:
    """Entry point for the ingestion consumer.

    Returns a process exit code:
    - 0 on success
    - 1 on usage or unexpected errors
    """
    if argv is None:
        argv = sys.argv[1:]

    parser = _build_parser()
    args = parser.parse_args(argv)

    raw_path = args.path
    if not raw_path:
        _log("ERROR missing-path")
        return 1

    path = Path(raw_path)

    # NOTE: In the final system, the producer may race with file creation or
    # movement, so we *must* tolerate missing files. For now we simply log
    # what we see without failing hard.
    exists_flag = path.exists()
    _log(
        f"INGEST_INTENT path={path} exists={str(exists_flag).lower()}"
    )

    # Placeholder for future DB integration:
    # - open SQLite connection via db.py
    # - insert into ingest_log
    # - commit and close
    #
    # For now, we just return success to keep the CLI contract stable.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
