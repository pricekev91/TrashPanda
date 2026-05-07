# Milestone 1 Backlog: Trustworthy Live Ingest

This document breaks Milestone 1 into concrete work items that can be executed, validated, and tracked to completion.

## Outcome

TrashPanda reliably ingests live jobs from supported sources, stores clean records in Postgres, and presents enough ingest health and job quality signal in the dashboard for daily use.

## Exit Criteria

- live ingest runs repeatedly without manual recovery for supported sources
- duplicate and stale jobs are handled predictably
- ingest failures are visible through the API and dashboard
- the queue is populated by trustworthy live data rather than demo-quality placeholders
- the ingest path has automated validation in CI

## Workstream 1: Source Reliability

### Tasks

- document the contract for each supported source: URL, expected payload shape, cadence, and known failure modes
- add per-source timeout, retry, and error classification behavior
- preserve the last successful ingest timestamp per source
- distinguish between fetch success with zero jobs and true source failure
- ensure the worker keeps processing remaining sources if one source fails

### Acceptance checks

- a source outage does not stop the full ingest cycle
- source failures produce visible structured error details
- the system records whether each source succeeded, failed, or returned zero items

## Workstream 2: Normalization and Deduplication

### Tasks

- define canonical rules for company, title, location, and source URL normalization
- review source-key construction to reduce false duplicates and false splits
- add tests for duplicate suppression across repeated cycles from the same source
- add tests for equivalent jobs with small title or URL differences
- define how cross-source duplicates should be handled in this milestone, either merged or explicitly deferred

### Acceptance checks

- repeated ingest cycles do not create duplicate rows for the same source item
- normalization produces stable company and title values across cycles
- duplicate handling behavior is documented and test-covered

## Workstream 3: Stale Job Lifecycle

### Tasks

- define which jobs are safe to delete versus mark stale or archive
- review current stale-removal behavior for jobs that disappear from live feeds
- make stale handling explicit in ingest state and job state where needed
- ensure applied or manually curated jobs are never removed by ingest cleanup

### Acceptance checks

- disappearing feed items are handled according to documented rules
- manually advanced jobs are preserved across ingest cycles
- stale behavior is predictable and observable in API responses

## Workstream 4: Data Quality and Schema Tightening

### Tasks

- identify required fields for operational triage: title, company, canonical source URL, source name, location mode, created or posted time where available, and summary
- add missing persisted fields if current payloads support them
- capture normalization confidence or fallback states when data is incomplete
- define defaults for unknown or missing source fields
- validate that ingest output is usable in the dashboard without manual cleanup

### Acceptance checks

- the majority of ingested jobs include the minimum triage fields
- incomplete jobs are clearly marked rather than silently treated as clean
- schema changes are reflected in API responses and tests

## Workstream 5: Dashboard and API Visibility

### Tasks

- surface ingest health at source level in the API response and dashboard
- show last successful ingest time, last failure time, item counts, and error summaries
- differentiate between feed freshness and application queue freshness
- add operator-facing indicators when current data is stale or partially degraded

### Acceptance checks

- an operator can tell whether the feeds are healthy from the UI
- degraded ingest state is visible without checking container logs
- the dashboard reflects per-source health, not just aggregate job counts

## Workstream 6: Test and CI Coverage

### Tasks

- add focused unit tests for source iteration, normalization, scoring boundaries, and stale cleanup rules
- add fixture-based tests for Remote OK and HN payload handling
- add a narrow ingest smoke test that exercises worker ingestion without depending on live internet during CI
- wire the relevant test commands into CI for merge protection on `main`

### Acceptance checks

- CI runs ingest-related tests automatically on changes touching backend, worker, or source config
- fixture-based tests catch schema drift in supported sources
- merge to `main` is blocked when ingest validations fail

## Suggested Execution Order

1. source reliability
2. normalization and deduplication
3. stale job lifecycle
4. dashboard and API visibility
5. data quality and schema tightening
6. test and CI coverage

## Definition of Done

Milestone 1 is done when the supported live sources can be trusted as the system-of-record input for daily triage, and regressions in that path are blocked by automated validation.