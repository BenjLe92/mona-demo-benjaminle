---
name: plan
description: Produce a technical implementation plan for a feature, covering architecture, API contracts, risks, testing, and tradeoffs. Planning only; does not implement.
argument-hint: "<feature or change to plan>"
disable-model-invocation: true
allowed-tools: Read, Grep, Glob
---

# Plan a feature

Produce a technical implementation plan for: $ARGUMENTS

This skill **does not implement**. Do not create or edit application code, tests, or configuration. Deliver the plan in the conversation; write it to a file only if the user asks.

If no feature was given, ask what to plan and stop.

## Before planning

1. Read `CLAUDE.md` and treat its architecture rules, explainable-matching requirements, and three-hour budget as constraints.
2. Read the code the feature touches, so the plan builds on what exists instead of what is assumed. If the repo is not scaffolded yet, say so and plan from the target layout in CLAUDE.md.
3. If the feature depends on CSV fields, check the real files (or an earlier `/analyze` report in this conversation). Never plan against guessed column names; list unknown ones under open questions.

## Plan contents

Keep it proportionate: a small change gets a short plan. Include each section, and write "none" where one does not apply.

- **Goal**: what the user can do when this is finished, and what is explicitly out of scope.
- **Architecture**: which layers change (`api`, `domain`, `data`, frontend) and how the pieces interact. Confirm dependencies still point inward and that matching logic stays in `domain`.
- **API contracts**: for every new or changed endpoint, the method, path, request shape, response shape, and error cases, written as concrete typed examples. Show how match explanations appear in the response.
- **Data**: CSV columns used, normalization needed, and how missing or invalid values are handled.
- **Implementation steps**: an ordered list of small steps, each naming the files to create or change and leaving the app in a working state. Order them so an end-to-end slice works as early as possible.
- **Testing**: the specific cases to cover (match, non-match, missing data, edge cases), at which level (rule unit test, loader test, API test, component test), and what fixtures are needed.
- **Risks**: what could go wrong or take longer than expected, with a mitigation or fallback for each.
- **Tradeoffs**: alternatives considered, which one is recommended, and why. Call out anything simplified to fit the budget and what it would cost to revisit.
- **Estimate**: rough time per step, and how the total sits against the remaining budget.
- **Open questions**: decisions that need the user before implementation starts.

End by asking the user to approve or amend the plan. Implementation happens separately through `/implement`.
