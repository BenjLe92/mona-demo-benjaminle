---
name: review
description: Perform a read-only code review, reporting findings by severity with file location and recommended fix.
argument-hint: "[optional scope: path, branch, or commit range]"
disable-model-invocation: true
allowed-tools: Read, Grep, Glob, Bash(git status:*), Bash(git diff:*), Bash(git log:*), Bash(git show:*)
---

# Code review

Review the code and report findings. Scope from the user: $ARGUMENTS

This skill is **read-only**. Do not edit, create, or delete files, and do not apply fixes, even obvious ones. Recommend them instead.

## Scope

- If the user gave a path, branch, or commit range, review that.
- Otherwise review uncommitted changes (`git status`, `git diff`, `git diff --staged`, and untracked files).
- If there are no uncommitted changes, review the most recent commit, and say that is what was reviewed.
- If there is nothing to review, say so and stop.

Read enough surrounding code to judge each change in context: callers, the tests that cover it, and the types it relies on.

## What to look for

Read `CLAUDE.md` first; violations of it are findings.

- **Correctness**: logic errors, wrong edge-case handling, off-by-one, unhandled empty or missing input, incorrect types.
- **Matching and explainability**: rules that return no reason, reasons that do not match the actual outcome, missing data treated as a silent match or failure, non-deterministic ranking, weights or thresholds hard-coded outside the config module.
- **Data handling**: raw CSV rows or column names used outside `data`, invalid rows dropped without logging, unsafe parsing of numbers, dates, or currency.
- **Architecture**: `domain` importing FastAPI or doing I/O, business logic in routers, matching logic in the frontend, dependencies pointing outward.
- **API contract**: missing response models, frontend types that disagree with the backend, unhandled error responses.
- **Tests**: changed behavior with no test, tests that cannot fail, missing non-match or missing-data cases.
- **Security and robustness**: unvalidated input, path handling, overly permissive CORS, secrets in code.
- **Maintainability**: duplication, dead code, unclear names, needless complexity. Report these only when they are worth acting on.

Verify each finding against the code before reporting it. Do not report style preferences a formatter would settle, and do not pad the list.

## Report

Start with one or two sentences: what was reviewed and the overall verdict. Then list findings grouped by severity, most severe first:

- **Critical**: wrong results, crashes, data loss, or security problems
- **High**: likely bugs, or clear violations of CLAUDE.md architecture rules
- **Medium**: missing tests, fragile code, contract mismatches
- **Low**: minor maintainability or clarity issues

For each finding give:

- **Location**: file path and line, as a clickable reference
- **Problem**: what is wrong, and the concrete input or situation that triggers it
- **Recommended fix**: the specific change to make

If a severity has no findings, omit it. If there are no findings at all, say so plainly. Finish by noting anything that was not reviewed or could not be checked.
