"""
Fast ingestion entry point for AutoMediaIngest.

This module is intentionally lightweight. It is responsible for:

- Accepting a single file path from the command line.
- Performing minimal validation.
- Recording that an ingestion *would* occur in SQLite when possible.
- Emitting simple structured logs.
- Exiting quickly with an appropriate status code.

In the pre-project phase, this is the primary consumer boundary for the
fire-and-forget producer.

Design note:
- Ingestion should remain usable even if the SQLite database cannot be
  created or written (e.g. read-only filesystem, missing directory).
- In that case we still log the intent and exit with success (code 0),
  but include DB_STATUS=UNAVAILABLE in the log and omit db_id.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from pathlib import Path as _PathForLogs

from app.db import get_connection, record_ingest_intent


def _build_parser() -> argparse.ArgumentParser:
    """Build and return the argument parser for the ingest entry point."""
    parser = argparse.ArgumentParser(
        description=(
            "Record ingestion intent for a single filesystem path. "
            "This is a quick, fire-and-forget style entry point."
        )
    )
    parser.add_argument(
        "path",
        metavar="PATH",
        help="Container-visible path to the file that triggered ingestion.",
    )
    return parser


def _log(level: str, message: str, *, path: Optional[Path] = None, extra: str = "") -> None:
    """Log a simple, structured message to stdout and to logs/ingest.log.

    Format (single line, space-separated key=value pairs where practical):

        2025-01-01T12:00:00Z ingest.py LEVEL=INFO EVENT=INGEST_INTENT path=/foo/bar exists=true db_id=1

    This keeps logs easy to grep while remaining structured enough for later parsing.
    """
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    parts = [
        timestamp,
        "ingest.py",
        f"LEVEL={level}",
        message,
    ]
    if path is not None:
        parts.append(f"path={path}")
    if extra:
        parts.append(extra)
    line = " ".join(parts)

    # Always log to stdout
    sys.stdout.write(line + "\n")
    sys.stdout.flush()

    # Also append to logs/ingest.log, but never fail ingest if this breaks
    try:
        logs_dir = _PathForLogs("logs")
        logs_dir.mkdir(parents=True, exist_ok=True)
        log_file = logs_dir / "logs/ingest.log"
        with log_file.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        # Logging must not affect ingest semantics; ignore file I/O errors.
        pass


def main(argv: list[str] | None = None) -> int:
    """Entry point for the ingestion consumer.

    Returns a process exit code:
    - 0 on success (including when DB is unavailable but intent was logged)
    - 1 on usage or unexpected non-DB errors
    """
    if argv is None:
        argv = sys.argv[1:]

    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit:
        # argparse already printed a message; treat as usage error.
        _log("ERROR", "EVENT=USAGE_ERROR missing-or-invalid-arguments")
        return 1

    raw_path = args.path
    if not raw_path:
        _log("ERROR", "EVENT=VALIDATION_ERROR reason=missing-path")
        return 1

    path = Path(raw_path)

    # Tolerate missing files; producer may race with file creation/moves.
    exists_flag = path.exists()

    # If something exists at this path but it is not a regular file,
    # treat this as a validation error and do NOT record an ingest row.
    if exists_flag and not path.is_file():
        _log(
            "ERROR",
            "EVENT=VALIDATION_ERROR reason=not-a-regular-file",
            path=path,
        )
        return 1

    file_size: Optional[int]
    if exists_flag:
        try:
            file_size = path.stat().st_size
        except OSError:
            file_size = None
    else:
        file_size = None

    ingest_id: Optional[int] = None
    db_status = "RECORDED"

    try:
        with get_connection() as conn:
            ingest_id = record_ingest_intent(
                conn,
                original_path=str(path),
                original_filename=path.name,
                file_size=file_size,
                detected_at=datetime.now(timezone.utc),
                error_message=None,
            )
            conn.commit()
    except Exception as exc:  # noqa: BLE001
        # Database is unavailable or failed. For fire-and-forget semantics,
        # we still consider the ingestion attempt accepted, but we log that
        # persistence failed so operators can investigate.
        db_status = "UNAVAILABLE"
        _log(
            "ERROR",
            "EVENT=DB_ERROR failed-to-record-ingest-intent",
            path=path,
            extra=f"error={type(exc).__name__}",
        )

    # Always emit a final intent log, even if DB was unavailable.
    extra_fields_parts = [
        f"exists={str(exists_flag).lower()}",
        f"DB_STATUS={db_status}",
    ]
    if ingest_id is not None:
        extra_fields_parts.append(f"db_id={ingest_id}")
    extra_fields = " ".join(extra_fields_parts)

    _log(
        "INFO",
        "EVENT=INGEST_INTENT_RECORDED",
        path=path,
        extra=extra_fields,
    )

    # Even if DB failed, we return 0 so the producer never treats this as a
    # retriable or blocking error.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
