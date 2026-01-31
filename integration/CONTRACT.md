# Ingestion Boundary Contract (Pre-Project Phase)

This document describes the contract between:

- the **producer** (host-side stub, e.g. `dev/path_ingest.py`), and  
- the **consumer** (`app.ingest`).

It is intentionally narrow and focused on the current pre-project scope.

---

## 1. Invocation Contract

### 1.1. Command Shape

The consumer is invoked as a Python module:

```bash
uv run python -m app.ingest PATH
```

During development, the producer stub is invoked as:

```bash
uv run python -m dev.path_ingest PATH
```

Where:

- `PATH` is a **single argument** representing the container-visible filesystem path to the file that triggered ingestion.
- `PATH` is passed through unchanged from producer to consumer (no normalization beyond what `Path(PATH)` does inside the consumer).

### 1.2. Arguments

- Exactly **one positional argument** is expected by `app.ingest`:
  - `PATH` (string, non-empty)

Invalid usage (missing or extra arguments) is treated as a **usage error** by the consumer and results in:

- Exit code: `1`
- Log line with `EVENT=USAGE_ERROR`.

The producer stub (`dev/path_ingest.py`) currently enforces:

- At least one argument.
- Non-empty string for `PATH`.

---

## 2. Producer Responsibilities (`dev/path_ingest.py`)

The producer:

1. Accepts a single path argument from the CLI.
2. Logs a **dispatch event**.
3. Delegates to `app.ingest.main([PATH])`.
4. Propagates the consumer’s exit code.

### 2.1. Producer Logging

Producer logs are written to:

- `stdout`
- `dev/host.log` (best-effort; failures are ignored)

Log format (single line):

```text
<timestamp> host LEVEL=INFO EVENT=DISPATCH path=<PATH>
```

Where:

- `<timestamp>` is UTC in ISO 8601, seconds precision, with `Z` suffix, e.g. `2026-01-31T18:57:03Z`.
- `host` identifies the producer side.
- `LEVEL=INFO` is fixed for now.
- `EVENT=DISPATCH` indicates a dispatch attempt.
- `path=<PATH>` is the exact path argument passed to the consumer.

Producer logging **must not** affect dispatch semantics:

- Any error writing to `dev/host.log` is ignored.
- The producer still calls the consumer.

---

## 3. Consumer Responsibilities (`app.ingest`)

The consumer:

1. Parses CLI arguments.
2. Performs minimal validation on `PATH`.
3. Optionally inspects the filesystem (existence, file size).
4. Attempts to record ingestion intent in SQLite.
5. Emits structured logs.
6. Exits quickly with a deterministic status code.

### 3.1. Path Validation

Given `PATH`:

- If `PATH` is an empty string:
  - Exit code: `1`
  - Log: `EVENT=VALIDATION_ERROR reason=missing-path`

- If something exists at `PATH` and **is not** a regular file (e.g. directory, symlink to directory, etc.):
  - Exit code: `1`
  - Log: `EVENT=VALIDATION_ERROR reason=not-a-regular-file path=<PATH>`

- If `PATH` does **not** exist:
  - This is **not** an error.
  - `exists=false` is recorded in the final log.
  - Ingestion intent is still recorded (or attempted) in the DB.

### 3.2. Filesystem Inspection

If `PATH` exists and is a regular file:

- `exists=true` in the final log.
- `file_size` is obtained via `path.stat().st_size` when possible.
- If `stat()` fails, `file_size` is recorded as `NULL` in the DB.

If `PATH` does not exist:

- `exists=false` in the final log.
- `file_size` is recorded as `NULL` in the DB.

### 3.3. Database Interaction

The consumer uses `app.db.get_connection()` and `record_ingest_intent()`.

On a **successful** DB write:

- A new row is inserted into `ingest_log` with:
  - `original_path` = `str(PATH)`
  - `original_filename` = `Path(PATH).name`
  - `file_size` = size in bytes or `NULL`
  - `detected_at` = current UTC timestamp (ISO 8601 string)
  - `processed_flag` = `0`
  - `group_id` = `NULL`
  - `error_message` = `NULL`
- `ingest_id` is the new row’s primary key.
- `DB_STATUS=RECORDED` in the final log.
- `db_id=<ingest_id>` is included in the final log.

On a **DB failure** (e.g. file not writable, schema issue, etc.):

- No exception escapes `main()`.
- A log line is emitted:

  ```text
  ... ingest.py LEVEL=ERROR EVENT=DB_ERROR failed-to-record-ingest-intent path=<PATH> error=<ExceptionType>
  ```

- The final intent log is still emitted (see below) with:
  - `DB_STATUS=UNAVAILABLE`
  - No `db_id` field.

The consumer **never** retries DB operations.

### 3.4. Consumer Logging

All consumer logs:

- Are written to `stdout`.
- Are also appended (best-effort) to `logs/ingest.log`.
  - Logging failures are ignored and do not affect exit codes.

#### 3.4.1. Log Format

General format:

```text
<timestamp> ingest.py LEVEL=<LEVEL> <MESSAGE> [path=<PATH>] [extra fields...]
```

Where:

- `<timestamp>` is UTC ISO 8601, seconds precision, `Z` suffix.
- `ingest.py` identifies the consumer.
- `<LEVEL>` is `INFO` or `ERROR`.
- `<MESSAGE>` is a short token string, e.g. `EVENT=INGEST_INTENT_RECORDED`.

#### 3.4.2. Final Intent Log

On any **non-usage** path (including DB failures), the consumer emits a final log line:

```text
<timestamp> ingest.py LEVEL=INFO EVENT=INGEST_INTENT_RECORDED path=<PATH> exists=<true|false> DB_STATUS=<RECORDED|UNAVAILABLE> [db_id=<id>]
```

- `exists` reflects whether a regular file existed at `PATH` at ingest time.
- `DB_STATUS`:
  - `RECORDED` if the DB insert succeeded.
  - `UNAVAILABLE` if the DB operation failed.
- `db_id` is present only when the DB insert succeeded.

On **usage errors** (argument parsing failures), the consumer logs:

```text
<timestamp> ingest.py LEVEL=ERROR EVENT=USAGE_ERROR missing-or-invalid-arguments
```

and does **not** emit `EVENT=INGEST_INTENT_RECORDED`.

On **validation errors** (e.g. not a regular file), the consumer logs:

```text
<timestamp> ingest.py LEVEL=ERROR EVENT=VALIDATION_ERROR reason=<reason> path=<PATH>
```

and does **not** emit `EVENT=INGEST_INTENT_RECORDED`.

### 3.5. Exit Codes

The consumer returns:

- `0` when:
  - Arguments are valid, and
  - Path validation passes (file or missing file), and
  - Ingestion intent is **attempted**, regardless of DB success.

- `1` when:
  - Argument parsing fails (usage error), or
  - Validation fails (e.g. path is a directory).

The producer currently propagates this exit code unchanged.

---

## 4. Database Schema (Current Snapshot)

The consumer expects a SQLite database at `state/ingest.db` (by default), with:

### 4.1. `ingest_log`

```sql
CREATE TABLE IF NOT EXISTS ingest_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    original_path TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    file_size INTEGER,
    detected_at TEXT NOT NULL,
    processed_flag INTEGER NOT NULL DEFAULT 0,
    group_id INTEGER,
    error_message TEXT
);
```

Each call to `app.ingest` that passes validation appends a new row to `ingest_log`.  
There is no deduplication at this boundary; repeated ingests of the same `PATH` produce multiple rows.

### 4.2. `library_items`

```sql
CREATE TABLE IF NOT EXISTS library_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ingest_id INTEGER NOT NULL,
    current_path TEXT NOT NULL,
    title TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    metadata TEXT,
    fingerprint TEXT,
    FOREIGN KEY (ingest_id) REFERENCES ingest_log(id)
);
```

In the pre-project phase, `library_items` is created but not populated or updated.  
All current behavior is limited to `ingest_log`.

Schema creation and PRAGMAs are handled by `app.db` on first connection.

---

## 5. Observability & Inspection

### 5.1. Logs

- Producer logs: `dev/host.log`
- Consumer logs: `logs/ingest.log`

Both are append-only and best-effort.

### 5.2. Database Inspection Helpers

Development helpers:

- `dev/inspect_ingest_log.py`
  - Shows recent rows from `ingest_log`.
- `dev/inspect_library_items.py`
  - Shows recent rows from `library_items`.

Run via:

```bash
uv run dev/inspect_ingest_log.py
uv run dev/inspect_library_items.py
```

(These are simple scripts, not modules; `uv run script.py` is acceptable here.)

---

## 6. Worked Example: Existing Regular File (“Happy Path”)

This example captures an end-to-end run where the target path exists and is a regular file, and the database write succeeds.

### 6.1. Command

```bash
uv run python -m dev.path_ingest data/inbox/example.mkv
echo "exit code: $?"
uv run dev/inspect_ingest_log.py
```

### 6.2. Producer Log

From `dev/path_ingest.py`:

```text
2026-01-31T19:05:26Z host LEVEL=INFO EVENT=DISPATCH path=data/inbox/example.mkv
```

Interpretation:

- At `19:05:26Z`, the producer stub dispatched an ingest for `data/inbox/example.mkv`.
- This line is written to:
  - `stdout`
  - `dev/host.log`

### 6.3. Consumer Log

From `app/ingest.py`:

```text
2026-01-31T19:05:26Z ingest.py LEVEL=INFO EVENT=INGEST_INTENT_RECORDED path=data/inbox/example.mkv exists=true DB_STATUS=RECORDED db_id=2
exit code: 0
```

Interpretation:

- `EVENT=INGEST_INTENT_RECORDED`: ingest attempt was accepted and processed.
- `path=data/inbox/example.mkv`: same path as producer.
- `exists=true`: at ingest time, `Path(...).exists()` was true and it was a regular file.
- `DB_STATUS=RECORDED`: DB insert succeeded.
- `db_id=2`: `record_ingest_intent` returned primary key `2`.
- `exit code: 0`:
  - `app.ingest.main` returned 0.
  - `dev.path_ingest` propagated this 0.

This matches the contract for a valid file with a successful DB write.

### 6.4. Database Rows

From `dev/inspect_ingest_log.py`:

```text
=== ingest_log (last 3 rows) ===
id | original_path | original_filename | file_size | detected_at | processed_flag | group_id | error_message
--------------------------------------------------------------------------------
2 | data/inbox/example.mkv | example.mkv | 0 | 2026-01-31T19:05:26.136040+00:00 | 0 | NULL | NULL
1 | data/inbox/example.mkv | example.mkv | 0 | 2026-01-31T17:00:17.476911+00:00 | 0 | NULL | NULL
```

Notes:

- Row `id = 2`:
  - `original_path` and `original_filename` match the path.
  - `file_size = 0` (file was 0 bytes on disk at ingest time).
  - `detected_at` matches the time of this latest run.
  - `processed_flag = 0`, `group_id = NULL`, `error_message = NULL` as expected.
- Row `id = 1`:
  - An earlier ingest of the same file.

Crucially:

- The `db_id=2` in the consumer log matches the new row with `id=2` in `ingest_log`.
- This confirms that:
  - `record_ingest_intent` ran.
  - `conn.commit()` in `ingest.py` persisted the row.
  - The ingestion spine is consistent: what the logs claim is in the DB is actually in the DB.

---

## 7. Worked Example: Missing File

This example captures an end-to-end run where the target path does **not** exist at ingest time, and the database write succeeds.

### 7.1. Command

```bash
uv run python -m dev.path_ingest data/inbox/does_not_exist.mkv
echo "exit code: $?"
uv run dev/inspect_ingest_log.py
```

### 7.2. Producer Log

```text
2026-01-31T19:07:42Z host LEVEL=INFO EVENT=DISPATCH path=data/inbox/does_not_exist.mkv
```

### 7.3. Consumer Log

```text
2026-01-31T19:07:42Z ingest.py LEVEL=INFO EVENT=INGEST_INTENT_RECORDED path=data/inbox/does_not_exist.mkv exists=false DB_STATUS=RECORDED db_id=4
exit code: 0
```

Interpretation:

- `exists=false`: the file did not exist at ingest time.
- `DB_STATUS=RECORDED`: DB insert succeeded.
- `db_id=4`: primary key of the new `ingest_log` row.
- Exit code `0`: missing files are tolerated; the ingest attempt is still considered accepted.

### 7.4. Database Rows

```text
=== ingest_log (last 5 rows) ===
id | original_path                  | original_filename   | file_size | detected_at                          | processed_flag | group_id | error_message
--------------------------------------------------------------------------------
4 | data/inbox/does_not_exist.mkv | does_not_exist.mkv | NULL | 2026-01-31T19:07:42.381844+00:00 | 0 | NULL | NULL
3 | data/inbox/does_not_exist.mkv | does_not_exist.mkv | NULL | 2026-01-31T19:07:03.973557+00:00 | 0 | NULL | NULL
2 | data/inbox/example.mkv        | example.mkv        | 0    | 2026-01-31T19:05:26.136040+00:00 | 0 | NULL | NULL
1 | data/inbox/example.mkv        | example.mkv        | 0    | 2026-01-31T17:00:17.476911+00:00 | 0 | NULL | NULL
```

Notes:

- Rows `id = 3` and `id = 4` correspond to two separate ingest attempts for the same missing path.
- `file_size = NULL` for both, because the file did not exist.
- This demonstrates the append-only, duplicate-tolerant nature of `ingest_log`.

---

## 8. Worked Example: Directory Path (Validation Error)

This example captures an end-to-end run where the target path is a directory, which is considered invalid input for the ingest boundary.

### 8.1. Command

```bash
uv run python -m dev.path_ingest data/inbox
echo "exit code: $?"
uv run dev/inspect_ingest_log.py
```

### 8.2. Producer Log

```text
2026-01-31T19:08:56Z host LEVEL=INFO EVENT=DISPATCH path=data/inbox
```

### 8.3. Consumer Log

```text
2026-01-31T19:08:56Z ingest.py LEVEL=ERROR EVENT=VALIDATION_ERROR reason=not-a-regular-file path=data/inbox
exit code: 1
```

Interpretation:

- `EVENT=VALIDATION_ERROR reason=not-a-regular-file`: something exists at `PATH`, but it is not a regular file (e.g. a directory).
- Exit code `1`: this is treated as a validation/usage error.
- No `EVENT=INGEST_INTENT_RECORDED` line is emitted.

### 8.4. Database Rows

```text
=== ingest_log (last 5 rows) ===
id | original_path                  | original_filename   | file_size | detected_at                          | processed_flag | group_id | error_message
--------------------------------------------------------------------------------
4 | data/inbox/does_not_exist.mkv | does_not_exist.mkv | NULL | 2026-01-31T19:07:42.381844+00:00 | 0 | NULL | NULL
3 | data/inbox/does_not_exist.mkv | does_not_exist.mkv | NULL | 2026-01-31T19:07:03.973557+00:00 | 0 | NULL | NULL
2 | data/inbox/example.mkv        | example.mkv        | 0    | 2026-01-31T19:05:26.136040+00:00 | 0 | NULL | NULL
1 | data/inbox/example.mkv        | example.mkv        | 0    | 2026-01-31T17:00:17.476911+00:00 | 0 | NULL | NULL
```

Notes:

- There is **no** row with `original_path = data/inbox`.
- Validation errors do not create `ingest_log` entries.

---

## 9. Non-Goals (Pre-Project Phase)

Out of scope for this contract:

- Background workers or asynchronous processing.
- Media grouping, renaming, or moving files.
- Retries or scheduling.
- UI/TUI.
- Any runtime AI/LLM integration.
- Reading logs to make runtime decisions.

This contract focuses solely on the **fire-and-forget ingestion boundary** and its immediate persistence and logging behavior.
