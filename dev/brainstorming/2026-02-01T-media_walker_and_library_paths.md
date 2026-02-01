# Brainstorm – Media Walker, Library Paths, and Truth Model

Date: 2026-02-01

This document consolidates discussions about:

- The `walk_media` concept (user-triggered scans on Unraid).
- The experimental `mediawalker_test` script.
- The relationship between `library_items` and library path configuration.
- Future flags like `not_covered` and `not_in_filesystem`.
- Host vs container responsibilities (Unraid, uv, docker exec).

Some ideas here may be incompatible with earlier brainstorms; where that is the case and no decision has been made yet, they are left explicitly open.

---

## 1. Scripts: walk_media vs mediawalker_test

- `mediaserver_scripts/walk_media`:
  - Bash script.
  - Part of the **final project**.
  - User-triggered on Unraid to walk media folders.
  - Separate from inotify-triggered ingestion.
  - Currently a **placeholder** with no real behavior.

- `dev/mediawalker_test/mediawalker_test`:
  - Bash script.
  - **Experimental**, development-only.
  - Walks files/folders and fires ingestion via `dev.path_ingest`.
  - Filters by extension: `.mp4`, `.jpg`, `.nfo` (current list).
  - Input priority:
    - CLI arguments (files or folders) if provided.
    - Otherwise, `dev/mediawalker_test/media_walker_input` (one path per line).
  - Purpose:
    - Populate `ingest_log` with realistic data.
    - Explore how bulk ingestion behaves.
    - Does **not** implement any `library_items` or media-unit logic.

---

## 2. Truth Model: library_items vs library_paths

- `library_items`:
  - Represents the **truth** about media units.
  - Rows are durable; deleting rows is a **big event** and not part of normal operation.
  - A row may remain even if:
    - Its path is not covered by any configured library path.
    - Its file no longer exists on disk.

- `library_paths` (e.g. a `library_paths.txt` file, not yet defined):
  - Configuration describing where the user claims the library lives.
  - At best, a complete description of where `library_items.current_path` should be found.
  - It can be wrong, incomplete, or temporarily out of sync.
  - It is **not** the source of truth about media units.

- Future flags (design ideas, not yet in schema):
  - `not_covered`:
    - Indicates that `current_path` is not under any configured library root.
    - This is a state, not necessarily an error.
  - `not_in_filesystem`:
    - Indicates that the file no longer exists on disk.
    - This would require scanning the filesystem, potentially beyond configured library paths.
    - This is currently an open design question.

- Open questions:
  - How to reconcile `library_items` and `library_paths` over time:
    - When to mark `not_covered`.
    - Whether to ever clear `not_covered` automatically when paths change.
    - How to surface these states to the user (logs only vs UI later).

---

## 3. Fingerprinting and Media Units

- Fingerprinting is expected to be a **key mechanism** for identifying media units:
  - A media unit can be recognized by its fingerprint even if:
    - It is currently `not_covered` by `library_paths`.
    - It later reappears under a new path that is covered.
  - Fingerprints help avoid duplicate `library_items` rows when files move or library roots change.

- Current status:
  - `library_items.fingerprint` exists in the schema.
  - No fingerprinting logic is implemented yet.
  - The exact fingerprinting strategy (full-file hash vs partial, etc.) is still open.

---

## 4. Host vs Container: uv, docker exec, and media_walker

- Final architecture:
  - Python app (with `uv`, dependencies, and SQLite) runs **inside a container**.
  - Unraid host scripts (including `walk_media` and inotify-based scripts) run **outside** the container.

- Implications:
  - Host scripts should **not** depend on `uv` or Python being installed on the host.
  - Instead, they should use `docker exec` (or equivalent) to run commands inside the container.

- Example future shape (not implemented yet):

  ```bash
  docker exec -d app_container python -m app.ingest /container/path/to/file
  ```

  or, if `uv` is used inside the container:

  ```bash
  docker exec -d app_container uv run python -m app.ingest /container/path/to/file
  ```

- Current pre-project behavior:
  - `dev/mediawalker_test/mediawalker_test` runs locally and calls:

    ```bash
    uv run python -m dev.path_ingest <relative-path>
    ```

  - This is acceptable for local development on Teddy and will later be adapted to the container model.

- Open questions:
  - Exact container name and invocation pattern on Unraid.
  - How host paths map to container-visible paths (volume mounts, path translation).

---

## 5. Potential Incompatibilities and Open Decisions

- Earlier brainstorms suggested that `library_paths` might be “the truth” about where the library lives.
  - Current direction: `library_items` is the truth; `library_paths` is configuration.
  - This is a clarified design choice and may require revisiting older notes.

- Deletion of `library_items` rows:
  - Some earlier thinking may have implied more aggressive cleanup.
  - Current stance: deletion is rare and a big event; normal operation keeps historical media units.

- Media-unit definition:
  - Still not fully defined.
  - Needs to reconcile:
    - Video/audio files.
    - `.nfo` and `.jpg` as assets.
    - Fingerprinting and deduplication.
  - This remains an open design area for future work.
