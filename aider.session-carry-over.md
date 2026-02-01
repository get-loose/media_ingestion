# Aider Session Carry-Over – Next Topic: Simple Worker Decision Table

Next session starts from the assumption that the **ingestion spine is stable** (`dev/path_ingest.py` → `app/ingest.py` → `app/db.py` → `ingest_log`) and that `library_items` exists only as an empty schema.

The goal is to design, at the **docs level only**, how a future worker would reason over `ingest_log` rows and (conceptually) `library_items` to classify files and decide what *would* happen, without implementing any worker loop or writing to `library_items`.

---

## 1. Next-Session Goal

Design a **simple, first-pass decision table** that, for each relevant `ingest_log` row:

- Uses only:
  - `original_path` (directory + filename),
  - File extension (lowercased),
- And decides:

1. Is this a **primary media candidate** or an **asset**?
   - Primary: video files (`.mp4`, `.mkv`) that define a media unit.
   - Asset: subtitles / NFO / images (`.srt`, `.nfo`, `.jpg`) that attach to a media unit.

2. For a **primary**:
   - Should it create a **new media unit** (`library_items` row)?
   - Or should it be treated as an **update/alternate** for an existing media unit in the same folder?

3. For an **asset**:
   - Can it be **unambiguously attached** to a single primary in the same folder?
   - Or is it **ambiguous** (multiple possible primaries)?
   - Or is it an **orphan** (no matching primary yet)?

All of this remains **design only** in the next session:
- No background worker.
- No code that mutates `library_items`.
- No code that flips `processed_flag`.

---

## 2. Draft Decision Table (To Refine Next Session)

We start from this first-pass table and refine it:

### 2.1 Classification by Extension

- If `ext(path) in {mp4, mkv}` → **PRIMARY**
- If `ext(path) in {srt, nfo, jpg}` → **ASSET**
- Otherwise → **IGNORE/FUTURE**

Where:
- `ext(path)` is the lowercase extension without dot.

### 2.2 Primary Handling (mp4/mkv)

Using only:
- `dir(path)` – directory component of `original_path`,
- `stem(path)` – filename without extension,
- “same folder + same stem” as a grouping heuristic.

For a PRIMARY ingest row:

- **No existing media unit** in the same folder with the same stem  
  → Treat as **new media unit** (would create a new `library_items` row).

- **Existing media unit** in the same folder with the same stem, **same extension**  
  → Treat as **update/replace** of the primary file for that media unit.

- **Existing media unit** in the same folder with the same stem, **different extension**  
  → Treat as an **alternate primary** for the same media unit (e.g. `movie.mkv` + `movie.mp4`).

- Existing media unit with same stem but in a **different folder**  
  → Treat as a **new media unit** (no cross-folder linking in this first pass).

- **Multiple media units** in the same folder with the same stem  
  → Mark as **ambiguous**; do not guess.

### 2.3 Asset Handling (srt/nfo/jpg)

For an ASSET ingest row:

- **Exactly one** primary media unit in the same folder with the same stem  
  → **Attach asset** to that media unit.

- **Multiple** primaries in the same folder with the same stem  
  → **Ambiguous**; do not auto-attach.

- **No** primary in the same folder with the same stem  
  → Treat as **unattached/orphan asset** for now.

- Filenames like `movie.en.srt`  
  → Use the base stem before the first dot (`movie`) when matching; then apply the same rules.

### 2.4 Interaction with `processed_flag` (Future Behavior)

Conceptual future behavior (not to be implemented next session):

- Worker would only consider `ingest_log` rows where `processed_flag = 0`.
- If the decision is **definite**:
  - It would update `library_items` accordingly.
  - It would set `processed_flag = 1` for that row.
- If the decision is **ambiguous**:
  - It would leave `processed_flag = 0` (or use a future status field).
  - It would emit a log describing the ambiguity and the evidence.

Next session we only refine this logic; we do **not** implement it.

---

## 3. Optional Dev Helper (Design Only)

We may also sketch (but not necessarily implement) a **dry-run helper**:

- Name idea: `dev/worker_dry_run.py`.

Concept:

- Reads a subset of `ingest_log` rows (e.g. latest N or `processed_flag = 0`).
- Applies the decision table above in pure Python.
- Prints lines such as:

  - `DECISION primary:new_unit path=... reason=no_existing_same_stem`
  - `DECISION primary:update path=... target=... reason=existing_same_stem_same_ext`
  - `DECISION asset:attach path=... target=... reason=single_match_same_stem`
  - `DECISION asset:ambiguous path=... reason=multiple_primary_same_stem`
  - `DECISION asset:orphan path=... reason=no_primary_same_stem`

Constraints:

- Must **not** modify `library_items`.
- Must **not** change `processed_flag`.
- Must **not** run as a background loop.

---

## 4. Files to Re-Add Next Session

For the next session, please add these files to the chat:

```text
/read app/db.py app/ingest.py dev/path_ingest.py dev/inspect_ingest_log.py dev/inspect_library_items.py dev/mediawalker_test/mediawalker_test.sh dev/mediawalker_test/media_walker_input dev/brainstorming/2026-01-31T20-00-brainstorm.md dev/brainstorming/2026-01-31T20-00-preliminary_conclusions.md dev/brainstorming/2026-02-01T-media_walker_and_library_paths.md PRE_PROJECT_PROGRESS.md
```

(Other always-read docs like `PROJECT_BIBLE.md`, `PRE_PROJECT.md`, `SQLite_schema_design.md`, `integration/CONTRACT.md`, and `Database_design_guidance.md` do not need to be listed here.)
