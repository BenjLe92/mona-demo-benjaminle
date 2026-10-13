"""Criteria a listing states but the matcher cannot evaluate, and their effect on eligibility status."""

import pytest

from app.data.criteria import review_criteria
from app.data.requirements import extract_requirements
from app.domain import grant_eligibility as ge
from app.domain.models import NumericRange, TriState, UncheckedCriterion
from app.domain.ranking import rank_grant
from app.domain.results import EligibilityStatus, Outcome
from tests.conftest import AS_OF, make_business, make_grant

LIKELY = EligibilityStatus.LIKELY_ELIGIBLE
VERIFY = EligibilityStatus.NEEDS_VERIFICATION
INELIGIBLE = EligibilityStatus.INELIGIBLE


def topics(text: str) -> list[str]:
    return [c.topic for c in review_criteria(text)[0]]


def grant_with(criteria: str, description: str = "", name: str = "Test Grant", **overrides):
    """A grant built the way the loader builds one: parsed requirements plus unchecked criteria."""
    unchecked, says_who = review_criteria(criteria)
    return make_grant(
        name=name,
        eligibility_text=criteria,
        description=description,
        requirements=extract_requirements(criteria, description, name),
        unchecked_criteria=unchecked,
        criteria_say_who_qualifies=says_who,
        **overrides,
    )


def status(grant, **business):
    return ge.classify_grant(make_business(**business), grant, AS_OF).status


# --- Detection -------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "Annual revenue must be less than $250,000.",
        "Less than $2M in annual gross revenue",
        "Gross annual revenue $750,000 or less in most recent tax year",
        "Your store earns an average annual revenue under $1M",
        "Annual budget must not exceed $50,000.",
    ],
)
def test_revenue_limits_are_flagged(text):
    assert topics(text) == ["revenue"]


@pytest.mark.parametrize(
    "text",
    ["No more than 50 employees", "Have 50 or fewer employees", "2-100 employees", "Employs fewer than five people full time"],
)
def test_employee_limits_are_flagged(text):
    assert topics(text) == ["employees"]


@pytest.mark.parametrize(
    "text",
    [
        "at least 1 year in business.",
        "Have been in business for at least 12 months prior to January 2020.",
        "Business must be established for a minimum of 6 months",
        "Company must be in business for no less than one year to qualify.",
        "Not be more than five years old.",
        "Operating for more than one year",
    ],
)
def test_tenure_requirements_are_flagged(text):
    assert topics(text) == ["tenure"]


def test_one_clause_can_raise_several_topics_and_each_keeps_its_wording():
    text = "Independently owned business, operating at least 2 years, fewer than 50 full-time employees, annual gross revenue under $2 million."
    unchecked, _ = review_criteria(text)
    assert [c.topic for c in unchecked] == ["revenue", "employees", "tenure"]
    assert all(c.source == text for c in unchecked)


@pytest.mark.parametrize(
    "text, topic",
    [
        ("Applicants must be at least 18 years of age.", "personal"),
        ("Valid City business license with no active violations", "registration"),
        ("Business must sit inside a designated opportunity zone.", "area"),
        ("Must have a goal and vision for business growth and scalability.", "other"),
        ("Excludes cannabis, weapons and adult entertainment.", "other"),
        ("Independent artists'-book publishers with titles planned.", "other"),
    ],
)
def test_other_stated_requirements_are_flagged(text, topic):
    assert topics(text) == [topic]


@pytest.mark.parametrize(
    "text",
    [
        "No minimum revenue, business age, or company size.",
        "Statewide, no county restriction.",
        "Applications are accepted on a rolling basis.",
        "Entry fees: $59 early / $89 standard. All fees non-refundable.",
        "Grant funds may be used to train employees.",
        "Winners announced March 2027.",
        "Priority consideration goes to businesses with fewer than 10 employees.",
        "These grants are designed to help businesses within the City grow and thrive.",
        "Eligibility",
    ],
)
def test_non_requirements_are_not_flagged(text):
    assert review_criteria(text)[0] == []


@pytest.mark.parametrize(
    "text",
    [
        "Any micro or small business owner in the US is eligible.",
        "Any US small business.",
        "Must be at least 51% woman-owned.",
        "Must be a for-profit business.",
        "Your business must be a for-profit business, not a nonprofit.",
        "Business must be located in Detroit.",
    ],
)
def test_clauses_the_matcher_evaluates_are_not_flagged_and_say_who_qualifies(text):
    assert review_criteria(text) == ([], True)


@pytest.mark.parametrize("text", ["", "Applications due October 11, 2026. No application fee.", "Winners announced in March."])
def test_criteria_that_do_not_say_who_qualifies(text):
    assert review_criteria(text) == ([], False)


def test_mention_of_revenue_or_employees_without_a_limit_is_not_a_revenue_or_employee_flag():
    assert "revenue" not in topics("Pre-revenue startups building a product.")
    assert "employees" not in topics("Grant funds may be used to hire employees.")


# --- Effect on eligibility status ---------------------------------------------------


def test_unparsed_revenue_employee_and_tenure_limits_need_verification():
    grant = grant_with("Annual revenue no more than $5 million; 2-100 employees; at least 1 year in business.")
    result = ge.classify_grant(make_business(), grant, AS_OF)
    assert result.status is VERIFY
    by_rule = {c.rule: c for c in result.checks}
    assert set(by_rule) == {"location", "unchecked_revenue", "unchecked_employees", "unchecked_tenure"}
    assert by_rule["location"].outcome is Outcome.PASS
    assert all(by_rule[r].outcome is Outcome.NEEDS_VERIFICATION for r in by_rule if r != "location")
    assert result.summary == (
        "Passed: location. To verify: annual revenue requirement; employee count requirement; time in business requirement."
    )


def test_unchecked_reason_quotes_the_listing_and_shows_the_profile_value():
    check = ge.check_unchecked_criterion(
        make_business(revenue_label="$100,000 - $249,999"),
        UncheckedCriterion(topic="revenue", source="Annual revenue no more than $5 million"),
    )
    assert "Annual revenue no more than $5 million" in check.reason
    assert "Your profile shows: $100,000 - $249,999." in check.reason
    assert "not checked automatically" in check.reason

    missing = ge.check_unchecked_criterion(
        make_business(revenue=None, revenue_label=None),
        UncheckedCriterion(topic="revenue", source="Under $1M in revenue"),
    )
    assert "Your profile shows: not on file." in missing.reason


def test_unchecked_criteria_are_never_treated_as_met_or_failed_from_profile_data():
    """A business far outside a stated cap is still only asked to verify: the cap is not parsed."""
    grant = grant_with("Annual revenue must be less than $250,000.")
    big = dict(revenue=NumericRange(min=1_000_000, max=2_499_999), revenue_label="$1,000,000 - $2,499,999")
    assert status(grant, **big) is VERIFY
    assert status(grant) is VERIFY


def test_confirmed_failure_still_wins_over_unchecked_criteria():
    grant = grant_with("Must be at least 51% woman-owned. No more than 10 employees.")
    assert status(grant, woman_owned=TriState.NO) is INELIGIBLE
    assert status(grant, woman_owned=TriState.YES) is VERIFY
    out_of_area = grant_with("No more than 10 employees.", location="NY")
    assert status(out_of_area) is INELIGIBLE


def test_absent_criteria_need_verification():
    result = ge.classify_grant(make_business(), grant_with(""), AS_OF)
    assert result.status is VERIFY
    assert result.checks[-1].rule == "criteria_not_listed"
    assert "gives no eligibility criteria" in result.checks[-1].reason
    assert result.summary == "Passed: location. To verify: eligibility criteria not listed."


def test_criteria_holding_only_process_notes_need_verification():
    result = ge.classify_grant(make_business(), grant_with("Applications due October 11, 2026. No application fee."), AS_OF)
    assert result.status is VERIFY
    assert "covers how to apply but not who qualifies" in result.checks[-1].reason


def test_promotional_description_alone_does_not_downgrade_a_grant():
    promo = "Our celebrated programme champions bold founders with at least 100 employees worth of ambition."
    grant = grant_with("Any small business owner in the US is eligible.", description=promo)
    assert grant.unchecked_criteria == []
    assert status(grant) is LIKELY


def test_likely_eligible_only_when_everything_stated_was_evaluated():
    fully_checked = grant_with("Must be at least 51% woman-owned. Must be a for-profit business.")
    result = ge.classify_grant(make_business(woman_owned=TriState.YES, nonprofit=TriState.NO), fully_checked, AS_OF)
    assert result.status is LIKELY
    assert result.summary == (
        "Passed: location; ownership: woman-owned; entity type: for-profit business. "
        "Nothing left to verify from the listing. This is not a guarantee of eligibility."
    )
    assert status(fully_checked, woman_owned=TriState.UNKNOWN, nonprofit=TriState.NO) is VERIFY
    assert status(fully_checked, woman_owned=TriState.NO, nonprofit=TriState.NO) is INELIGIBLE


def test_ambiguous_ownership_statement_needs_verification():
    grant = grant_with("All women and minority business owners are eligible.")
    assert grant.unchecked_criteria == []
    assert status(grant, woman_owned=TriState.NO, bipoc_owned=TriState.NO) is VERIFY
    assert status(grant, woman_owned=TriState.UNKNOWN, bipoc_owned=TriState.UNKNOWN) is VERIFY
    assert status(grant, woman_owned=TriState.YES) is LIKELY


def test_relevance_is_unaffected_by_unchecked_criteria():
    business = make_business()
    plain = grant_with("Any small business owner in the US is eligible.")
    capped = grant_with("Annual revenue must be less than $250,000. No more than 5 employees.")
    assert status(plain) is LIKELY and status(capped) is VERIFY
    assert rank_grant(business, plain, AS_OF) == rank_grant(business, capped, AS_OF)


# --- Real records, built as the loader builds them --------------------------------------


def test_g0034_veteran_passes_but_revenue_employee_and_tenure_limits_remain():
    grant = grant_with(
        "U.S. military veteran serving as CEO, President or Business Owner; active U.S.-based business; annual "
        "revenue no more than $5 million; 2-100 employees; at least 1 year in business.",
        name="Stephen L. Tadlock Veteran Business Grant (Founders First CDC)",
    )
    assert [c.topic for c in grant.unchecked_criteria] == ["revenue", "employees", "tenure"]
    result = ge.classify_grant(make_business(veteran_owned=TriState.YES), grant, AS_OF)
    assert result.status is VERIFY
    assert result.summary.startswith("Passed: location; ownership: veteran-owned. To verify: annual revenue requirement;")
    assert status(grant, veteran_owned=TriState.NO) is INELIGIBLE


def test_g0249_veteran_programme_lists_county_tenure_and_course_requirements():
    grant = grant_with(
        "- Grant allocation of up to $2,000 per veteran entrepreneur\n"
        "- Attend and complete mandatory small business education course\n"
        "- Residence and business must be located in Duval County\n"
        "- Business must be established for a minimum of 6 months",
        name="City of Jacksonville Veteran Grant Program",
    )
    assert [c.topic for c in grant.unchecked_criteria] == ["tenure", "personal", "area", "other"]
    assert status(grant, veteran_owned=TriState.YES) is VERIFY
    assert status(grant, veteran_owned=TriState.NO) is VERIFY


def test_g0180_black_owned_rule_is_firm_and_employee_range_is_unchecked():
    grant = grant_with("Qualified applicants must be Black-owned small businesses with 1 to 25 employees.")
    assert [c.topic for c in grant.unchecked_criteria] == ["employees"]
    assert status(grant, black_owned=TriState.YES) is VERIFY
    assert status(grant, black_owned=TriState.NO) is INELIGIBLE
