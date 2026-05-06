# TrashPanda Architecture

## 1. Intent

TrashPanda is a local-first AI automation platform for job search operations. It automates discovery, normalization, ranking, tailoring support, application tracking, recruiter communication, and analytics while keeping inference and sensitive data local.

The primary deployment target is HLH at `192.168.6.10`.

## 2. Repository Ownership

This repository owns application behavior.

Included here:

- domain models for jobs, resumes, applications, companies, recruiters, and events
- backend APIs and worker processes
- dashboard frontend
- app-level Docker assets
- prompts, templates, and scoring logic
- application-facing secrets contract and environment variable schema

Excluded from this repository:

- Proxmox host configuration
- LXC lifecycle and container provisioning
- host networking, bridge, and mount orchestration
- shared AI appliance deployment logic

Those concerns belong in `iac-hlh` for HLH and `iac-plh` for PLH.

## 3. First Milestone

The first build target is the smallest useful closed loop:

1. ingest jobs from one or more sources
2. normalize jobs into a stable internal schema
3. persist them in Postgres
4. score them against the master resume
5. render the prioritized queue in the dashboard

Deferred until after that slice:

- email ingestion and recruiter reply handling
- tailored resume generation
- cover letter generation
- interview preparation agents
- company intelligence enrichment beyond lightweight metadata

## 4. Layered Application Shape

TrashPanda should remain modular so technology choices can change without rewriting the entire system.

### 4.1 Frontend

- dashboard UI
- job pipeline views
- approval flows
- analytics views

### 4.2 Backend API

- REST or equivalent application API
- authentication and authorization policy
- orchestration entrypoints for ingestion and scoring
- state machine transitions for job lifecycle

### 4.3 Workers

- scraping and normalization workers
- scoring workers
- future resume tailoring and email processors

### 4.4 Data Layer

- Postgres as system of record
- application migrations owned here
- optional cache or queue layers added only when justified

## 5. External Dependency Contract

TrashPanda consumes a shared AI appliance through an OpenAI-compatible endpoint.

Contract expectations:

- local network access only
- stable base URL and API key contract
- health endpoint for readiness checks
- model selection abstracted behind the appliance rather than embedded in app logic

TrashPanda must not assume a specific inference engine implementation.

## 6. Security Baseline

- local inference only
- no telemetry by default
- no external logging sink by default
- secrets stored outside the repo and mounted at runtime
- human approval required before any outward-facing application action is fully automated

## 7. HLH Deployment Assumption

For the first HLH deployment, TrashPanda runs inside a dedicated application LXC that hosts the app-local container stack. The AI appliance remains separate and shared.

That means:

- the app repo defines the application containers
- the host repo defines where and how that application LXC exists
- the AI appliance remains a sibling service, not an embedded TrashPanda component