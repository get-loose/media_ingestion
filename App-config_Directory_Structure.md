# /config Directory Structure

/config is the single persistent volume mounted into the container.

It must contain all mutable state.

Proposed structure:

/config/
├── ingest.db        # SQLite database
├── logs/
│   ├── ingest.log
│   └── worker.log   # future
└── state/
    └── version.txt  # optional schema/app versioning

Rules:
- Code must not assume absolute host paths
- All paths must be relative to /config
- /config must be replaceable or backed up as a unit

