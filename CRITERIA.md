# Matching criteria

Every rule the matcher applies, taken from the code. Each match gets two things that are worked out separately: an **eligibility status** (can the business apply?) and a **relevance score** (how good a fit is it?). Neither one reads the other.

Sources: `backend/app/domain/grant_eligibility.py`, `loan_eligibility.py`, `ranking.py`, `config.py`, and `backend/app/data/requirements.py` and `criteria.py`.

## 1. Scope (applied when the CSVs load)

| Source | Kept | Dropped |
|---|---|---|
| Grant index, by type | Type of Support includes Grant, Reimbursement, Award(s) or Pitch Competition | Resources, accelerators, investments, fellowships, scholarships, tax credits, loan-type rows, and rows whose amount says there is no cash award |
| Grant index, by status | Open; Coming Soon (returned in a separate bucket, never mixed with actionable results) | Closed |
| Grant deadline (checked at match time) | Future dates; rolling programmes with a past date (kept with a warning) | Past fixed dates **and** past recurring ("annually", "monthly") dates. A past date is never assumed to have renewed. |
| Loan index | One offer per lender, or one offer per product where the CSV gives separate minimums (Biz2Credit: MCA and term loan) | none |

Rows that can't be parsed are skipped and recorded in that file's `LoadReport`, which `/api/meta` shows. Rows excluded by scope are counted separately from skipped rows.

## 2. Grant eligibility checks

| Check | Pass | Fail | Needs verification |
|---|---|---|---|
| **Location** | National or global scope; the business's state; or a listed city that matches the business (through metro aliases such as Brooklyn → NYC) | Limited to other states, or to other cities in the business's state | No location listed; "selected states only" |
| **Ownership** (woman, Black, BIPOC, veteran), read from the criteria text | The profile flag is Yes | Firm rule and the profile flag is No | The flag is blank, or the wording is ambiguous |
| **Entity type** (nonprofit or for-profit), read from the criteria text | The business is that type | Firm rule or explicit exclusion, and the business is the other type | Nonprofit status is not on file, or the wording is ambiguous |
| **Physical location** (brick-and-mortar), read from the criteria text | The business has one | Firm rule and the profile says it has none | Not on file, or the wording is ambiguous |
| **Listed only under "Nonprofit"** (category tag with no stated rule) | none | Never | A business that is not a nonprofit, or whose status is unknown, is asked to confirm |
| **Stated but unevaluated criteria**, by topic: revenue, employees, time in business, personal (age, residency, citizenship), registration or licensing, area or income designation, other | none | Never | Always. The clause is quoted, and for revenue, employees and time in business the profile value is shown next to it. The values are never compared. |
| **No criteria listed**, or the column holds only process notes | none | Never | Always |

### How free-text criteria are read

The criteria column is split into clauses. Each clause is sorted into one of three kinds:

| Kind | Example signals | Effect |
|---|---|---|
| **Firm rule** (`strict=True`) | "must", "required", "only", "at least", "51%", "majority", or an explicit exclusion ("for-profit businesses are ineligible", "not open to …") | A business that doesn't meet it **fails** |
| **Ambiguous** (`strict=False`) | "open to …", "… are eligible", "per veteran entrepreneur", a group word in the programme name, a rule the listing contradicts elsewhere | **Needs verification**, never a fail |
| **Ignored** | Preferences ("encouraged", "priority", "optional"), examples ("such as", "e.g."), third parties (partner, sponsor, "member of"), a funder's name | No requirement |

One clause can produce several requirements. Each requirement quotes the clause it came from. When a new pattern is uncertain, it is treated as ambiguous rather than firm.

These words count as group terms:
- **Woman:** woman/women, female
- **Black:** Black, African American
- **BIPOC:** BIPOC, minority, people of color, Latino/a/x/e, Hispanic, Indigenous, Native American, AAPI, Asian American
- **Veteran:** veteran

The description column is never used to decide eligibility, so promotional text can't downgrade a grant.

## 3. Loan eligibility checks

| Check | Pass | Fail | Needs verification | Not applicable |
|---|---|---|---|---|
| **State** | The lender serves all states, or serves the business's state | The lender does not lend in that state | none | none |
| **Minimum credit score** | The business's whole band is at or above the minimum | The whole band is below it | The band straddles the minimum, or the score is not on file | none |
| **Minimum annual revenue** | Same band logic; also passes when the lender has no minimum and welcomes startups | Same band logic | Same band logic | No minimum is published |
| **Minimum years in business** | Same band logic; also passes when the lender has no minimum | Same band logic | Same band logic | No minimum is published |

Business revenue and credit score mix bands with raw numbers in the data; a raw number is treated as a single-point band.

## 4. Overall status

1. Any **fail** → **Ineligible**
2. Otherwise, any **needs verification** → **Needs Verification**
3. Otherwise → **Likely Eligible**

The top status is never "Eligible". Every result carries a warning that only some requirements could be checked. For a grant, Likely Eligible means every clause in its criteria column was evaluated and passed. That is rare by design.

Principles behind these rules:
- **Unknown is not no.** A blank attribute gives Needs Verification, not a fail.
- **No inferred attributes.** Flags are used exactly as recorded. Black-owned does not imply BIPOC, and an LLC is not assumed to be for-profit.
- **Industry is a ranking factor, not a filter.**

## 5. Relevance score (0–100)

All weights live in `backend/app/domain/config.py`. A test checks that each set of weights adds up to 100.

### Grants

| Component | Max | Points |
|---|---|---|
| Industry fit | 35 | Match 35 · open to all industries 15 · no industry listed 10 · can't compare 5 · mismatch 0 |
| Audience fit | 20 | Targeted group the business belongs to 20 · general audience 8 · unknown 4 · mismatch 0 |
| Local fit | 20 | City 20 · state 15 · multi-state (more than 5 state scopes) 12 · national 10 · selected states 8 · global 6 · none 0 |
| Timing | 15 | Rolling, and the business needs funds within a month 15 · deadline within the 60-day ideal window 15 · rolling 12 · deadline far out 10 · closing within 14 days 8 · unknown 6 · coming soon 5 |
| Use of funds | 10 | Matches a stated use of funds 10 · general 5 · unknown 3 |

Uses of funds are suggested by grant tags. Brick-and-Mortar and Reimbursement suggest expansion, renovation, real estate and equipment. Startup suggests business launch.

### Loans

| Component | Max | Points |
|---|---|---|
| Use of funds fit | 40 | Full points when the product serves the business's stated uses; 37.5% of the weight when the uses are not on file |
| Qualification headroom | 25 | Clear 100% · borderline 50% · unknown 33% · below the minimum 0% |
| Cost | 20 | Zero interest 20 · rate ≤ 7% 16 · rate ≤ 10% 12 · higher 8 · rate not published 8 |
| Timing | 15 | MCA or line of credit, and funds are needed within 2 weeks 15 · funds needed within a month 12 · otherwise 8 |

Which uses each product serves:

| Product | Uses |
|---|---|
| Term loan | Payroll, marketing, inventory, equipment, expansion, launch, refinancing |
| SBA 7(a) | Refinancing, equipment, expansion, commercial real estate |
| Line of credit / MCA | Inventory, payroll, marketing |
| Purchase order | Inventory |
| Commercial real estate | Real estate, expansion |
| Truck | Vehicles |

## 6. Sort order

Results sort by status (Likely Eligible, then Needs Verification, then Ineligible), then by score (highest first), then by deadline (soonest first), then by name.
