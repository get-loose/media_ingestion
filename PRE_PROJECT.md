# Pre-Project Summary: Fire-and-Forget Ingestion Spine (Local-First)

## Purpose of This Phase

This phase establishes the **ingestion spine** of the AutoMediaIngest system.

The goal is to design, implement, and validate the **boundary** between:
- a fire-and-forget event producer, and
- a container-style ingestion consumer

This is done **locally on the development machine ("Teddy")** before any
Unraid- or Docker-specific integration.

At this stage, we are explicitly validating:
- contracts
- idempotency assumptions
- logging
- database interactions
- fast-exit semantics

We are **not** building the full ingestion pipeline yet.

---

## Development Environment (Authoritative)

- All coding happens locally on Teddy
- Aider is used as a development assistant
- SQLite is used locally as the ingestion database
- The database is owned by the application (not a separate service)
- No Unraid tooling is required yet
- No Docker is required yet

The local setup mirrors the **final production shape**:
a single application owning its SQLite database via a mounted directory.

---

## Architectural Direction (Important)

The final system will run as:
- **one container**
- owning its **SQLite database**
- with a persistent mounted `/config` directory

There will NOT be:
- a separate database container
- a networked database dependency
- runtime AI or LLM interaction

The local pre-project phase uses the **same database model**
as the final Unraid deployment, differing only in filesystem paths.

---

## Scope of This Phase

### Implemented in this phase
- A local fire-and-forget *stub* (producer)
- An ingestion entry point (`ingest.py`)
- A local SQLite database
- Structured logging
- A written producer/consumer contract
- Curated log samples

### Explicitly out of scope
- Unraid integration
- inotifywait
- Docker
- media grouping
- renaming or moving files
- worker loops
- retries
- scheduling
- UI / TUI
- AI at runtime

---

## Fire-and-Forget Model

The ingestion boundary is defined as:

Producer → ingest.py → SQLite → logs → exit

The producer:
- emits events
- never waits
- never retries
- never inspects results

The consumer (`ingest.py`):
- accepts a single file path
- records ingestion intent
- logs outcome
- exits quickly
- tolerates duplicates and race conditions

---

## Stubs Used in This Phase

Two local stubs may be used:

### Option A — Manual Trigger
Used to validate basic correctness.
Direct invocation of `ingest.py`.

### Option B — Fire-and-Forget Stub Script
A small local script that:
- calls `ingest.py` in the background
- logs producer-side events
- exits immediately

This stub emulates the final Unraid inotify behavior
without introducing infrastructure complexity.

---

## Role of Aider

Aider is expected to reason over:
- this document
- the project specification
- the ingestion contract
- the stub scripts
- database schema notes
- curated log samples

Aider should **not** assume access to:
- a running system
- Unraid
- Docker
- live logs

All reasoning must be based on the provided artifacts only.

