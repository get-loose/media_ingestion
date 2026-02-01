# Aider Session Carry-Over – Next Topic: First Simple Worker

Next session we want to discuss **a first-try, simple worker** that reasons over `ingest_log` and (conceptually) `library_items`, without yet implementing a real worker loop.

## 1. Design Truths to Carry Over

These are **gospel** and must not be contradicted:

- From `PROJECT_BIBLE.md`:
  - `ingest_log`:
    - Append-only history of ingestion attempts that passed validation.
    - No deduplication at this boundary.
    - Rows are never deleted in normal operation.
  - `library_items`:
    - Represents the **truth** about media units (one row per media unit, not per file).
    - Deleting rows is a **big event**, not normal behavior.
    - A row may remain even if:
      - Its `current_path` is not covered by any configured library path.
      - Its file is no longer present on disk.
  - Library paths:
    - A future `library_paths` config is **not** truth; it can be wrong or incomplete.
    - `library_items` remains authoritative even when not covered by `library_paths`.

- From `integration/CONTRACT.md`:
  - `exists=true/false`:
    - Reflects **filesystem state at ingest time only**.
    - Does **not** indicate “new vs existing media unit”.
  - `EVENT=INGEST_INTENT_RECORDED`:
    - Emitted only when validation passes (file or missing file).
    - Includes `exists`, `DB_STATUS`, and optional `db_id`.
  - Validation errors (e.g. directory path) do **not** create `ingest_log` rows.

## 2. Current Implementation to Have in Context

We will reason about a worker **on top of** the existing spine. Please re-add these files (or their contents) in the next session:

- `app/db.py`
  - Schema for:
    - `ingest_log`
    - `library_items`
  - `record_ingest_intent(...)` behavior.

- `app/ingest.py`
  - How `ingest_log` rows are created.
  - Validation rules:
    - Directory → `EVENT=VALIDATION_ERROR`, exit 1, no `ingest_log` row.
  - Logging and exit codes.

- `dev/path_ingest.py`
  - Producer stub behavior.
  - Format of `dev/host.log` lines (`EVENT=DISPATCH`).

- `dev/inspect_ingest_log.py`
  - How we inspect `ingest_log` (including colored output and dotted `file_size`).

- `dev/inspect_library_items.py`
  - How we will inspect `library_items` once we start populating it.

- `dev/mediawalker_test/mediawalker_test.sh`
- `dev/mediawalker_test/media_walker_input`
  - How we bulk-populate `ingest_log` in dev.
  - Remember: this script is **experimental**, dev-only, and not part of the ingestion contract.

- `PRE_PROJECT.md`
- `PRE_PROJECT_PROGRESS.md`
  - To keep pre-project guardrails in mind:
    - No real worker loops yet.
    - No background processing.
    - Worker design is **docs-first**, code (if any) must be explicit, one-off helpers.

## 3. Brainstorming Context for Worker & Media Units

Re-add these brainstorming docs so we can align the worker design with existing ideas:

- `dev/brainstorming/2026-01-31T20-00-brainstorm.md`
- `dev/brainstorming/2026-01-31T20-00-preliminary_conclusions.md`
- `dev/brainstorming/2026-02-01T-media_walker_and_library_paths.md`

Key ideas to remember:

- `library_items` rows represent **media units**:
  - A media unit = primary media file (mp4/mkv/…) + assets (srt, nfo, jpg).
  - Assets attach to a media unit; they are not separate `library_items` rows.
- Future worker responsibilities (design only for now):
  - Read from `ingest_log` (likely `processed_flag = 0`).
  - For each row:
    - Decide if it is a **primary media file** (mp4/mkv/…) or an **asset** (srt/nfo/jpg).
    - Decide if it represents a **new media unit** or an **update** to an existing one.
  - Use:
    - File type (extension),
    - Path/filename heuristics (e.g. similarly named files in same folder),
    - Eventually `fingerprint`,
    to make those decisions.

## 4. Next-Session Goal: Simple Worker Decision Table

In the next session we want to:

- Design a **small decision table** (docs, not code) that, given an `ingest_log` row with:
  - Extension in `{mp4, mkv, srt, nfo, jpg}`,
  - Path and filename,
- Decides:
  - Is this a **primary media candidate** (mp4/mkv) or an **asset** (srt/nfo/jpg)?
  - If primary:
    - Should it create a new `library_items` row?
    - Or attach to / update an existing media unit?
  - If asset:
    - Which media unit (if any) should it be associated with?
      - Based on “similarly named files in the same folder” (e.g. `movie.mkv`, `movie.srt`, `movie.nfo`, `movie.jpg`).

Constraints to keep in mind:

- Pre-project: no real worker loop yet.
- We can:
  - Define the decision table.
  - Maybe sketch a one-off, explicit script that **reads** `ingest_log` and prints what it *would* do.
- We must not:
  - Implement a background worker or continuous processing.

## 5. One-Liner to Re-Add Files in Next Session

For quick copy-paste into Aider next time, use:

```text
Please add these files to the chat: PROJECT_BIBLE.md, integration/CONTRACT.md, PRE_PROJECT.md, PRE_PROJECT_PROGRESS.md, app/db.py, app/ingest.py, dev/path_ingest.py, dev/inspect_ingest_log.py, dev/inspect_library_items.py, dev/mediawalker_test/mediawalker_test.sh, dev/mediawalker_test/media_walker_input, dev/brainstorming/2026-01-31T20-00-brainstorm.md, dev/brainstorming/2026-01-31T20-00-preliminary_conclusions.md, dev/brainstorming/2026-02-01T-media_walker_and_library_paths.md
```
