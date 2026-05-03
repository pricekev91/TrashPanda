# Contributing to TrashPandaOmega

Thank you for your interest in contributing. This document describes the conventions and workflows used in this project.

---

## Getting Started

### Clone and Set Up

```bash
git clone https://github.com/pricekev91/TrashPandaOmega.git
cd TrashPandaOmega

python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

pip install -r requirements.txt   # once populated
```

### Run Tests

```bash
pytest tests/
```

---

## Branching Model

| Branch pattern | Purpose |
|---|---|
| `main` | Stable, release-ready code |
| `feature/<name>` | New features or experiments |
| `fix/<name>` | Bug fixes |
| `chore/<name>` | Maintenance, tooling, docs |

- All changes enter `main` via pull request.
- Keep branches short-lived; open a PR as soon as there is something reviewable.
- Do not push directly to `main`.

---

## Commit Messages

This project follows [Conventional Commits](https://www.conventionalcommits.org/).

```
<type>(<scope>): <short summary>
```

### Types

| Type | When to use |
|---|---|
| `feat` | A new feature |
| `fix` | A bug fix |
| `docs` | Documentation changes only |
| `chore` | Tooling, deps, CI — no production code change |
| `refactor` | Code change that neither fixes a bug nor adds a feature |
| `test` | Adding or updating tests |
| `perf` | Performance improvement |

### Examples

```
feat(scraper): add async HTTP fetch with retry support
fix(scheduler): handle missed jobs on restart
docs(architecture): add data flow diagram
chore(deps): pin httpx to 0.27.0
```

---

## Code Style

- **Python 3.11+** — use modern Python features (match statements, `|` union types, etc.)
- **Type hints** — all functions and methods should have type annotations
- **Docstrings** — public functions and classes require docstrings
- **Linting** — `ruff` is the preferred linter/formatter (configuration TBD)
- **Async** — I/O-bound operations must use `async`/`await`; avoid blocking calls in async contexts
- **No magic** — explicit is better than implicit; avoid overuse of decorators, metaclasses, or dynamic dispatch

---

## ADR Workflow

Significant architectural decisions are recorded in [docs/decisions.md](docs/decisions.md).

When you make a decision that meaningfully changes the architecture, dependencies, or direction of the project:

1. Copy the ADR template from the top of `docs/decisions.md`.
2. Assign the next sequential number.
3. Fill in Context, Decision, and Consequences.
4. Set status to `Accepted`.
5. Include the ADR in the same PR as the change it documents.

---

## Questions

Open an issue or start a discussion if you have questions. This is a solo-friendly project, so there is no formal review SLA.
