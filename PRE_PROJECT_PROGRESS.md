# Pre-Project Progress – AutoMediaIngest

This document tracks what’s implemented in the **pre-project** phase and what’s still pending, based on `PRE_PROJECT.md` and `PROJECT_SPEC.md`.

---

## 1. Ingestion Spine Overview

Target shape (pre-project):

```text
[ Producer Stub ] → dev/path_ingest.py
        |
        v
[ Consumer ] → app/ingest.py → app/db.py (SQLite) → logs → exit
```

The goal is to validate this boundary locally on Teddy before any Unraid/Docker work.

---

## 2. What’s Implemented

### 2.1 Consumer Entry Point – `app/ingest.py`

**Status:** Implemented

- Accepts a **single path argument** via CLI.
- Validates:
  - Non-empty argument (`raw_path`).
- Tolerates:
  - Missing files (no hard failure if `path.exists()` is false).
- Derives:
  - `original_path` (string form of the path).
  - `original_filename` (`Path(...).name`).
  - `file_size` (if file exists and is a regular file; otherwise `None`).
- Interacts with DB:
  - Uses `get_connection()` from `app.db`.
  - Calls `record_ingest_intent(...)` to append to `ingest_log`.
- Logging:
  - Writes structured log lines to:
    - `stdout`
    - `logs/ingest.log`
  - Key events:
    - `EVENT=USAGE_ERROR`
    - `EVENT=VALIDATION_ERROR`
    - `EVENT=DB_ERROR`
    - `EVENT=INGEST_INTENT_RECORDED`
  - Includes flags like:
    - `exists=true/false`
    - `DB_STATUS=RECORDED` or `DB_STATUS=UNAVAILABLE`
    - `db_id=<ingest_log.id>` when available.
- Exit codes:
  - `0` on success (including when DB is unavailable but intent was logged).
  - `1` on usage/argument errors.

---

### 2.2 Database Layer – `app/db.py`

**Status:** Implemented

- DB location:
  - Default: `state/ingest.db` via `DEFAULT_DB_PATH`.
  - Configurable via `DatabaseConfig`.
- Connection management:
  - `get_connection(config: Optional[DatabaseConfig])`:
    - Ensures parent directory exists.
    - Applies PRAGMAs once per process:
      - `journal_mode=WAL`
      - `synchronous=FULL`
    - Ensures schema exists once per process.
- Schema:
  - `ingest_log`:
    - `id` (PK)
    - `original_path`
    - `original_filename`
    - `file_size` (nullable)
    - `detected_at` (TEXT, ISO timestamp)
    - `processed_flag` (int, default 0)
    - `group_id` (nullable, future use)
    - `error_message` (nullable)
  - `library_items`:
    - `id` (PK)
    - `ingest_id` (FK → `ingest_log.id`)
    - `current_path`
    - `title` (nullable)
    - `status` (TEXT, default `'pending'`)
    - `metadata` (TEXT, JSON payload)
    - `fingerprint` (TEXT)
- Operations:
  - `record_ingest_intent(conn, ...) -> int`:
    - Inserts a row into `ingest_log`.
    - Returns the new `id`.
    - Does **not** commit; caller controls transactions.
- No business logic:
  - `db.py` only knows SQL and schema, not ingestion policy.

---

### 2.3 Producer Stub – `dev/path_ingest.py`

**Status:** Implemented

- Simulates the **Unraid host** producer.
- CLI:
  - Accepts a single `PATH` argument.
  - Prints simple usage errors to `stderr` if missing/empty.
- Behavior:
  - Logs a producer-side dispatch event:
    - To `stdout`.
    - To `dev/host.log`.
    - Example:
      - `2026-01-31T17:05:00Z host LEVEL=INFO EVENT=DISPATCH path=data/inbox/example.mkv`
  - Delegates to `app.ingest.main([str(path)])`.
- Semantics:
  - Fire-and-forget style:
    - No retries.
    - No inspection of results beyond the immediate return code.

---

### 2.4 Inspection Tools – `dev/inspect_*.py`

**Status:** Implemented

- `dev/inspect_ingest_log.py`:
  - Asks: “How many of the last entries should be shown?”
  - Prints last N rows from `ingest_log` (all columns).
- `dev/inspect_library_items.py`:
  - Same pattern, but for `library_items`.
  - Currently shows `(no rows)` because we don’t populate `library_items` yet.
- `dev/inspect_db.py`:
  - Deprecated stub pointing to the two scripts above.

These tools are for manual verification of DB state during pre-project.

---

### 2.5 Logging Separation

**Status:** Implemented

- Producer logs:
  - `dev/host.log` (written by `dev/path_ingest.py`).
  - Represents Unraid-side behavior.
- Consumer logs:
  - `logs/ingest.log` (written by `app/ingest.py`).
  - Represents container/app-side behavior.
- Both:
  - Structured, append-only.
  - Never read by the application to make decisions.

---

## 3. What’s Intentionally Not Implemented (Yet)

These are **out of scope** for pre-project, per `PRE_PROJECT.md`:

- No Unraid integration (no real `inotifywait`).
- No Dockerfiles or container wiring.
- No background workers or processing loops.
- No media grouping logic.
- No renaming or moving files.
- No retries or schedulers.
- No UI/TUI.
- No runtime AI/LLM usage.

---

## 4. Next Steps Within Pre-Project

These are the remaining **pre-project** tasks, at a high level.

### 4.1 Exercise and Validate the Contract

- Run realistic scenarios via `dev/path_ingest.py`:
  - Existing file.
  - Missing file.
  - Same file ingested multiple times.
  - Path that is a directory.
- For each scenario, verify:
  - `dev/host.log` (producer behavior).
  - `logs/ingest.log` (consumer behavior).
  - `dev/inspect_ingest_log.py` output (DB history).
- Confirm that:
  - Exit codes match expectations.
  - Log lines contain the right keys (`EVENT=...`, `exists=...`, `DB_STATUS=...`, `db_id=...`).
  - `ingest_log` is append-only and tolerant of duplicates.

### 4.2 Flesh Out `integration/CONTRACT.md`

- Document the **producer → consumer** contract:
  - CLI contract for `app/ingest.py`:
    - Arguments.
    - Exit codes.
  - Logging contract:
    - Expected fields and events in `logs/ingest.log`.
    - Expected fields and events in `dev/host.log`.
  - DB contract:
    - What gets written to `ingest_log` for each scenario.
- Adjust small details in `ingest.py` or `dev/path_ingest.py` if needed to match the written contract.

### 4.3 Prepare for Post–Pre-Project Work (Design Only)

- Clarify, in docs (not code), how a future worker will:
  - Read from `ingest_log`.
  - Populate and maintain `library_items`.
- Keep `library_items` schema and `dev/inspect_library_items.py` ready, but:
  - Do **not** implement worker loops or background processing yet.

---

## 5. Quick Checklist

- [x] `app/ingest.py` entrypoint implemented.
- [x] `app/db.py` with schema + `record_ingest_intent`.
- [x] `dev/path_ingest.py` producer stub with logging.
- [x] `dev/inspect_ingest_log.py` and `dev/inspect_library_items.py`.
- [ ] Run and record a few end-to-end scenarios.
- [ ] Finalize `integration/CONTRACT.md` to describe the boundary.
- [ ] Sketch (in docs) how `library_items` will be used in the next phase.
