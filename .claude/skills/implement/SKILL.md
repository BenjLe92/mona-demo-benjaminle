---
name: implement
description: Implement an approved feature following CLAUDE.md, with focused changes and relevant tests.
argument-hint: "<approved feature or plan step to implement>"
disable-model-invocation: true
---

# Implement a feature

Implement: $ARGUMENTS

If no feature was given, ask what to implement and stop.

## Before writing code

1. Read `CLAUDE.md`. Its architecture rules, explainable-matching requirements, and standards are binding.
2. Find the approved plan for this feature in the conversation (normally from `/plan`). Follow it. If there is no plan and the feature is more than a small, obvious change, outline the approach in a few lines and get the user's agreement first.
3. Read the code you will touch and match its existing naming, structure, and idioms.
4. If the work depends on CSV fields, confirm the column names against the real files.

## While implementing

- **Stay in scope.** Change only what this feature needs. No drive-by refactors, renames, or reformatting; mention unrelated problems you notice instead of fixing them.
- **Respect the layers.** HTTP handling in `api`, matching rules in `domain` with no I/O or FastAPI imports, CSV parsing in `data`, and no matching logic in the frontend.
- **Keep matching explainable.** Every new rule is a small function that returns its outcome with a human-readable reason, handles missing data as an explicit "unknown", and takes its weights and thresholds from the shared config module.
- **Write the tests with the code.** Cover match, non-match, and missing-data cases for each rule; add loader, API, or component tests where the feature touches those layers. Use small fixtures, not the full datasets.
- **Work in small steps** that each leave the app runnable, and reach a working end-to-end slice before adding refinements.
- **Add dependencies sparingly**, and say so when you add one.
- If the plan turns out to be wrong or something blocks it, stop and explain the deviation before going a different way.

## Before finishing

1. Run the tests for the code you changed, plus the type check and build where they exist. Fix failures you introduced.
2. Do not commit or push unless the user asks.
3. Update `CLAUDE.md` if commands, layout, or architecture changed.

## Report

Summarize briefly:

- what was implemented, and any deviation from the plan with the reason
- files created and changed
- tests added, and the actual result of each check that was run
- anything left undone, skipped, or not verified
