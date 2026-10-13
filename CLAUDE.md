# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

mona-demo-benjaminle matches small businesses with grants and loans they may qualify for, using three CSV datasets in `data/` as the only data source. A user picks one of the business profiles and sees ranked opportunities, each with an eligibility status, a relevance score, and the reasons for both.

It is an MVP built to a three-hour budget. Prefer the simpler option and keep the end-to-end flow working. There is no database, no authentication, and no AI or ML in the matching.

## Commands

The shell is Windows PowerShell 5.1: chain commands with `;`, not `&&`. Writing files with `Set-Content -Encoding utf8` adds a byte-order mark that breaks `package.json`.

Backend (run from `backend/`; the virtualenv is `backend/.venv`):

```
python -m venv .venv ; .venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000    # docs at /docs
.venv\Scripts\python -m pytest -q                                    # all tests
.venv\Scripts\python -m pytest tests/test_ranking.py::test_local_score   # one test
```

Frontend (run from `frontend/`):

```
npm install
npm run dev        # http://localhost:5173, proxies /api to port 8000
npm run test       # Vitest, run mode
npx vitest run src/components/MatchCard.test.tsx -t "labels status"   # one test
npm run build      # tsc type-check + production build
npm run lint       # oxlint
```

Environment variables read by the backend:

- `MONA_AS_OF_DATE` (`YYYY-MM-DD`): pins "today" for deadline checks. Defaults to the current date. Set it for reproducible demos and tests.
- `MONA_DATA_DIR`: overrides the CSV folder. Defaults to `data/` at the repo root.

## Architecture

```
backend/app/
  api/routes.py     HTTP only: query params, filtering, paging, response envelopes
  domain/           pure Python, no file or FastAPI imports
    models.py         BusinessProfile, Grant, LoanOffer, NumericRange, TriState
    results.py        RuleResult, Eligibility, Relevance, Match, compare_minimum, build_eligibility
    grant_eligibility.py / loan_eligibility.py    hard requirements
    ranking.py        relevance scoring for grants and loans
    config.py         every scoring weight and threshold
    matcher.py        runs eligibility + ranking, sorts
  data/             the only place raw CSV rows and column names appear
    loaders.py        CSV -> domain models, with a LoadReport per file
    normalize.py      cell text -> bands, locations, amounts, state rules
    requirements.py   free-text grant criteria -> hard requirements
    mappings.py       states, metro aliases, industry map (plain data)
    repository.py     in-memory store loaded once at startup
frontend/src/
  api/client.ts  types/api.ts  components/  format.ts
```

Dependencies point inward: `api` and `data` import `domain`; `domain` imports neither. Domain models are Pydantic models and are returned directly as API responses, so `frontend/src/types/api.ts` must be updated by hand when they change.

The frontend holds no matching logic. It renders the statuses, scores and reason strings the API returns.

## Matching rules

These were agreed with the project owner. Do not change them without asking.

**Scope (applied at load time)**

- Grant index rows are kept only if `Type of Support` includes Grant, Reimbursement, Award(s) or Pitch Competition. Resources, accelerators, investments, fellowships, scholarships, tax credits and loan-type rows are excluded, as are rows whose amount says there is no cash award.
- Closed rows are dropped. Coming Soon rows are kept but returned in their own bucket, never mixed with actionable results.
- Open rows whose listed date has passed are left out at match time, for fixed **and recurring** ("annually", "monthly") deadlines: a past date is never assumed to have renewed. Only rolling programmes with a past date stay, with a warning.
- Loans come from the loan index. A lender becomes one offer, or one offer per product where the CSV gives per-product minimums (Biz2Credit: MCA and term loans).

**Eligibility and relevance are independent.** `ranking.py` never reads an eligibility result, and eligibility never reads a score. Every match carries both, each with its own explanation.

**Eligibility** is a list of rule results (`pass`, `fail`, `needs_verification`, `not_applicable`), each with a human-readable reason:

- any fail → `ineligible`
- otherwise any needs-verification → `needs_verification`
- otherwise → `likely_eligible`

The top status is "Likely Eligible", never "Eligible": only some requirements can be checked, and every result says so in its warnings.

- **Unknown is not no.** A blank business attribute is `TriState.UNKNOWN` or a `None` band, and produces `needs_verification`.
- **No inferred attributes.** Flags are loaded exactly as recorded. Never derive one from another flag (BIPOC from Black-owned) or from the legal entity type (an LLC is not assumed to be for-profit; the data has an LLC flagged as a nonprofit).
- **Bands versus minimums** (`compare_minimum`): whole band at or above the minimum passes, whole band below fails, a band that straddles it is borderline and needs verification.
- **Free text** (`requirements.py`) is parsed clause by clause for ownership, nonprofit/for-profit and physical-location requirements. Each clause is one of three things, and each requirement quotes its source:
  - a firm rule ("must be 51% woman-owned") or an explicit exclusion ("for-profit businesses are ineligible", which requires the *other* entity type): `strict=True`, so a business that does not meet it fails;
  - an ambiguous statement of who the grant is for ("open to women entrepreneurs", "per veteran entrepreneur", a group word in the programme name, a rule the listing contradicts elsewhere): `strict=False`, which gives Needs Verification and never fails anyone;
  - a preference or incidental mention ("encouraged", "priority", "optional", a funder's or partner's name): nothing.

  One clause can yield several requirements. When a new pattern is unsure, make it ambiguous, not firm.
- **Stated but unevaluated criteria** (`criteria.py`): every clause in the criteria column counts as a requirement unless it is recognisably a "no requirement" statement, a preference, a process note, a sentence about the programme, a general "any small business" line, or something the matcher evaluates. What remains is flagged by topic (revenue, employees, tenure, personal, registration, area, other) and becomes a needs-verification check that quotes the clause. Nothing is interpreted: a revenue cap is never compared with the profile. A blank criteria column, or one holding only process notes, also needs verification. The description column is never used for this, so promotional text cannot downgrade a grant.
- **Likely Eligible therefore means** every clause in the criteria column was evaluated and passed. It is rare for grants by design. Loans are unaffected, because their requirements are structured columns.
- **Industry is a ranking factor, not a filter.** A grant listed only under "Nonprofit" asks a for-profit business to verify; it never fails it.
- **Locations and industries use explicit tables** in `mappings.py`. Grant cities are matched through metro aliases (Brooklyn → NYC). Add to the tables; do not add fuzzy matching.

**Relevance** is a 0–100 sum of weighted components defined in `domain/config.py` (grants: industry, audience, local, timing, use of funds; loans: use of funds, qualification headroom, cost, timing). A test asserts the weights total 100. Results sort by status, then score, then deadline, then name.

## Data notes

- The grant index has no ID column; grants are `G-0001`… by file position, so IDs change if rows are reordered.
- Business revenue and credit score mix bands with raw numbers; a raw number becomes a single-point band.
- Invalid rows are skipped and recorded in the file's `LoadReport`, which `/api/meta` exposes. Scope exclusions are counted separately from skipped rows.

## Testing

- Rule, ranking and normalizer tests use in-memory objects built by `make_business`, `make_grant` and `make_offer` in `backend/tests/conftest.py`.
- Loader and API tests use the small CSVs in `backend/tests/fixtures/`, never the real datasets. The fixture files share the real file names because the loaders look them up by name.
- API tests pin the date by overriding the `get_as_of` dependency.
- A new rule needs pass, fail and missing-data cases. A new free-text pattern needs a case that must match and an incidental mention that must not.
- `backend/tests/test_grant_regressions.py` holds the wording of real grant records that were once misjudged, each checked with a qualifying and a non-qualifying business. Add to it whenever a real record is found to be parsed wrongly.

## Project skills

`.claude/skills/` holds `/analyze`, `/plan`, `/implement`, `/review` and `/verify`. All are invoked explicitly.
