from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _run(cmd: list[str]) -> int:
    """Run a command, stream its output, and return its exit code."""
    print(f"\n$ {' '.join(cmd)}")
    result = subprocess.run(cmd)
    print(f"(exit code: {result.returncode})")
    return result.returncode


def main() -> int:
    """Simple end-to-end smoke test for the ingestion spine.

    It will:
    - Ingest an existing file (if present).
    - Ingest a missing file.
    - Ingest a directory (expected validation error).
    - Show the last few ingest_log rows.
    """
    project_root = Path(__file__).resolve().parent.parent
    example_file = project_root / "data" / "inbox" / "example.mkv"
    missing_file = project_root / "data" / "inbox" / "does_not_exist.mkv"
    inbox_dir = project_root / "data" / "inbox"

    # 1. Existing file (if it exists)
    if example_file.exists() and example_file.is_file():
        _run(
            [
                sys.executable,
                "-m",
                "dev.path_ingest",
                str(example_file.relative_to(project_root)),
            ]
        )
    else:
        print("\n[skip] example file does not exist at data/inbox/example.mkv")

    # 2. Missing file
    _run(
        [
            sys.executable,
            "-m",
            "dev.path_ingest",
            str(missing_file.relative_to(project_root)),
        ]
    )

    # 3. Directory (expected validation error, no DB row)
    if inbox_dir.exists() and inbox_dir.is_dir():
        _run(
            [
                sys.executable,
                "-m",
                "dev.path_ingest",
                str(inbox_dir.relative_to(project_root)),
            ]
        )
    else:
        print("\n[skip] inbox directory does not exist at data/inbox")

    # 4. Show last few ingest_log rows
    print("\n=== Inspecting ingest_log ===")
    _run(
        [
            sys.executable,
            "dev/inspect_ingest_log.py",
        ]
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
