# TrashPanda Delivery Roadmap

This document is the delivery roadmap for TrashPanda. It defines the milestones, sequencing, and acceptance criteria needed to move from the current live-ingest prototype to the full local-first job operations platform.

Use this as the planning source of truth.

## Delivery Terms

- Roadmap: the ordered path from current state to end state
- Milestone: a bounded delivery slice with clear acceptance criteria
- Backlog: the queue of tasks that support a milestone
- CI pipeline: automated validation such as lint, tests, and build checks
- CD pipeline: automated deployment and release flow into runtime environments

## Current State

TrashPanda already has the first operational skeleton in place:

- dashboard UI
- backend API
- worker-driven live ingest
- Postgres persistence
- baseline scoring and next-action routing

The immediate goal is not to start with real data from scratch. The immediate goal is to harden the existing live-data path until the output is trustworthy enough to drive daily decisions.

## End State

TrashPanda operates as a local-first job operations system that can:

- ingest jobs from multiple sources reliably
- normalize and deduplicate them into a stable internal model
- score them against the master resume and preferences
- route each job into an actionable workflow state
- support tailoring, application tracking, recruiter follow-up, and analytics
- deploy safely through repeatable validation and release automation

## Milestone 1: Trustworthy Live Ingest

Goal: make the ingest-to-dashboard path reliable enough for day-to-day use.

Scope:

- keep current sources working consistently
- improve normalization and deduplication rules
- tighten stale job handling
- expose ingest health and source-level failure details
- validate that stored jobs are clean enough to review in the dashboard

Acceptance criteria:

- at least two live sources ingest on schedule without manual intervention
- duplicate jobs are suppressed consistently across repeated ingest cycles
- stale jobs are removed or marked predictably
- ingest failures are visible in the API and dashboard
- the dashboard queue is populated by live source data, not placeholders

## Milestone 2: Resume-Aware Ranking

Goal: move from keyword-only ranking to decision-grade prioritization.

Scope:

- score jobs against the saved master resume
- add transparent ranking explanations
- incorporate candidate preferences such as remote preference, title fit, and platform focus
- separate raw ingest signals from ranking outputs

Acceptance criteria:

- rankings change in a predictable way when the master resume changes
- score explanations are visible and understandable in the UI
- high-priority jobs are meaningfully distinguishable from low-priority jobs
- ranking logic is covered by focused tests

## Milestone 3: Workflow Operations

Goal: make TrashPanda operational for managing active job pursuit.

Scope:

- improve lifecycle transitions and next-action handling
- support batch triage and queue management
- add follow-up scheduling and overdue follow-up visibility
- make operator actions durable and auditable

Acceptance criteria:

- a user can review, shortlist, apply, archive, snooze, and follow up from the dashboard
- state transitions remain consistent across refreshes and ingest cycles
- the queue clearly separates discovery work from in-flight work

## Milestone 4: Tailoring and Submission Support

Goal: assist with resume tailoring and application preparation while keeping a human approval gate.

Scope:

- generate resume-tailoring suggestions from the master resume and job description
- track tailored artifacts per job
- support draft cover letter generation where appropriate
- preserve explicit human approval before any outbound action

Acceptance criteria:

- tailored outputs are stored and associated with a job record
- the operator can review generated content before use
- no external submission action happens without explicit approval

## Milestone 5: Recruiter and Search Analytics

Goal: close the loop after applications are submitted.

Scope:

- track recruiter contacts and interactions
- add interview and follow-up visibility
- report pipeline metrics such as application velocity, response rate, and ghosting rate
- support historical review of search performance

Acceptance criteria:

- recruiter and follow-up activity is visible in the system of record
- dashboard metrics reflect actual pipeline state rather than inferred placeholders
- trend reporting helps guide search strategy

## Delivery Enablers

These are cross-cutting workstreams that should advance alongside the milestones.

### Repository and Naming Hygiene

- rename the hosted repository from TrashPandaOmega to TrashPanda
- align remote URLs, docs, and deployment labels with the canonical project name

### CI/CD Foundation

- add lint and test automation for backend, worker, and frontend slices
- add ingest smoke tests for supported sources
- define promotion expectations for local, lab, and production-like deployments
- treat CI failures as merge blockers for `main`

### Operations and Observability

- add source-level ingest metrics and logs
- define backup and restore expectations for Postgres and runtime data
- document runtime secrets and environment contracts

## Recommended Near-Term Sequence

1. Rename the hosted repository and normalize references.
2. Harden Milestone 1 until the live ingest path is stable.
3. Add CI gates before expanding the source set or increasing automation.
4. Build Milestone 2 so ranking becomes resume-aware.
5. Expand into workflow operations only after ingest and ranking are trustworthy.

## Working Rule

Do not widen scope just because the UI can already display more concepts. Advance the platform by closing one trustworthy operational slice at a time.