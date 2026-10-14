# Technical notes

Notes on the approach and the key tradeoffs. For the full list of matching rules and scoring weights, see [CRITERIA.md](CRITERIA.md). For setup and run instructions, see [README.md](README.md).

## Approach

- **Rules, not AI.** Matching is deterministic and every decision comes with a written reason. For each grant or loan, the API returns an eligibility status, a 0–100 relevance score, and the reasons for both. The frontend holds no matching logic; it displays what the API returns.
- **Eligibility and relevance are kept separate.** Eligibility asks whether the business can apply. Relevance asks how good a fit the opportunity is. `ranking.py` never reads an eligibility result, and eligibility never reads a score, so a strong fit can never hide a failed requirement.
- **Layered backend.**

  ```
  backend/app/
    api/      HTTP only: query params, filtering, paging, response envelopes
    domain/   rules, scoring and models; pure Python, no file or web imports
    data/     the only code that knows CSV column names; parses cells and free text
  ```

  Dependencies point inward: `api` and `data` import `domain`, never the other way round. All scoring weights and thresholds live in `domain/config.py`.
- **The data is loaded once.** The three CSVs are read into memory at startup. Each file gets a `LoadReport` of skipped and excluded rows, which `/api/meta` shows.
- **Stack.** Python and FastAPI (Pydantic models are returned directly as responses) on the backend; React, TypeScript and Vite on the frontend.

## Key tradeoffs

- **The top status is "Likely Eligible", never "Eligible".** Only some requirements can be checked from the data, so every result says so.
- **Unknown is not no.** If a business field is blank, the result is Needs Verification, not a fail. Flags are used exactly as recorded and never inferred. For example, Black-owned is not taken to mean BIPOC, and an LLC is not assumed to be for-profit; the data has an LLC marked as a nonprofit.
- **Free-text criteria are read cautiously.** Each clause is treated as a firm rule (can fail a business), an ambiguous statement (Needs Verification), or a preference or mention (ignored). When a pattern is unclear, it is treated as ambiguous. A wrong rejection costs a business more than an extra check.
- **Criteria the app can't evaluate are never silently passed.** A stated revenue cap, tenure rule or residency rule is quoted back as Needs Verification rather than ignored. As a result, Likely Eligible is rare for grants. That is deliberate: I chose honesty over looking optimistic. Loans are less affected because their requirements are structured columns.
- **Ranges are compared conservatively.** A revenue or credit-score band entirely above a minimum passes, entirely below fails, and one that straddles the minimum needs verification.
- **Explicit lookup tables, not fuzzy matching.** City aliases (Brooklyn → NYC), states and the industry mapping are written out in `data/mappings.py`. They are predictable and easy to test, but they don't cover every spelling.
- **Industry affects ranking only.** A grant listed only for nonprofits asks a for-profit business to verify; it never rules it out.
- **Past deadlines are not assumed to renew.** An open grant whose date has passed is dropped, even if it is listed as annual or monthly. Only rolling programmes stay, with a warning. This can hide a recurring programme until its date is updated.
- **Simplicity within the time budget.** There is no database, authentication or caching layer. The datasets are small, so in-memory matching on each request is fast enough.

## Limitations

- Grant IDs (`G-0001`, …) come from the row position in the CSV, so they change if the rows are reordered. The grant index has no ID column.
- Numeric criteria in free text, such as revenue caps, employee limits and years in business, are flagged but not compared with the profile.
- The location, metro-alias and industry tables only cover what appears in the current data.
- The frontend type definitions (`frontend/src/types/api.ts`) mirror the backend models by hand.

## Next steps

- Parse common numeric criteria (revenue caps, years in business) into real checks, using the same band logic as loans.
- Give grants stable IDs, for example a hash of the name and the funder.
- Let users fill in missing profile fields so Needs Verification results can resolve to a final status.
- Generate the frontend types from the OpenAPI schema.

## Testing

- **Backend:** 362 pytest tests cover the rules, normalizers, free-text parsing, ranking, loaders and API.
  - Rule and ranking tests use in-memory objects from `tests/conftest.py`.
  - Loader and API tests use small fixture CSVs, never the real data, and pin the date.
  - `tests/test_grant_regressions.py` keeps the wording of real grant records that were once misjudged. Each is checked against one business that qualifies and one that doesn't.
- **Frontend:** Vitest tests, a type-checked build (`npm run build`) and lint (`npm run lint`).
- **Reproducible demos:** set `MONA_AS_OF_DATE=YYYY-MM-DD` to pin the date used for deadline checks.
