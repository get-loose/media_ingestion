# Session TODO / Next Steps

## 1. Ingestion Spine & DB

- [ ] Review `app/db.py` for:
  - [ ] Connection lifecycle and `get_connection` usage
  - [ ] Schema initialization logic and idempotency
  - [ ] `record_ingest_intent` parameters and behavior
- [ ] Confirm `DEFAULT_DB_PATH` and `DatabaseConfig` align with:
  - [ ] Local dev usage
  - [ ] Future `/config/state/ingest.db` container path

## 2. Ingest Entry Point

- [ ] Review `app/ingest.py`:
  - [ ] CLI contract (arguments, exit codes)
  - [ ] Logging format and fields (`_log`)
  - [ ] Fast-exit behavior and minimal work in `main`

## 3. Dev & Inspection Tools

- [ ] Align dev inspection scripts with `db.py`:
  - [ ] `dev/inspect_ingest_log.py` should not hardcode DB path differently from `db.py`
  - [ ] `dev/inspect_library_items.py` same as above
- [ ] Confirm `dev/path_ingest.py` and `dev/fire_and_forget.sh`:
  - [ ] Match the integration contract in `integration/CONTRACT.md`
  - [ ] Use fire-and-forget semantics (no waiting, no retries)

## 4. Media Walker (Future Prep, No Implementation Yet)

- [ ] Re-read `dev/brainstorming/2026-02-01T-media_walker_and_library_paths.md`
- [ ] Clarify:
  - [ ] How media walker will discover files
  - [ ] How it will call `ingest.py` (paths, assumptions)
- [ ] Ensure no media walker logic is implemented yet (PRE-PROJECT constraint).

## 5. Documentation & Specs

- [ ] Cross-check:
  - [ ] `PROJECT_SPEC.md`
  - [ ] `PRE_PROJECT.md`
  - [ ] `Database_design_guidance.md`
  - [ ] `SQLite_schema_design.md`
- [ ] Confirm current code matches:
  - [ ] Fire-and-forget model
  - [ ] “No workers / no renames / no moves” rule
  - [ ] “No AI at runtime” rule

---

## Likely Files to Read Next Session

- `app/db.py`
- `app/ingest.py`
- `dev/path_ingest.py`
- `dev/fire_and_forget.sh`
- `dev/inspect_ingest_log.py`
- `dev/inspect_library_items.py`
- `integration/CONTRACT.md`
- `PROJECT_SPEC.md`
- `PRE_PROJECT.md`
- `SQLite_schema_design.md`
- `Database_design_guidance.md`

For quick loading in aider:

`/read app/db.py app/ingest.py dev/path_ingest.py dev/fire_and_forget.sh dev/inspect_ingest_log.py dev/inspect_library_items.py integration/CONTRACT.md PROJECT_SPEC.md PRE_PROJECT.md SQLite_schema_design.md Database_design_guidance.md`
