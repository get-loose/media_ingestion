from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

from app.ingest import main as ingest_main


def _log_host(message: str, *, path: Path | None = None, extra: str = "") -> None:
    """Log a simple, structured producer-side message to dev/host.log.

    This emulates the Unraid host script logs, separate from the app logs.
    Format example:

        2025-01-01T12:00:00Z host LEVEL=INFO EVENT=DISPATCH path=/foo/bar
    """
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    parts: list[str] = [
        timestamp,
        "host",
        "LEVEL=INFO",
        message,
    ]
    if path is not None:
        parts.append(f"path={path}")
    if extra:
        parts.append(extra)
    line = " ".join(parts)

    # Log to stdout for visibility during development.
    sys.stdout.write(line + "\n")
    sys.stdout.flush()

    # Append to dev/host.log, but never affect behavior if this fails.
    try:
        dev_dir = Path("dev")
        dev_dir.mkdir(parents=True, exist_ok=True)
        log_file = dev_dir / "host.log"
        with log_file.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except Exception:
        # Producer logging must not affect dispatch semantics.
        pass


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

    # Log the producer-side dispatch event.
    _log_host("EVENT=DISPATCH", path=path)

    # Delegate to the existing ingest entry point.
    # Note: we pass a list of args, just like a CLI would.
    return ingest_main([str(path)])


if __name__ == "__main__":
    raise SystemExit(main())
