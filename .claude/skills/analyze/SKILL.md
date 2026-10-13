---
name: analyze
description: Inspect the three Mona CSV datasets, evaluate data quality, identify eligibility constraints, and report findings. Read-only; does not modify application code.
argument-hint: "[optional focus, e.g. a file name or question]"
disable-model-invocation: true
allowed-tools: Read, Grep, Glob
---

# Analyze the Mona datasets

Inspect the three provided CSV datasets and report what they contain, how clean they are, and what they imply for matching. Optional focus from the user: $ARGUMENTS

This skill is **read-only**. Do not create, edit, or delete application code, tests, or the CSV files. Throwaway analysis scripts go in the session scratchpad directory, never in the repo.

## Steps

1. **Locate the data.** Look in `data/` first, then search the repo for `*.csv`. If fewer than three datasets are found, stop and say which are missing; do not guess at a schema.
2. **Profile each file.** Read the header and enough rows to be representative; for large files, compute over the whole file with a scratchpad script instead of sampling by eye. Record:
   - row count, column names, inferred type per column
   - what one row represents (a business, a grant, a loan, ...)
   - a likely primary key and whether it is actually unique
3. **Evaluate data quality.** For each column where it matters:
   - missing or blank values (count and percentage)
   - duplicates, both exact rows and repeated keys
   - inconsistent formats: dates, currency, percentages, booleans, casing, stray whitespace
   - inconsistent categories (e.g. `CA` vs `California`), free text where a category is expected
   - out-of-range or implausible values (negative amounts, deadlines in the past, min greater than max)
   - encoding or delimiter problems, multi-value cells (comma or semicolon lists inside one field)
4. **Map relationships.** Identify which columns link the datasets and check that the values really join: count matched and orphaned values on each side.
5. **Identify eligibility constraints.** For each opportunity field that restricts who qualifies (location, industry, business size, revenue, years in operation, ownership, use of funds, deadlines, amount ranges):
   - name the business-side field it would be compared against
   - classify it as a **hard filter** (pass/fail) or a **scoring criterion** (ranking), per the matching rules in CLAUDE.md
   - note how often it is populated, and what "missing" should mean for it
   - flag constraints that exist only in free text and would need parsing

## Report

Reply in the conversation; do not write a report file unless asked. Use this structure:

- **Overview**: one short paragraph, then a table of file, rows, columns, what a row represents.
- **Schema**: per file, a table of column, type, percent missing, notes.
- **Data quality issues**: ordered by impact on matching, each with the file, column, count of affected rows, and one concrete example value.
- **Relationships**: join keys and match rates.
- **Eligibility constraints**: table of opportunity field, business field, hard filter or scoring, coverage, caveats.
- **Open questions**: ambiguities that need a human decision before implementation.

Report only what the data shows. Give counts and example values, state how much of each file was actually examined, and mark any inference as an inference.
