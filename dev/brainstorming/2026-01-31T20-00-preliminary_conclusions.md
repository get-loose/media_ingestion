# Preliminary Conclusions – Library Items & Media Units

Date: 2026-01-31T20:00

This summarizes what we should **take away so far**, without committing to implementation yet.

---

## 1. Roles of the Two Tables

- `ingest_log`:
  - Immutable event history: every ingest attempt is recorded.
  - Used to rebuild or audit what happened over time.
- `library_items`:
  - Canonical, **current-state** view of media units.
  - One row per logical media item (movie/episode/clip), not per every file.
  - Will drive NFO and artwork generation for Kodi.

---

## 2. Media Units and Assets

- A **media unit** consists of:
  - A primary media file (video/audio).
  - Its `.nfo`.
  - Its poster/thumbnail `.jpg`.
  - Optional subtitles and extra images.
- `library_items` rows represent media units.
- Subtitles, images, and NFO files are **assets attached to a media unit**, not separate `library_items` rows.

---

## 3. Initial Shape of `library_items` Rows

For a new, relevant file (video/audio):

- Create a `library_items` row (in a future worker phase) with:
  - `ingest_id` → the `ingest_log.id` that introduced or last updated it.
  - `current_path` → initially the `original_path` from `ingest_log`.
  - `title` → initially derived from the filename.
  - `status` → `'pending'` (needs first-pass processing).
  - `metadata` → JSON for richer info (actors, tags, source website, etc.).
  - `fingerprint` → content-based identifier for deduplication.
- Additional fields we likely want:
  - `filename` (derived from `current_path`).
  - `extension` (for filtering and behavior).
  - `created_at` / `updated_at` (library-level lifecycle timestamps).

---

## 4. Status and Processing Phases

- Use `status` as a coarse lifecycle indicator:
  - `pending`: row exists, initial processing not done.
  - `ready`: initial processing done (basic metadata, filename cleanup, etc.).
  - `error`: processing failed.
- A future worker will:
  - Find `library_items` with `status = 'pending'`.
  - Perform first-pass processing.
  - Set `status` to `ready` or `error`.

---

## 5. File-Type Policy and Deduplication

- Only certain file types should become primary `library_items`:
  - Primarily video and audio (e.g. `.mkv`, `.mp4`, `.flac`, `.mp3`, …).
- Other files (subtitles, NFO, images) are:
  - Either ignored as primary items, or
  - Attached as assets to an existing media unit.
- Deduplication will be based on `fingerprint`:
  - Same fingerprint → same media unit (path may change).
  - Different fingerprint → potentially a new media unit.

---

## 6. Handling New Ingests for Existing Items

- New ingest events for an existing media unit are **signals**, not always noise:
  - If fingerprint and path are unchanged → likely noise; mark ingest as processed, no library change.
  - If fingerprint matches but path changed → update `current_path` (and filename/extension), possibly re-interpret path.
  - If fingerprint changed → treat more like a new version; may need a fuller pass.

---

## 7. Kodi / NFO Relationship

- `library_items` (plus metadata) is the **source of truth**.
- `.nfo` files and `.jpg` artwork are **Kodi-facing projections**:
  - Generated from `library_items`.
  - Can be regenerated if needed.
- Any information important for Kodi nodes or file view (e.g. “producer” as originating website) should live in `library_items` / `metadata` and be mapped into NFO fields.

---

## 8. Scope Reminder (Pre-Project)

- All of the above is **design for the next phase**.
- In the current pre-project phase:
  - We do **not** implement workers or `library_items` logic.
  - We only document how we expect `library_items` to be used later.
