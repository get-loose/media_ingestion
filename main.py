"""
Top-level CLI entry point for AutoMediaIngest (pre-project phase).

For now this is a thin wrapper around app.ingest.main so that you can:

- Run `python main.py <path>` during local development, or
- Later replace this with a richer CLI without changing the ingest contract.

The real fire-and-forget producer in production will call `ingest.py`
directly inside the container, but having a single top-level entry point
is convenient for local experimentation.
"""

from __future__ import annotations

import sys

from app.ingest import main as ingest_main


def main(argv: list[str] | None = None) -> int:
    """Delegate to the ingestion entry point.

    This keeps the CLI surface small and predictable while allowing
    future expansion (e.g. subcommands) without breaking the current
    contract.
    """
    if argv is None:
        argv = sys.argv[1:]
    return ingest_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
