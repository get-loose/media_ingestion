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
