"""Regression tests built from the wording of real grant-index records that were once misjudged.

Each case parses the record's own text, then classifies a qualifying and a non-qualifying
business. All businesses here are located where the grant is available, so only the
ownership and entity checks decide the status.
"""

from datetime import date

from app.data.requirements import extract_requirements
from app.domain.grant_eligibility import classify_grant, is_expired
from app.domain.models import TriState
from app.domain.results import EligibilityStatus, Outcome
from tests.conftest import AS_OF, make_business, make_grant

LIKELY = EligibilityStatus.LIKELY_ELIGIBLE
VERIFY = EligibilityStatus.NEEDS_VERIFICATION
INELIGIBLE = EligibilityStatus.INELIGIBLE

YES, NO, UNKNOWN = TriState.YES, TriState.NO, TriState.UNKNOWN


def grant_from(name: str, criteria: str, description: str = "", **overrides):
    requirements = extract_requirements(criteria, description, name)
    return make_grant(name=name, eligibility_text=criteria, description=description, requirements=requirements, **overrides)


def business(**flags):
    """A business with every ownership and entity flag set to "no" unless overridden."""
    values = dict(woman_owned=NO, black_owned=NO, bipoc_owned=NO, veteran_owned=NO, nonprofit=NO)
    values.update(flags)
    return make_business(**values)


def status(grant, **flags):
    return classify_grant(business(**flags), grant, AS_OF).status


def parsed(grant):
    return [(r.kind, r.groups, r.strict) for r in grant.requirements]


def test_g0020_ineligible_list_does_not_become_a_for_profit_requirement():
    grant = grant_from(
        "Whole Foods Market Store Giving",
        "NONPROFITS ONLY. Eligible: registered US 501(c)(3) nonprofits, Canadian charitable organizations, and UK "
        "charitable incorporated organizations, all of which must demonstrate verified nonprofit status. INELIGIBLE: "
        "individuals, for-profit businesses, political entities, and organizations that discriminate based on race, "
        "ethnicity, or culture. Support goes to communities surrounding Whole Foods Market stores.",
        "Whole Foods Market's store-level giving program, which funds nonprofits working on food access.",
    )
    assert parsed(grant) == [("nonprofit", [], True)]
    assert status(grant, nonprofit=YES) is LIKELY
    assert status(grant, nonprofit=NO) is INELIGIBLE
    assert status(grant, nonprofit=UNKNOWN) is VERIFY


def test_g0053_must_have_a_woman_founder():
    grant = grant_from(
        "Entreprenista 100 Awards",
        "Open to private for-profit or nonprofit business owners who are legal residents of the United States or "
        "Canada (excluding Quebec), age 18+. The business must have a woman founder or at least one active woman "
        "co-founder involved in operations. No minimum revenue, business age, or company size.",
        "Annual awards program from Entreprenista honoring 100 women founders across all stages.",
    )
    assert parsed(grant) == [("founder", ["woman"], True)]  # and no entity rule: both types are admitted
    assert status(grant, woman_owned=YES) is LIKELY
    assert status(grant, woman_owned=YES, nonprofit=YES) is LIKELY
    assert status(grant, woman_owned=NO) is INELIGIBLE
    assert status(grant, woman_owned=UNKNOWN) is VERIFY


def test_g0249_veteran_programme_without_a_stated_rule_needs_verification():
    grant = grant_from(
        "City of Jacksonville Veteran Grant Program",
        "- Grant allocation of up to $2,000 per veteran entrepreneur\n"
        "- Attend and complete mandatory small business education course\n"
        "- Residence and business must be located in Duval County\n"
        "- Business must be established for a minimum of 6 months",
        "The City of Jacksonville’s Veteran Grant Program offers up to $2,000 per eligible veteran entrepreneur in "
        "Duval County to support business development through tangible asset purchases.",
    )
    assert parsed(grant) == [("founder", ["veteran"], False)]
    assert status(grant, veteran_owned=YES) is LIKELY
    assert status(grant, veteran_owned=NO) is VERIFY  # suggested, not stated: never Likely Eligible, never failed
    assert status(grant, veteran_owned=UNKNOWN) is VERIFY


def test_g0034_veteran_serving_as_ceo_or_owner():
    grant = grant_from(
        "Stephen L. Tadlock Veteran Business Grant (Founders First CDC)",
        "U.S. military veteran serving as CEO, President or Business Owner; active U.S.-based business; annual "
        "revenue no more than $5 million; 2-100 employees; at least 1 year in business.",
        "Founders First CDC awards this grant in memory of U.S. Navy veteran Stephen L. Tadlock.",
    )
    assert parsed(grant) == [("founder", ["veteran"], True)]
    assert status(grant, veteran_owned=YES) is LIKELY
    assert status(grant, veteran_owned=NO) is INELIGIBLE
    assert status(grant, veteran_owned=UNKNOWN) is VERIFY


def test_g0076_women_and_minority_owners_are_eligible():
    grant = grant_from(
        "Galaxy Grant",
        "All women and minority business owners are eligible.",
        "Offers a $2,500 grant open to women and minority entrepreneurs to help build and grow their small "
        "businesses. Provided by Hidden Star, a nonprofit dedicated to supporting underrepresented business owners.",
    )
    # Says who is eligible without excluding anyone else: ambiguous, and no entity rule from the funder's own status.
    assert parsed(grant) == [("founder", ["woman", "bipoc"], False)]
    assert status(grant, woman_owned=YES) is LIKELY
    assert status(grant, bipoc_owned=YES) is LIKELY
    assert status(grant) is VERIFY
    assert status(grant, woman_owned=UNKNOWN, bipoc_owned=UNKNOWN) is VERIFY


def test_g0051_nonprofit_lead_applicant_with_for_profit_collaborators():
    grant = grant_from(
        "Humanity AI Open Call for Grants",
        "Nonprofits only as lead applicant — must be a U.S.-based 501(c)(3). Individuals must apply through a fiscal "
        "sponsor or in collaboration with a 501(c)(3). FOR-PROFITS MAY PARTICIPATE IN COLLABORATIONS BUT CANNOT BE "
        "THE LEAD APPLICANT. Work must serve U.S.-based communities.",
    )
    assert parsed(grant) == [("nonprofit", [], False)]
    assert status(grant, nonprofit=YES) is LIKELY
    assert status(grant, nonprofit=NO) is VERIFY  # a route exists for for-profits, so not a confirmed failure
    assert status(grant, nonprofit=UNKNOWN) is VERIFY


def test_g0001_for_profit_and_woman_owned_in_one_clause():
    grant = grant_from(
        "WomanUp & Pitch (Michigan Women Forward)",
        "Michigan-based for-profit business, at least 51% woman-owned. Excludes cannabis, weapons and adult "
        "entertainment. Previous non-winning finalists may reapply after one year.",
        "Eligibility: a Michigan-based for-profit business that is at least 51% woman-owned; cannabis, weapons and "
        "adult entertainment businesses are excluded.",
    )
    assert parsed(grant) == [("founder", ["woman"], True), ("for_profit", [], True)]
    assert status(grant, woman_owned=YES, nonprofit=NO) is LIKELY
    assert status(grant, woman_owned=YES, nonprofit=YES) is INELIGIBLE
    assert status(grant, woman_owned=NO, nonprofit=NO) is INELIGIBLE
    assert status(grant, woman_owned=YES, nonprofit=UNKNOWN) is VERIFY

    checks = classify_grant(business(woman_owned=YES, nonprofit=YES), grant, AS_OF).checks
    assert {c.rule: c.outcome for c in checks} == {
        "location": Outcome.PASS,
        "founder_requirement": Outcome.PASS,
        "entity_requirement": Outcome.FAIL,
    }


def test_g0078_woman_owned_is_firm_but_for_profit_is_contradicted_by_the_description():
    grant = grant_from(
        "YippityDoo Big Idea Grant",
        "- For-Profit Women Entrepreneurs/Small Business Owners, Women Owned Businesses that are at least 50% owned "
        "and run by a woman.\n- Ages 18 or over, within the United States.\n"
        "- Your business can already be started or in idea stage",
        "Awards two $1,000 grants each month - one to a for-profit and one to a nonprofit women-owned business.",
    )
    assert parsed(grant) == [("founder", ["woman"], True), ("for_profit", [], False)]
    assert status(grant, woman_owned=YES, nonprofit=NO) is LIKELY
    assert status(grant, woman_owned=YES, nonprofit=YES) is VERIFY  # the description funds nonprofits too
    assert status(grant, woman_owned=NO, nonprofit=NO) is INELIGIBLE


def test_ambiguous_statement_reason_says_it_is_not_a_firm_rule():
    grant = grant_from("Galaxy Grant", "All women and minority business owners are eligible.")
    [location, ownership] = classify_grant(business(), grant, AS_OF).checks
    assert ownership.outcome is Outcome.NEEDS_VERIFICATION
    assert "does not state it as a firm rule" in ownership.reason
    assert "All women and minority business owners are eligible." in ownership.reason


def test_recurring_grant_with_a_past_date_is_not_served():
    """G-0001 lists 10/4/2026 with type "annually"; as of 10/13 nothing shows it has reopened."""
    grant = make_grant(deadline=date(2026, 10, 4), deadline_type="annually")
    assert grant.deadline_kind == "recurring"
    assert is_expired(grant, AS_OF) is True
    assert is_expired(grant, date(2026, 10, 4)) is False
