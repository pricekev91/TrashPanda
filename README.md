# TrashPanda

TrashPanda is a self-hosted AI job automation system for local-first job discovery, resume tailoring, application tracking, recruiter communication, and search analytics.

The first delivery target is HLH at `192.168.6.10`.

## Repository Boundary

This repository owns application concerns only:

- job ingestion, normalization, scoring, and tracking logic
- resume intelligence and approval workflows
- recruiter and email automation
- dashboard and API code
- app-level containers and compose definitions
- prompts, schemas, and application configuration contracts

This repository does not own HLH host infrastructure. Proxmox host changes, LXC definitions, storage wiring, and shared AI appliance deployment belong in the `iac-hlh` repository.

## First Milestone

The first end-to-end slice is:

1. ingest jobs
2. normalize and store them in Postgres
3. score them against the master resume
4. show the scored pipeline in the dashboard

That milestone proves the core application path without mixing in email automation, resume generation, or recruiter workflows too early.

## Runtime Relationship

TrashPanda depends on a shared local AI appliance exposed through an OpenAI-compatible interface. The AI appliance is shared infrastructure and can serve TrashPanda, BrickCipher, and VoxChimera.

- `TrashPanda` consumes the appliance API
- `iac-hlh` deploys the appliance on HLH
- `iac-plh` deploys the equivalent platform on PLH

## Initial Code Shape

The application stack will stay technology-separated so layers can change independently:

- `frontend/` for the web dashboard
- `backend/` for the API and application services
- `workers/` for async pipeline jobs
- `docs/` for architecture and ADRs
- `deploy/` for app-local container definitions

The architecture baseline lives in `docs/architecture.md`.

## Delivery Roadmap

The project plan lives in `docs/roadmap.md`.

That document is the single source of truth for delivery sequencing, milestone scope, and acceptance criteria. Keep the detailed roadmap there so it is maintained in one place.

Current milestone focus:

1. trustworthy live ingest
2. resume-aware ranking
3. workflow operations

Use the README to surface the roadmap. Use the roadmap document to maintain it.

## Initial Local Runtime

The repository now includes a first runnable milestone scaffold:

- `dashboard` served from `frontend/`
- `backend` API from `backend/`
- `worker` process from `workers/`
- Postgres in Docker Compose
- repo-owned runtime config in `deploy/runtime/config/`
- repo-owned writable app data in `deploy/runtime/data/`

Run it locally with:

```bash
cp .env.example .env
docker compose -f deploy/compose.yaml up --build
```

The worker now ingests live jobs from the sources defined in `deploy/runtime/config/ingest-sources.json` and writes ingest state snapshots into `deploy/runtime/data/`. The default runtime config now includes `Remote OK` as the first mainstream public job-board source because it exposes a stable public JSON feed without auth or brittle scraping.

The dashboard also persists a master resume in `deploy/runtime/data/master-resume.md` through the API so later scoring and tailoring work can operate against a real canonical resume instead of placeholder text.

Endpoints:

- dashboard: `http://localhost:3000`
- API health: `http://localhost:8000/health`
- jobs API: `http://localhost:8000/api/v1/jobs`