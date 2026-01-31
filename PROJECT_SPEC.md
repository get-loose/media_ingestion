# AutoMediaIngest – Project Specification

## 1. Project Overview

**Name:** AutoMediaIngest

**Goal:**  
AutoMediaIngest is an automated, containerized media ingestion pipeline designed
to run on an Unraid server. It detects newly written media-related files
(video, audio, images, NFO, subtitles), records ingestion intent, and later
processes them into a clean, structured media library.

The project prioritizes:
- deterministic behavior
- explicit boundaries
- idempotency
- observability via logs
- minimal infrastructure complexity

There are **no AI or LLM dependencies at runtime**.

---

## 2. Target Runtime Environment

### Host (Unraid)

- OS: Unraid (Linux, Slackware-based, limited tooling)
- Responsibilities:
  - Watch filesystem events using `inotifywait`
  - Detect file-ready events (`close_write`, `moved_to`)
  - Dispatch ingestion using fire-and-forget semantics
  - Never wait for results
  - Never retry
  - Write simple structured logs

### Container (Application)

- OS: Linux
- Language: Python 3.11+
- Responsibilities:
  - Accept ingestion events
  - Persist ingestion intent
  - Perform processing asynchronously (future)
  - Maintain library state
  - Write structured logs

---

## 3. High-Level Architecture

```text
[ Unraid Host ]
    |
    |  (fire-and-forget)
    v
docker exec -d app_container python ingest.py <container_path>
    |
    v
[ ingest.py ] → [ SQLite DB ] → [ logs ] → exit
```

Key principle:
> The host never waits, retries, or inspects results.

---

## 4. Fire-and-Forget Semantics

### Producer (Host Script)

- Emits an event exactly once per detected filesystem action
- Passes a container-visible path
- Does not block
- Does not retry
- Does not inspect exit codes
- Logs what it attempted

### Consumer (`ingest.py`)

- Accepts a single file path
- Validates minimal input
- Records ingestion intent
- Logs outcome
- Exits quickly
- Tolerates:
  - duplicate calls
  - missing files
  - out-of-order events

---

## 5. Database Architecture (Authoritative)

AutoMediaIngest uses **SQLite as an application-owned database**.

### Design Choice

- SQLite runs **inside the same container as the application**
- Persistence is provided via a mounted `/config` directory
- There is **no separate database container**
- There is **no networked database dependency**

This choice is intentional to:
- reduce operational complexity
- simplify open-source distribution
- align with SQLite’s embedded design
- match Unraid’s volume-based persistence model

Future migration to a service database (e.g. PostgreSQL) is possible,
but explicitly out of scope for early versions.

---

## 6. Data Model (Conceptual)

### ingest_log (Immutable History)

Purpose:
- Immutable audit trail of all ingestion attempts
- Basis for re-hydration and replay

Characteristics:
- Append-only
- Never deleted
- Rarely updated (status only)

Conceptual fields:
- id
- original_path
- original_filename
- file_size (optional)
- detected_at
- processed_flag
- group_id (future)
- error_message (nullable)

---

### library_items (Current State)

Purpose:
- Canonical representation of the media library

Characteristics:
- Represents current state only
- Can be rebuilt from ingest_log

Conceptual fields:
- id
- ingest_id (FK)
- current_path
- title
- status
- metadata (JSON)
- fingerprint

---

## 7. Code Structure (Conceptual)

```text
app/
├── ingest.py    # Fast entry point
├── db.py        # Database access layer
└── worker.py    # Slow/background processing (future)
```

### Design Rules

- `ingest.py` must remain lightweight
- Business logic must not leak into `db.py`
- SQL must be centralized
- Paths must be container-relative
- No hardcoded Unraid paths in code

---

## 8. Logging

- Logs are structured and append-only
- Logs exist to explain behavior
- Logs are never read by the system to make decisions
- Logs are treated as evidence, not logic

---

## 9. Development Philosophy

- Develop locally first
- Validate logic before infrastructure
- Introduce complexity one layer at a time
- Prefer explicit contracts over implicit behavior
- Keep runtime deterministic and boring

---

## 10. Role of Aider

Aider is used **only during development** to reason over:

- this specification
- the pre-project document
- contracts
- stub scripts
- database design notes
- curated log samples

Aider must not assume:
- a running system
- Unraid availability
- Docker availability
- live logs

All reasoning must be based on provided artifacts.

