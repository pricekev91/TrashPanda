# Architectural Decision Records — TrashPandaOmega

This file tracks significant architectural decisions made for this project using a lightweight ADR format.

---

## ADR Template

```
## ADR NNN: <Title>

**Date:** YYYY-MM-DD
**Status:** Proposed | Accepted | Deprecated | Superseded by ADR-NNN

### Context
<What is the situation and why does a decision need to be made?>

### Decision
<What was decided?>

### Consequences
<What are the trade-offs, benefits, and risks of this decision?>
```

---

## ADR 001: Why this project is isolated in its own repository

**Date:** 2026-05-03
**Status:** Accepted

### Context

The author maintains three separate projects: TrashPandaOmega, BrickCipher, and VoxChimera. Each project has a distinct domain, technology profile, and release cadence:

- **TrashPandaOmega** — automation, scraping, and job-pipeline orchestration (Python)
- **BrickCipher** — cryptographic tooling and ciphers (separate domain)
- **VoxChimera** — audio/voice processing (separate domain)

A monorepo approach was considered but rejected. Combining unrelated projects creates hidden coupling risks, complicates CI/CD pipelines, increases cognitive overhead for contributors, and muddies dependency management.

### Decision

Each project lives in its own isolated GitHub repository. There is no shared code, no shared dependencies, and no shared release cycle between TrashPandaOmega, BrickCipher, and VoxChimera.

### Consequences

- **Positive**: Clean separation of concerns; each repo can evolve independently.
- **Positive**: Dependency changes in one project cannot break another.
- **Positive**: CI/CD pipelines are scoped to a single project, reducing noise.
- **Positive**: Contributors to one project do not need to understand the others.
- **Negative**: Cross-project tooling or shared utilities cannot be easily reused without publishing a shared package (which is an intentional forcing function for explicit, versioned APIs if sharing ever becomes necessary).

---

## ADR 002: Initial technology stack selection (Python + async + scraping libs)

**Date:** 2026-05-03
**Status:** Accepted

### Context

TrashPandaOmega needs to perform concurrent web scraping, schedule recurring jobs, and orchestrate data pipelines. The choice of language and libraries has long-term implications for maintainability, ecosystem support, and developer velocity.

Alternatives considered:

| Option | Notes |
|---|---|
| Go | Strong concurrency model, but smaller scraping ecosystem |
| Node.js | Large async ecosystem, but less natural for data pipelines |
| Python (sync) | Familiar, but blocking I/O is a bottleneck for scraping at scale |
| **Python (async)** | **Rich scraping ecosystem + native async runtime = best fit** |

### Decision

The project uses **Python 3.11+** as its primary language, with an async-first design:

- **`asyncio`** (stdlib) as the async runtime
- **`httpx`** or **`aiohttp`** for async HTTP requests
- **`beautifulsoup4`** for HTML parsing
- **`playwright`** (planned) for JavaScript-heavy scraping
- **`APScheduler`** (planned) for job scheduling
- **`pytest`** + **`pytest-asyncio`** for testing

### Consequences

- **Positive**: Python has the broadest scraping and data-processing ecosystem.
- **Positive**: `asyncio` enables high-concurrency I/O without threads.
- **Positive**: `pytest` is the de facto standard for Python testing; excellent async support via `pytest-asyncio`.
- **Neutral**: Python's GIL limits CPU-bound parallelism; however, this project is I/O-bound so the GIL is not a constraint.
- **Negative**: Async Python has a steeper learning curve than synchronous Python for some contributors.
- **Negative**: Dependency management (pinning, auditing) requires discipline to avoid supply-chain risks.
