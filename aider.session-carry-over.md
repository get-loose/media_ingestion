# Session Carry-Over

Next focus: Worker A – token-based media unit grouping.

- Move away from fuzzy-first clustering for media units.
- Design a folder-local, token-based core derivation:
  - Tokenize stems on separators.
  - Derive per-media-unit cores from shared token prefixes.
  - Attach assets based on token-prefix similarity.
- Use this to:
  - Group files into media units per folder.
  - Surface decorations per unit and per folder (for later interpretation).
- Keep Worker A read-only in PRE-PROJECT (no DB writes, no processed_flag changes).

## Files to Revisit Next Session

For designing and (later) prototyping Worker A’s token-based grouping, we will likely need:

- `app/db.py`
  - To understand how `ingest_log` is accessed and what fields are available.
- `app/ingest.py`
  - To confirm how `original_path` / `original_filename` are recorded.
- `dev/inspect_ingest_log.py`
  - To see how ingest_log is currently inspected and what sample data looks like.
- `dev/inspect_library_items.py`
  - To align future Worker A outputs with the intended `library_items` shape.
- `what-the-downloads-look-like.md`
  - Ground truth for how filenames are structured by the downloader.
- `aider.session-todo.md`
  - To keep Worker A’s token-based design aligned with the current TODO.

Suggested /read command for next session:

`/read app/db.py app/ingest.py dev/inspect_ingest_log.py dev/inspect_library_items.py what-the-downloads-look-like.md aider.session-todo.md`
