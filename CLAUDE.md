# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

mona-demo-benjaminle matches small businesses with relevant grant and loan opportunities, using three provided CSV datasets as the only data source.

This is a greenfield MVP with a **three-hour development budget**. The goal is a working end-to-end slice (CSV → matching API → UI showing ranked matches with reasons), not breadth. When in doubt, pick the simpler option and finish the vertical slice first.

Priorities, in order: working end-to-end flow, explainable matching, tests on the matching logic, maintainability. Polish comes last.

## Status

Nothing is scaffolded yet. The layout and commands below are the agreed targets; update this file if the real setup diverges. The CSV datasets have not been added, so their columns are unknown — inspect the actual files before writing loaders or models, and never guess at a schema.

## Stack

- Frontend: React + TypeScript + Vite, tested with Vitest
- Backend: Python + FastAPI, tested with Pytest
- Data: local CSV files loaded at startup (no database)

## Target layout

```
backend/
  app/
    api/        # FastAPI routers: HTTP only, no business logic
    domain/     # Pydantic models + matching rules: pure Python, no I/O
    data/       # CSV loading, validation, normalization
    main.py
  tests/
frontend/
  src/
    api/        # typed client for the backend
    components/
    types/      # mirrors backend response models
data/           # the three provided CSVs, read-only
```

## Commands

Backend (run from `backend/`):

```
pip install -r requirements.txt
uvicorn app.main:app --reload          # http://localhost:8000, docs at /docs
pytest                                 # all tests
pytest tests/test_matching.py::test_name   # single test
```

Frontend (run from `frontend/`):

```
npm install
npm run dev                            # http://localhost:5173
npm run test                           # Vitest
npx vitest run src/path/file.test.ts -t "test name"   # single test
npm run build                          # type-check + production build
```

The shell is Windows PowerShell 5.1: chain commands with `;`, not `&&`.

## Architecture rules

- **Dependencies point inward.** `api` → `domain` ← `data`. The `domain` package imports neither FastAPI nor file/CSV code, so matching can be unit-tested with plain in-memory objects.
- **CSV parsing happens once, at the edge.** `data/` turns raw rows into validated domain models (trimmed strings, parsed numbers/dates, normalized categories). Nothing outside `data/` touches raw rows or column names.
- **Bad rows are reported, not silently dropped.** Skip a row that fails validation, but log it with its file and row number.
- **Load CSVs once at startup** and hold them in memory; inject them into routes via FastAPI dependencies so tests can substitute fixtures.
- **The frontend holds no matching logic.** It renders what the API returns, including the explanations.

## Explainable matching

Every match must be able to say why it was returned. This is the core product requirement, so it shapes the design:

- Matching is **deterministic and rule-based**: no ML models, embeddings, or LLM calls.
- Split rules into **eligibility filters** (hard pass/fail, e.g. location or business-size limits) and **scoring criteria** (weighted, contribute to ranking).
- Each rule is a small, separately testable function that returns its outcome together with a human-readable reason.
- A match result carries the total score plus the per-rule breakdown: which criteria matched, which did not, and the reason text for each. The UI shows this breakdown.
- Weights and thresholds live in one named config module, not scattered as literals.
- Missing data in a CSV field is an explicit "unknown" outcome with its own reason, never treated as a silent match or a silent failure.

## Standards

- Python: type hints on all functions, Pydantic models for anything crossing the API boundary.
- TypeScript: `strict` mode, no `any`; API response types defined once in `frontend/src/types`.
- Keep the API surface small and typed with response models, so `/docs` stays an accurate contract.
- Add a dependency only when it saves clear time within the budget.

## Testing

- Put most test effort into `domain/` matching rules: one test per rule covering match, non-match, and missing-data cases, plus a few ranking tests over small hand-built fixtures.
- Test CSV loading against small fixture files in `backend/tests/fixtures/`, not the full datasets.
- One or two API tests through FastAPI's `TestClient` to cover the wiring.
- Frontend: test the components that render match results and explanations; skip tests for trivial presentational markup.
- A feature is done when its tests pass and it works through the UI against the real CSVs.
