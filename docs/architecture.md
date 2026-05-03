# Architecture — TrashPandaOmega

> _Last updated: 2026-05-03_

---

## High-Level Overview

TrashPandaOmega is a Python-based platform for automated data acquisition and processing. It consists of three primary components — a **scraping engine**, a **job scheduler**, and a **pipeline orchestrator** — that work together to fetch, transform, and route data with minimal human intervention.

The system is designed to be async-first, lightweight, and configuration-driven. It runs as a standalone Python process and does not share infrastructure with any other project.

---

## Core Components

### 1. Scraping Engine

Responsible for fetching raw data from external sources (web pages, APIs, feeds).

- Uses `httpx` / `aiohttp` for async HTTP requests
- Pluggable parsers (e.g., `beautifulsoup4` for HTML, `json` for APIs)
- Respects rate limits and supports retry/backoff
- Returns normalised data structures to the pipeline

### 2. Job Scheduler

Manages when and how often tasks run.

- Declarative job definitions (cron-style or interval-based)
- Supports retry logic with configurable backoff strategies
- Emits job lifecycle events (started, completed, failed)
- Integrates with `APScheduler` (planned)

### 3. Pipeline Orchestrator

Coordinates the flow of data through processing stages.

- Composable pipeline stages (fetch → parse → transform → store)
- Each stage is a pure function or async coroutine
- Stages can be chained, branched, or parallelised
- Error isolation: a failing stage does not crash the entire pipeline

---

## Data Flow

```
[External Source]
      │
      ▼
[Scraping Engine]  ──── fetches raw content
      │
      ▼
[Parser / Normaliser]  ── structured data objects
      │
      ▼
[Pipeline Orchestrator]  ── routes through processing stages
      │
      ├──▶ [Transform Stage]
      │
      ├──▶ [Enrich Stage]
      │
      └──▶ [Storage / Output Stage]

[Job Scheduler] ─── triggers Scraping Engine on schedule
```

---

## Dependencies and Integration Points

| Dependency | Role | Status |
|---|---|---|
| `httpx` | Async HTTP client | Planned |
| `beautifulsoup4` | HTML parsing | Planned |
| `APScheduler` | Job scheduling | Planned |
| `pytest` + `pytest-asyncio` | Testing | Active |
| `asyncio` | Async runtime | Active (stdlib) |

External integration points (planned):

- HTTP/S endpoints (scraping targets)
- Local filesystem (output storage)
- Optional: message queue or database (future)

---

## Assumptions and Constraints

- **Single-process**: The initial version runs as a single Python process; distributed execution is out of scope for v0.x.
- **No shared state with other projects**: TrashPandaOmega is fully isolated from BrickCipher and VoxChimera.
- **Python 3.11+**: All code targets Python 3.11 or later. No legacy compatibility required.
- **Pull-based**: The scraper pulls from sources on a schedule; push/webhook ingestion is not in scope for v0.x.
- **Output is local**: For now, output is written to local files or stdout. Remote storage is a future concern.

---

## Security Considerations

- **No credentials in source**: All secrets (API keys, auth tokens) must be supplied via environment variables or a secrets manager — never committed to the repository.
- **Input sanitisation**: All data fetched from external sources is treated as untrusted. Parsers must handle malformed or malicious content safely.
- **Dependency hygiene**: Dependencies are pinned and audited. Avoid pulling in large dependency trees unnecessarily.
- **Rate limiting**: The scraping engine must respect `robots.txt` and per-site rate limits to avoid abuse.

---

## Future Expansion

- **Distributed execution**: Scale out scraping workers using a task queue (e.g., Celery, arq).
- **Pluggable storage backends**: Support for databases (SQLite, PostgreSQL) and object storage (S3).
- **Observability**: Structured logging, metrics, and distributed tracing.
- **CLI interface**: A `trashpanda` CLI for triggering jobs and inspecting pipeline state.
- **Docker support**: Containerised execution for reproducible deployments.

---

## Text-Based Component Diagram

```
┌─────────────────────────────────────────────────┐
│                 TrashPandaOmega                 │
│                                                 │
│  ┌─────────────┐      ┌──────────────────────┐  │
│  │ Job         │      │ Scraping Engine      │  │
│  │ Scheduler   │─────▶│ (httpx / aiohttp)    │  │
│  └─────────────┘      └──────────┬───────────┘  │
│                                  │              │
│                                  ▼              │
│                       ┌──────────────────────┐  │
│                       │ Pipeline Orchestrator│  │
│                       │                      │  │
│                       │  [fetch]             │  │
│                       │     ↓                │  │
│                       │  [parse]             │  │
│                       │     ↓                │  │
│                       │  [transform]         │  │
│                       │     ↓                │  │
│                       │  [output]            │  │
│                       └──────────────────────┘  │
└─────────────────────────────────────────────────┘
```
