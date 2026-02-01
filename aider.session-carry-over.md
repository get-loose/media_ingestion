# Aider Session Carry-Over – Next Topic: First Simple Worker

Next session we want to discuss **a first-try, simple worker** that reasons over `ingest_log` and (conceptually) `library_items`, without yet implementing a real worker loop.

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
