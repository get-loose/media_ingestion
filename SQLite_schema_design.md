# SQLite Schema Design Notes

## Design Goals

- Append-first ingestion history
- Clear separation between:
  - immutable ingestion events
  - current library state
- Idempotency support
- Ability to rebuild state from history
- Safe under duplicate and out-of-order events

---

## ingest_log (Immutable History)

Purpose:
- Record every ingestion attempt
- Serve as an audit trail
- Enable re-hydration / replay

Characteristics:
- Rows are never deleted
- Rows are rarely updated (status only)
- Inserts are fast and frequent

Conceptual fields:
- id (primary key)
- original_path
- original_filename
- file_size (optional, nullable early)
- detected_at (timestamp)
- processed_flag (boolean)
- group_id (nullable, future use)
- error_message (nullable)

---

## library_items (Current State)

Purpose:
- Represent the current canonical media library
- Used by UI and future APIs

Characteristics:
- Represents the *latest known state*
- Can be rebuilt from ingest_log if needed

Conceptual fields:
- id (primary key)
- ingest_id (foreign key to ingest_log)
- current_path
- title
- status
- metadata (JSON)
- fingerprint (hash of file segment)

---

## Migration Philosophy

- Early versions prioritize correctness and clarity
- Schema changes are expected
- Migrations should be possible without data loss
- ingest_log should remain stable as much as possible

