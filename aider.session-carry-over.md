# Aider Session Carry-Over – Next Topic: First Simple Worker

Next session we want to discuss **a first-try, simple worker** that reasons over `ingest_log` and (conceptually) `library_items`, without yet implementing a real worker loop.

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

## 5. Draft Decision Table (First Pass)

This table assumes:
- Extensions in `{mp4, mkv, srt, nfo, jpg}`.
- We only use:
  - Extension,
  - Directory,
  - Basename without extension,
  - Very simple “similarly named in same folder” heuristics.
- We do **not** rely on `fingerprint` yet.

Legend:
- `dir(path)`: directory component.
- `stem(path)`: filename without extension.
- `ext(path)`: lowercase extension without dot.
- “Existing media unit in folder with same stem” means:
  - A `library_items` row whose `current_path` is in the same directory,
  - And whose primary file’s stem matches `stem(path)`.

### Step 1 – Classify primary vs asset

| Condition                         | Classification | Notes                                  |
|----------------------------------|----------------|----------------------------------------|
| `ext in {mp4, mkv}`              | PRIMARY        | Candidate for media unit root.        |
| `ext in {srt, nfo, jpg}`         | ASSET          | Attachable to a primary media unit.   |
| Anything else                    | IGNORE/FUTURE  | Out of scope for this first worker.   |

### Step 2 – Primary media handling (mp4/mkv)

Given a PRIMARY row:

| Situation                                                                 | Action                                                                 | Rationale |
|---------------------------------------------------------------------------|-------------------------------------------------------------------------|-----------|
| No existing `library_items` in same folder with same stem                | Create **new media unit** (`library_items` row).                       | New title in this folder. |
| Existing media unit in same folder with same stem, same extension        | Treat as **update/replace** of primary file for that media unit.      | Same logical media, new file version. |
| Existing media unit in same folder with same stem, different extension   | Attach as **alternate primary** (same media unit, multiple formats).   | e.g. `movie.mkv` and `movie.mp4`. |
| Existing media unit in different folder but same stem                    | **Do not auto-link**; treat as **new media unit**.                     | Avoid cross-folder collisions; future heuristics may revisit. |
| Multiple media units in same folder with same stem (should be rare)     | Mark as **ambiguous**; log decision as “needs manual resolution”.      | Avoid guessing when state is inconsistent. |

### Step 3 – Asset handling (srt/nfo/jpg)

Given an ASSET row:

| Situation                                                                 | Action                                                                 | Rationale |
|---------------------------------------------------------------------------|-------------------------------------------------------------------------|-----------|
| Exactly one primary media unit in same folder with same stem             | Attach asset to that media unit.                                      | Clear 1:1 match. |
| Multiple primary media units in same folder with same stem (e.g. cut1/2) | Mark as **ambiguous**; do not auto-attach.                            | Avoid mis-association. |
| No primary media unit in same folder with same stem                      | Record as **unattached asset** (or “orphan asset”) for now.           | Primary may arrive later or be missing. |
| Asset filename includes language/extra tags (e.g. `movie.en.srt`)        | Use base stem before first dot (`movie`) to match; otherwise as above. | Simple language-tag heuristic. |

### Step 4 – Interaction with `ingest_log.processed_flag`

For this first worker:

- Only consider `ingest_log` rows where `processed_flag = 0`.
- For each processed row:
  - Decide classification and action using the above tables.
  - If we can make a **definite** decision (no ambiguity):
    - Update `library_items` accordingly.
    - Set `processed_flag = 1` for that `ingest_log` row.
  - If decision is **ambiguous**:
    - Leave `processed_flag = 0` (or set a separate status field if we add one later).
    - Emit a log line describing the ambiguity and what evidence was considered.

(Implementation of this behavior is **future**; for now this is design only.)

## 6. One-Off “What Would I Do?” Script (Concept Sketch)

In this pre-project phase, instead of a real worker loop, we may later add a **one-off helper** like:

- `dev/worker_dry_run.py` (name TBD)

Behavior (conceptual only):

- Reads a subset of `ingest_log` rows (e.g. latest N, or where `processed_flag = 0`).
- For each row:
  - Applies the decision table above.
  - Prints a line such as:

    - `DECISION primary:new_unit path=/media/movies/movie.mkv reason=no_existing_same_stem`
    - `DECISION asset:attach path=/media/movies/movie.srt target=/media/movies/movie.mkv reason=single_match_same_stem`
    - `DECISION asset:ambiguous path=/media/movies/movie.srt reason=multiple_primary_same_stem`
    - `DECISION asset:orphan path=/media/movies/movie.srt reason=no_primary_same_stem`

- Does **not**:
  - Modify `library_items`.
  - Flip `processed_flag`.
  - Run continuously.

This keeps us within pre-project guardrails while validating the decision logic against real `ingest_log` data.

## 7. One-Liner to Re-Add Files in Next Session

For quick copy-paste into Aider next time, use:

```text
/add PROJECT_BIBLE.md integration/CONTRACT.md PRE_PROJECT.md PRE_PROJECT_PROGRESS.md app/db.py app/ingest.py dev/path_ingest.py dev/inspect_ingest_log.py dev/inspect_library_items.py dev/mediawalker_test/mediawalker_test.sh dev/mediawalker_test/media_walker_input dev/brainstorming/2026-01-31T20-00-brainstorm.md dev/brainstorming/2026-01-31T20-00-preliminary_conclusions.md dev/brainstorming/2026-02-01T-media_walker_and_library_paths.md
```
