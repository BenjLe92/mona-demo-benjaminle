import pytest

from app.domain import loan_eligibility as le
from app.domain.models import NumericRange
from app.domain.results import EligibilityStatus, Outcome
from tests.conftest import make_business, make_offer


def band(low, high=None):
    return NumericRange(min=low, max=high)


@pytest.mark.parametrize(
    "states, business_state, expected",
    [
        ("All", "ND", Outcome.PASS),
        ("All except ND, NV", "IL", Outcome.PASS),
        ("All except ND, NV", "NV", Outcome.FAIL),
        ("Eligible: Alabama, Illinois, and Wyoming", "IL", Outcome.PASS),
        ("Eligible: Alabama, Illinois, and Wyoming", "NY", Outcome.FAIL),
    ],
)
def test_state_rule(states, business_state, expected):
    business = make_business(state=business_state, state_name=business_state)
    assert le.check_state(business, make_offer(states=states)).outcome is expected


@pytest.mark.parametrize(
    "credit, label, minimum, expected",
    [
        (band(680, 719), "680 - 719", 620, Outcome.PASS),
        (band(720), "720 or above", 650, Outcome.PASS),
        (band(620, 620), "620", 620, Outcome.PASS),
        (band(550, 599), "550 - 599", 620, Outcome.FAIL),
        (band(600, 649), "600 - 649", 620, Outcome.NEEDS_VERIFICATION),
        (None, None, 620, Outcome.NEEDS_VERIFICATION),
    ],
)
def test_credit_score(credit, label, minimum, expected):
    business = make_business(credit_score=credit, credit_score_label=label)
    result = le.check_credit_score(business, make_offer(min_credit_score=minimum))
    assert result.outcome is expected
    assert str(minimum) in result.reason


def test_borderline_credit_reason_says_borderline():
    business = make_business(credit_score=band(600, 649), credit_score_label="600 - 649")
    assert le.check_credit_score(business, make_offer(min_credit_score=620)).reason.startswith("Borderline")


def test_missing_credit_reason_says_not_on_file():
    business = make_business(credit_score=None, credit_score_label=None)
    assert "not on file" in le.check_credit_score(business, make_offer()).reason


def test_no_credit_minimum_is_not_applicable():
    assert le.check_credit_score(make_business(), make_offer(min_credit_score=None)).outcome is Outcome.NOT_APPLICABLE


def test_credit_below_minimum_with_exceptions_needs_verification():
    business = make_business(credit_score=band(550, 599), credit_score_label="550 - 599")
    offer = make_offer(min_credit_score=620, credit_note="some exceptions", credit_flexible=True)
    result = le.check_credit_score(business, offer)
    assert result.outcome is Outcome.NEEDS_VERIFICATION
    assert "some exceptions" in result.reason


def test_credit_note_that_is_not_an_exception_still_fails():
    business = make_business(credit_score=band(600, 639), credit_score_label="600 - 639")
    offer = make_offer(min_credit_score=640, credit_note="ideally 680")
    assert le.check_credit_score(business, offer).outcome is Outcome.FAIL


@pytest.mark.parametrize(
    "revenue, minimum, expected",
    [
        (band(100_000, 249_999), 50_000, Outcome.PASS),
        (band(10_000, 49_999), 50_000, Outcome.FAIL),
        (band(250_000, 499_999), 250_000, Outcome.PASS),
        (band(100_000, 249_999), 150_000, Outcome.NEEDS_VERIFICATION),
        (None, 50_000, Outcome.NEEDS_VERIFICATION),
        (None, 0, Outcome.PASS),  # a $0 minimum passes even when revenue is unknown
        (band(0, 9_999), None, Outcome.NOT_APPLICABLE),
    ],
)
def test_revenue(revenue, minimum, expected):
    business = make_business(revenue=revenue, revenue_label="label" if revenue else None)
    assert le.check_revenue(business, make_offer(min_revenue=minimum)).outcome is expected


def test_revenue_rule_in_prose_needs_verification_and_quotes_it():
    offer = make_offer(min_revenue=None, revenue_rule_text="YoY revenue growth trend for two years")
    result = le.check_revenue(make_business(), offer)
    assert result.outcome is Outcome.NEEDS_VERIFICATION
    assert "YoY revenue growth trend for two years" in result.reason


@pytest.mark.parametrize(
    "years, minimum, expected",
    [
        (band(2, 3.99), 2, Outcome.PASS),
        (band(2, 3.99), 3, Outcome.NEEDS_VERIFICATION),
        (band(1, 1.99), 1.5, Outcome.NEEDS_VERIFICATION),
        (band(0, 0.99), 1, Outcome.FAIL),
        (band(0, 0), 0, Outcome.PASS),
        (band(5), 3, Outcome.PASS),
        (None, 2, Outcome.NEEDS_VERIFICATION),
        (band(0, 0.99), None, Outcome.NOT_APPLICABLE),
    ],
)
def test_years_in_business(years, minimum, expected):
    business = make_business(years_in_business=years, years_in_business_label="label" if years else None)
    assert le.check_years_in_business(business, make_offer(min_years=minimum)).outcome is expected


def test_classify_loan_statuses():
    offer = make_offer()
    assert le.classify_loan(make_business(), offer).status is EligibilityStatus.LIKELY_ELIGIBLE

    unknown_credit = make_business(credit_score=None, credit_score_label=None)
    assert le.classify_loan(unknown_credit, offer).status is EligibilityStatus.NEEDS_VERIFICATION

    low_revenue = make_business(revenue=band(0, 9_999), revenue_label="$0 - $9,999", credit_score=None)
    result = le.classify_loan(low_revenue, offer)
    assert result.status is EligibilityStatus.INELIGIBLE  # a confirmed failure outranks an unknown
    assert "minimum annual revenue" in result.summary


def test_likely_eligible_never_claims_a_guarantee():
    result = le.classify_loan(make_business(), make_offer(limitations=["Lender-level only."]))
    assert "not a guarantee" in result.summary
    assert "Lender-level only." in result.warnings


def test_business_with_no_core_data_gets_verification_not_an_error():
    blank = make_business(credit_score=None, revenue=None, years_in_business=None, funding_uses=[], funding_timing=None)
    assert le.classify_loan(blank, make_offer()).status is EligibilityStatus.NEEDS_VERIFICATION
