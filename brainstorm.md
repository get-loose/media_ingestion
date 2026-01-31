# Brainstorm Notes – Library Items Next Phase

Date: 2026-01-31  
Context: Early design thoughts about how `library_items` will be used in the next phase.

---

## 1. Initial Thoughts (User)

- For a new ingested file, **without any action on the file**, an entry in `library_items` should be created so the ingested file is represented.
- `title` should initially be the **filename**.
- `current_path` should initially be the **original path**.
- `status` should be `pending`:
  - Every newly generated library item still needs at least a first pass after creation.
  - That first pass will determine what follows (e.g. cleanup of the filename if difficult characters are present).
- There should be a distinction between:
  - The **first action**: creation of an entry in `library_items` (only for real unique files, not duplicates).
  - At least a **second action** that follows for every new row (triggered by `pending` or maybe `new` to clarify a “virgin” row).
- Only certain file types should become `library_items`:
  - Filter to allow: audio, video, subtitles, NFO, (and possibly others to be decided).
- We need to distinguish between:
  - `title` (how it will be called in the `.nfo` for Kodi, since the goal is to have these files show up correctly in Kodi file view),
  - and `filename`.
- There is no need to also have `original_filename` present in `library_items` because that’s what the `ingest_log` table is for.

Open questions / implications raised:
- Should `status` use `pending` or `new` to indicate a just-created, unprocessed row?
- How to handle duplicates and “real unique files”?
- Which file types are relevant beyond audio/video/subtitles/NFO?
- How to separate display `title` from on-disk `filename` and from `original_filename` in `ingest_log`?

---

## 2. Initial Reaction (Assistant – Structured Brainstorm)

### 2.1. When and How to Create `library_items` Rows

- `ingest_log` remains the **event history**: “we saw PATH at TIME”.
- `library_items` is the **current state**: “this is a media item we care about”.
- For a new file that passes basic filters:
  - A future worker (next phase) should create a `library_items` row as soon as possible after ingest.
  - That row is a **placeholder representation** of the item, even before heavy processing.

Implication:
- The worker’s first responsibility for a new ingest:
  - Decide if this ingest represents a **new** library item or an **update/duplicate**.
  - If new → create `library_items` row.
  - If duplicate/update → adjust existing row or just mark ingest as processed.

### 2.2. Status Values (`pending` vs `new`) and Phases

- Use `status` as a **coarse lifecycle** indicator, not a detailed workflow engine.
- Reasonable initial states:
  - `pending`: row exists, initial processing not done yet (your “virgin row”).
  - `ready`: initial processing done (basic metadata, filename cleanup, etc.).
  - `error`: worker tried and failed (unreadable file, unsupported format, etc.).
- `pending` is sufficient to mean “created but not processed yet”; `new` may not be necessary as a separate state.

Implication:
- Worker logic:
  - Find `library_items` where `status = 'pending'`.
  - Perform first-pass processing.
  - Set `status = 'ready'` or `status = 'error'`.

### 2.3. Fields in `library_items`: Title vs Filename vs Paths

- `ingest_log`:
  - `original_path`, `original_filename` → immutable history.
- `library_items`:
  - `current_path`: where the file currently lives in the library (may change later).
  - `filename` (future field): current filename, derived from `current_path`.
  - `title`: display title for Kodi / NFO, which may diverge from filename.

For a brand-new item:
- `current_path` = `original_path`.
- `filename` = `Path(original_path).name`.
- `title` initially = `filename` (or filename without extension), until better metadata is available.

Later:
- `title` might become something like `Inception (2010)` even if the filename is still messy.
- If files are renamed/moved, `current_path` and `filename` change, but `ingest_log.original_*` stays as the historical record.

Implication:
- No need for `original_filename` in `library_items`; that belongs in `ingest_log`.
- Clear separation between:
  - `title` (for NFO / UI),
  - `filename` (on-disk name),
  - `current_path` (full path).

### 2.4. File-Type Filtering and “Real Unique Files”

Two concerns:

1. **File type filtering** – which files become `library_items` at all.
2. **Uniqueness / duplicates** – same content seen multiple times.

Initial whitelist ideas:
- Video: `.mkv`, `.mp4`, `.avi`, `.mov`, `.m4v`
- Audio: `.flac`, `.mp3`, `.aac`, `.ogg`, `.m4a`
- Subtitles: `.srt`, `.ass`, `.ssa`, `.sub`, `.idx`
- NFO: `.nfo`
- Possibly images: `.jpg`, `.jpeg`, `.png`, `.webp` (for posters/fanart)

For the next phase sketch:
- Worker creates `library_items` rows primarily for **video and audio** files.
- Subtitles/NFO/images:
  - Either ignored initially, or
  - Attached as metadata to an existing item (not separate `library_items` rows).

### 2.5. Uniqueness and `fingerprint`

- `fingerprint` in `library_items` is the key to “real unique files”.
- Worker computes a fingerprint (hash of file content or part of it).
- When processing a new ingest:
  - If a `library_items` row with the same `fingerprint` exists:
    - Treat as duplicate or move:
      - Possibly update `current_path` and `ingest_id`.
      - Do **not** create a new `library_items` row.
  - If no matching fingerprint:
    - Create a new `library_items` row.

Implication:
- Deduplication is a **worker concern**, not an ingest concern.
- `ingest_log` still records every event; `library_items` collapses duplicates into a single “item”.

### 2.6. Relationship to `ingest_log` and Phases

- `ingest_log`:
  - Immutable history of what was seen, when, and where.
- `library_items`:
  - Current view of the library.
  - `ingest_id` points to the **last** ingest that updated this item.

Likely next-phase worker flow:
1. Find `ingest_log` rows with `processed_flag = 0`.
2. For each:
   - If file type not in whitelist → mark processed, no `library_items` change.
   - If file type in whitelist:
     - Compute fingerprint.
     - If matching `library_items` exists → update it.
     - Else → create new `library_items` row with:
       - `ingest_id` = this ingest’s id.
       - `current_path` = `original_path`.
       - `title` = initial guess (filename).
       - `status` = `'pending'`.
3. Mark `ingest_log.processed_flag = 1`.

---

These notes are **design sketches only** for the next phase.  
No worker or `library_items` logic should be implemented during the pre-project phase.
