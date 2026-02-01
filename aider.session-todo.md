# Aider Session Carry-Over – Next Topic: Simple Worker Decision Table

## 1. Assumptions

- Ingestion spine is stable:
  - `dev/path_ingest.py` → `app/ingest.py` → `app/db.py` → `ingest_log`
- `library_items` exists but is effectively empty.
- PRE-PROJECT constraints:
  - No worker loops.
  - No writes to `library_items`.
  - No changes to `processed_flag`.

## 2. Next-Session Goal (Docs Only)

- Design a decision table for a future worker that:
  - Reads `ingest_log` rows.
  - Uses only:
    - `original_path` (directory + filename)
    - Lowercased file extension
  - Decides per row:
    - PRIMARY vs ASSET vs IGNORE/FUTURE.
    - For PRIMARY:
      - New media unit vs update vs alternate.
    - For ASSET:
      - Attach vs ambiguous vs orphan.

## 3. Draft Decision Rules (To Refine)

### 3.1 Classification by Extension

- PRIMARY: `ext in {mp4, mkv}`
- ASSET: `ext in {srt, nfo, jpg}`
- Otherwise: IGNORE/FUTURE

### 3.2 Primary Handling (mp4/mkv)

- Use:
  - `dir(path)` – directory of `original_path`
  - `stem(path)` – filename without extension
  - Heuristic: “same folder + same stem” groups related files
- Rules:
  - No existing media unit with same folder + stem:
    - → PRIMARY:new_unit
  - Existing media unit, same folder + stem, same extension:
    - → PRIMARY:update/replace
  - Existing media unit, same folder + stem, different extension:
    - → PRIMARY:alternate
  - Existing media unit with same stem but different folder:
    - → PRIMARY:new_unit
  - Multiple media units with same folder + stem:
    - → PRIMARY:ambiguous

### 3.3 Asset Handling (srt/nfo/jpg)

- Use same folder + stem heuristic.
- Rules:
  - Exactly one primary in same folder + stem:
    - → ASSET:attach
  - Multiple primaries in same folder + stem:
    - → ASSET:ambiguous
  - No primary in same folder + stem:
    - → ASSET:orphan
  - Filenames like `movie.en.srt`:
    - Use base stem before first dot (`movie`) for matching.

### 3.4 `processed_flag` (Future Only)

- Worker would:
  - Consider only rows with `processed_flag = 0`.
  - On definite decision:
    - Update `library_items`.
    - Set `processed_flag = 1`.
  - On ambiguous decision:
    - Leave `processed_flag = 0`.
    - Log ambiguity.
- Next session: refine rules only; no implementation.

## 4. Optional Dev Helper (Design Only)

- Possible script: `dev/worker_dry_run.py`
- Behavior:
  - Read subset of `ingest_log` (e.g. latest N or `processed_flag = 0`).
  - Apply decision table in pure Python.
  - Print lines like:
    - `DECISION primary:new_unit path=... reason=no_existing_same_stem`
    - `DECISION primary:update path=... target=... reason=existing_same_stem_same_ext`
    - `DECISION primary:alternate path=... target=... reason=existing_same_stem_diff_ext`
    - `DECISION asset:attach path=... target=... reason=single_match_same_stem`
    - `DECISION asset:ambiguous path=... reason=multiple_primary_same_stem`
    - `DECISION asset:orphan path=... reason=no_primary_same_stem`
- Constraints:
  - No writes to `library_items`.
  - No changes to `processed_flag`.
  - No background loop.

## 5. Anonymized Dev / Sharing Workflow (Design Only)

- Goal: enable sharing realistic ingest data in chat without exposing real paths or filenames.

- Design a docs-only plan for an anonymized mirror of:
  - `ingest_log`
  - `library_items`
  - (optionally) selected log lines

- Requirements:
  - Folder paths, subfolders, and filenames are **deterministically anonymized**.
  - Directory structure is preserved (same depth, same counts).
  - Same original path → same anonymized path (stable mapping).
  - No way to reverse from anonymized data back to real paths.

- Proposed approach:
  - Dev-only helper script, e.g. `dev/anonymize_snapshot.py`.
  - Reads from the real DB and logs; writes:
    - Either a separate SQLite file (e.g. `state/anonymized_ingest.db`), or
    - A JSON/text snapshot suitable for pasting into chat.
  - Mapping strategy (examples to refine):
    - Directories: `/media/Movies/Some Show/Season 01/` → `/D1/D2/D3/D4/`
    - Filenames: `Some.Show.S01E01.1080p.mkv` → `F0001.mkv`
  - Decide which fields to anonymize vs keep:
    - Anonymize: `original_path`, `original_filename`, any path-like fields.
    - Keep: timestamps, sizes, extensions, status flags.

- Constraints:
  - Must not modify the production DB or logs.
  - Must not introduce runtime dependencies (dev-only helper).
  - PRE-PROJECT: no background loops; explicit one-shot snapshot generation.

## 6. Future Workers – Media Unit Grouping and Thumbnails

### 6.1 Worker A – Media Unit Grouping (Design & Prototype)

- Responsibility:
  - For each bottom-level folder:
    - Group files into media units based on shared core name / structure.
- Inputs:
  - `ingest_log` rows (original_path, original_filename, extension).
- Behavior (PRE-PROJECT / dry-run):
  - Treat each bottom-level folder as a high-cohesion cluster.
  - For each folder:
    - Analyze all filenames together.
    - Identify which files belong to the same media unit.
    - Classify files as PRIMARY (video) vs ASSET (jpg/nfo/srt/…).
  - No writes to `library_items`.
  - No changes to `processed_flag`.
- Output (dry-run):
  - Print or log:
    - `MEDIA_UNIT folder=... core=... files=[...]`
    - Decorations observed per unit and per folder (opaque tokens for now).

### 6.2 Worker B – JPG Presence, Naming, and Folder Thumbnails (Design Only)

- Responsibility:
  - Ensure each media unit has a jpg and that Kodi-facing conventions are met.
- Behavior (target, not implemented in PRE-PROJECT):
  - For each media unit:
    - Check if at least one jpg exists:
      - If missing: for now, do nothing (just report).
      - If present:
        - Ensure there is a jpg whose filename matches the video filename.
        - If not, rename/copy as needed without losing the original name (e.g. log or track original).
  - For each folder:
    - If `folder.jpg` is absent:
      - Choose the oldest jpg in the folder and copy it as `folder.jpg`.
    - If a `ffff*.jpg` exists:
      - Treat it as user-selected folder thumbnail:
        - Copy it as `folder.jpg`.
        - Strip the `ffff` prefix from the original so it again matches the media unit filename.
- Constraints:
  - No background loops.
  - No writes to `library_items` in PRE-PROJECT.
  - Actual ffmpeg integration is a later step.
