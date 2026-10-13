---
name: verify
description: Run available tests, linting, type checks, and integration checks, then report the actual results. Does not modify code.
argument-hint: "[optional scope: backend, frontend, or a specific check]"
disable-model-invocation: true
---

# Verify the project

Run the project's checks and report what actually happened. Optional scope from the user: $ARGUMENTS

This skill **does not modify code**. Do not edit source, tests, or configuration, and do not fix failures; report them. Do not run checks in a fixing mode (no `--fix`, no formatters that write files, no snapshot updates). Do not install or upgrade dependencies without asking.

## Steps

1. **Discover what is available.** Read `CLAUDE.md` for the documented commands, then confirm against the real configuration (`backend/requirements.txt` or `pyproject.toml`, `frontend/package.json` scripts, lint and type-check config). Run only checks that are actually configured.
2. **Run each available check**, limited to the user's scope if one was given. Independent checks can run in parallel.
   - Backend tests: `pytest` from `backend/`
   - Backend lint and type checks: only if a tool such as ruff or mypy is configured
   - Frontend tests: `npx vitest run` from `frontend/` (run mode, not watch mode)
   - Frontend type check and build: `npm run build`, or `npx tsc --noEmit`
   - Frontend lint: `npm run lint`, if the script exists
3. **Integration check**, when both sides exist: start the backend, confirm it starts cleanly and loads the CSVs, call the main endpoints with a real request, and check the response shape and that matches include their explanations. If the frontend is runnable, confirm it builds and can reach the API. Stop every server you started.
4. **Never run a check in watch or interactive mode**, and use a timeout so a hung process cannot stall the run.

The shell is Windows PowerShell 5.1: chain commands with `;`, not `&&`.

## Report

Start with one line giving the overall status: all passing, failures found, or could not fully verify. Then a table:

| Check | Command | Result | Details |
|-------|---------|--------|---------|

- **Result** is one of: passed, failed, skipped (not configured), could not run.
- **Details** gives counts (tests passed, failed, skipped; number of lint or type errors) and duration where available.

After the table:

- **Failures**: for each one, the test or file, the exact error message, and the location. Quote real output; do not paraphrase it into something milder.
- **Not verified**: every check that was skipped or could not run, with the reason (missing dependency, nothing scaffolded, no config).
- **Likely causes**: optional, brief, and clearly labeled as diagnosis, not as fact.

Report results exactly as observed. A check that did not run is never reported as passing, and a passing unit suite is not described as proof the feature works end to end unless the integration check also ran.
