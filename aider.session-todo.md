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

## 7. Worker A – Token-Based Media Unit Grouping (Better Than Fuzzy)

This section refines Worker A’s design, focusing on a **token-based, folder-local** approach
instead of fuzzy clustering. The goal is to align with downloader guarantees and avoid
over-grouping issues seen in the fuzzy experiment (e.g. `fox_` cores).

### 7.1. Core Idea

- Treat each **bottom-level folder** as a high-cohesion universe.
- Within a folder:
  - Filenames for a given media unit share a **core name**.
  - Extra pieces (resolution, site, time, actor, production house, uploader) are **decorations**.
- Worker A should:
  - Derive **cores** directly from filenames in the folder (token-based), not from fuzzy clusters.
  - Group files into media units by shared cores.
  - Surface decorations per unit and per folder.

### 7.2. Tokenization

For each filename (stem, without extension):

- Split into tokens on separators:
  - Characters: `_`, `-`, `.`, space, and possibly brackets `[]()`.
- Example:
  - `sdfw_moviename1_720p-20250101-0116` →
    - tokens: `["sdfw", "moviename1", "720p", "20250101", "0116"]`
  - `a_brown_fox_jumped_20250101` →
    - tokens: `["a", "brown", "fox", "jumped", "20250101"]`

Tokenization is **per folder** and uses only stdlib.

### 7.3. Per-Folder Core Derivation (No Fuzzy)

Within a folder:

1. **Group by video stems first**:
   - Consider only PRIMARY files (video extensions).
   - For each video stem, keep its token list.

2. **Find candidate cores per video**:
   - For each video stem:
     - Look at other stems in the same folder.
     - Compute a **longest common token prefix** with its nearest neighbors.
     - Require a minimum number of shared tokens (e.g. at least 2–3 tokens) to consider them part of the same media unit.
   - Example:
     - `["a", "brown", "fox", "jumped", "20250101"]`
     - `["a", "brown", "fox", "jumped", "20250102"]`
     - Core tokens: `["a", "brown", "fox", "jumped"]`.

3. **Avoid generic cores**:
   - If a candidate core is very short (e.g. 1 token like `"fox"`), treat it as **too generic**.
   - Prefer longer token prefixes that distinguish units:
     - `["a", "brown", "fox"]` vs `["a", "white", "fox"]` should become **two different cores**.

4. **Assign assets to cores**:
   - For each ASSET file (jpg/nfo/srt):
     - Tokenize its stem.
     - Find the video core whose token prefix best matches (e.g. longest common token prefix).
     - Attach the asset to that media unit if the match is strong enough.

### 7.4. Handling Decorations

Once cores are defined:

- For each media unit:
  - Decorations = tokens in member filenames **after** the core tokens.
  - Example:
    - Core tokens: `["moviename1"]`
    - File tokens: `["sdfw", "moviename1", "720p", "20250101", "0116"]`
    - Decorations: `["sdfw", "720p", "20250101", "0116"]`.

- For the folder:
  - Aggregate decoration tokens across all units.
  - Identify:
    - Tokens that recur across many units (likely site, production house, uploader).
    - Tokens that are per-unit (actor, specific tags).
  - Worker A does **not** interpret them yet; it just surfaces them.

### 7.5. Advantages Over Fuzzy

- **Deterministic and explainable**:
  - No similarity thresholds or opaque scores.
  - Grouping is based on explicit token prefixes and folder-local patterns.
- **Respects downloader guarantees**:
  - One core per media unit, shared across its files.
  - Decorations are added consistently by the downloader.
- **Avoids over-grouping**:
  - Cases like `a_brown_fox_jumped...` vs `a_white_fox_jumped...`:
    - Token-based cores distinguish them by `["a", "brown", "fox"]` vs `["a", "white", "fox"]`.
    - They do not collapse into a generic `["fox"]` core.

### 7.6. Worker A Focus in Next Sessions

- Design a **token-based core derivation algorithm** in more detail:
  - Exact tokenization rules.
  - Minimum core length (in tokens).
  - How to handle random prefixes (fixed-length noise at the start).
- Define Worker A’s **dry-run output**:
  - `MEDIA_UNIT folder=... core_tokens=[...] files=[...]`
  - `DECORATIONS unit=... tokens=[...]`
  - `FOLDER_DECORATIONS tokens=[...]`
- Keep Worker A:
  - Read-only (no DB writes in PRE-PROJECT).
  - Focused on structure discovery, not on thumbnails or NFO writing yet.
