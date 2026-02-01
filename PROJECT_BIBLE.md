# Project Bible – AutoMediaIngest

This document records **final, authoritative design decisions** for AutoMediaIngest.

- It is intentionally conservative and updated slowly.
- Only decisions that are considered **gospel** belong here.
- Changing or removing an item in this document is a **big event** and should be treated as a versioned design change.

If a question or proposal conflicts with this document, that conflict must be made explicit and resolved before implementation.

---

## 1. Core Architecture

1.1. **Database Ownership**

- The application owns a single SQLite database file.
- In the final deployment, this database lives inside the application container, backed by a mounted `/config` directory.
- There is no separate database service or networked DB dependency.

1.2. **Ingestion Spine**

- The ingestion boundary is:

  ```text
  Producer (host) → app.ingest (container) → SQLite → logs → exit
  ```

- The producer is fire-and-forget:
  - Never waits for results.
  - Never retries.
  - Never inspects exit codes.

- The consumer (`app.ingest`) must:
  - Accept a single path argument.
  - Perform minimal validation.
  - Attempt to record ingestion intent in SQLite.
  - Emit structured logs.
  - Exit quickly.

---

## 2. Database Tables and Roles

2.1. **`ingest_log` – Immutable Ingestion History**

- `ingest_log` is an append-only history of ingestion attempts that passed validation.
- Rows are never deleted.
- Rows are rarely updated (only `processed_flag` and possibly `error_message` in later phases).
- There is no deduplication at this boundary:
  - Multiple ingests of the same path or file are expected and recorded as separate rows.

2.2. **`library_items` – Canonical Media Units**

- `library_items` represents the **truth** about media units.
- Each row corresponds to a **media unit** (logical item for Kodi / NFO), not every individual file.
- Deleting rows from `library_items` is a **big event** and is not part of normal operation.
- A `library_items` row may remain even if:
  - Its path is not covered by any configured library path.
  - Its file is no longer present on disk.

- The exact definition of a “media unit” and the detailed lifecycle of `library_items` are **not yet finalized** and are intentionally left out of this bible for now.

---

## 3. Contracts and Behavior

3.1. **Consumer Contract (`app.ingest`)**

- The CLI contract and logging behavior of `app.ingest` are defined in `integration/CONTRACT.md`.
- `app.ingest` must:
  - Return exit code `0` for all non-usage, non-validation errors, even if the database is unavailable.
  - Never retry database operations.
  - Never read logs to make runtime decisions.

3.2. **Logs**

- Logs are structured, append-only, and best-effort.
- Logs exist to explain behavior and support debugging.
- Logs are never used as an input to application logic.

---

## 4. Bible Governance

- This document only contains decisions that are considered **final** at the current stage.
- Brainstorming, open questions, and tentative designs belong in separate documents under `dev/brainstorming/` or similar.
- Creating a **new version** of this bible (changing or retracting gospel items) is a deliberate design step and should not be done lightly.
