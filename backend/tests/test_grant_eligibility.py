from datetime import date

import pytest

from app.domain import grant_eligibility as ge
from app.domain.models import Requirement, TriState
from app.domain.results import EligibilityStatus, Outcome
from tests.conftest import AS_OF, make_business, make_grant


@pytest.mark.parametrize(
    "location, expected",
    [
        ("US", Outcome.PASS),
        ("Global", Outcome.PASS),
        ("US,Canada", Outcome.PASS),
        ("IL", Outcome.PASS),
        ("IL (Chicago)", Outcome.PASS),
        ("NY,IL (Chicago)", Outcome.PASS),
        ("DMV", Outcome.FAIL),
        ("NY", Outcome.FAIL),
        ("NY (NYC)", Outcome.FAIL),
        ("IL (Decatur)", Outcome.FAIL),
        ("Canada", Outcome.FAIL),
        ("US (select states)", Outcome.NEEDS_VERIFICATION),
        ("", Outcome.NEEDS_VERIFICATION),
    ],
)
def test_location_for_chicago_business(location, expected):
    assert ge.check_location(make_business(), make_grant(location=location)).outcome is expected


def test_borough_matches_metro_grant():
    brooklyn = make_business(city="Brooklyn", state="NY", state_name="New York", locality_keys=["brooklyn", "nyc"])
    assert ge.check_location(brooklyn, make_grant(location="NY (NYC)")).outcome is Outcome.PASS
    assert ge.check_location(brooklyn, make_grant(location="NY (Buffalo)")).outcome is Outcome.FAIL


def test_suburb_does_not_match_named_city_and_reason_names_both():
    naperville = make_business(city="Naperville", locality_keys=["naperville"])
    result = ge.check_location(naperville, make_grant(location="IL (Chicago)"))
    assert result.outcome is Outcome.FAIL
    assert "Chicago" in result.reason and "Naperville" in result.reason


def founder(*groups):
    return Requirement(kind="founder", groups=list(groups), source="Must be owned by the named group.")


@pytest.mark.parametrize(
    "flag, expected",
    [(TriState.YES, Outcome.PASS), (TriState.NO, Outcome.FAIL), (TriState.UNKNOWN, Outcome.NEEDS_VERIFICATION)],
)
def test_founder_requirement_single_group(flag, expected):
    result = ge.check_founder_requirement(make_business(woman_owned=flag), founder("woman"))
    assert result.outcome is expected
    assert "Must be owned by the named group." in result.reason  # quotes its source


def test_founder_requirement_any_of():
    requirement = founder("woman", "veteran")
    yes_on_one = make_business(woman_owned=TriState.NO, veteran_owned=TriState.YES)
    no_and_unknown = make_business(woman_owned=TriState.NO, veteran_owned=TriState.UNKNOWN)
    no_on_all = make_business(woman_owned=TriState.NO, veteran_owned=TriState.NO)
    assert ge.check_founder_requirement(yes_on_one, requirement).outcome is Outcome.PASS
    assert ge.check_founder_requirement(no_and_unknown, requirement).outcome is Outcome.NEEDS_VERIFICATION
    assert ge.check_founder_requirement(no_on_all, requirement).outcome is Outcome.FAIL


@pytest.mark.parametrize(
    "kind, nonprofit, expected",
    [
        ("nonprofit", TriState.YES, Outcome.PASS),
        ("nonprofit", TriState.NO, Outcome.FAIL),
        ("nonprofit", TriState.UNKNOWN, Outcome.NEEDS_VERIFICATION),
        ("for_profit", TriState.NO, Outcome.PASS),
        ("for_profit", TriState.YES, Outcome.FAIL),
        ("for_profit", TriState.UNKNOWN, Outcome.NEEDS_VERIFICATION),
    ],
)
def test_entity_requirement(kind, nonprofit, expected):
    requirement = Requirement(kind=kind, source="Stated rule.")
    assert ge.check_entity_requirement(make_business(nonprofit=nonprofit), requirement).outcome is expected


@pytest.mark.parametrize(
    "flag, expected",
    [(TriState.YES, Outcome.PASS), (TriState.NO, Outcome.FAIL), (TriState.UNKNOWN, Outcome.NEEDS_VERIFICATION)],
)
def test_brick_and_mortar_requirement(flag, expected):
    requirement = Requirement(kind="brick_and_mortar", source="Must have a storefront.")
    assert ge.check_brick_and_mortar(make_business(brick_and_mortar=flag), requirement).outcome is expected


def test_nonprofit_listing_asks_for_profit_business_to_verify_but_never_fails():
    listed = make_grant(tags=["Nonprofit"], all_industries=False)
    assert ge.check_nonprofit_listing(make_business(nonprofit=TriState.NO), listed).outcome is Outcome.NEEDS_VERIFICATION
    assert ge.check_nonprofit_listing(make_business(nonprofit=TriState.UNKNOWN), listed).outcome is Outcome.NEEDS_VERIFICATION
    assert ge.check_nonprofit_listing(make_business(nonprofit=TriState.YES), listed) is None


def test_nonprofit_tag_alongside_industries_is_not_a_check():
    mixed = make_grant(tags=["Nonprofit"], industries=["Technology"], all_industries=False)
    assert ge.check_nonprofit_listing(make_business(), mixed) is None
    assert ge.check_nonprofit_listing(make_business(), make_grant(tags=["Nonprofit"], all_industries=True)) is None


@pytest.mark.parametrize(
    "deadline, deadline_type, expired",
    [
        (date(2026, 10, 12), None, True),
        (date(2026, 10, 13), None, False),  # closes today: still open
        (date(2026, 11, 1), None, False),
        (date(2026, 9, 1), "rolling", False),
        (date(2026, 9, 1), "annually", False),
        (None, "rolling", False),
        (None, None, False),
    ],
)
def test_is_expired(deadline, deadline_type, expired):
    assert ge.is_expired(make_grant(deadline=deadline, deadline_type=deadline_type), AS_OF) is expired


def test_classify_grant_statuses(as_of):
    business = make_business(woman_owned=TriState.UNKNOWN)
    assert ge.classify_grant(business, make_grant(), as_of).status is EligibilityStatus.LIKELY_ELIGIBLE
    assert ge.classify_grant(business, make_grant(requirements=[founder("woman")]), as_of).status is EligibilityStatus.NEEDS_VERIFICATION
    out_of_state = make_grant(location="NY", requirements=[founder("woman")])
    assert ge.classify_grant(business, out_of_state, as_of).status is EligibilityStatus.INELIGIBLE


def test_industry_mismatch_does_not_affect_eligibility(as_of):
    film_grant = make_grant(industries=["Film & Media"], all_industries=False)
    assert ge.classify_grant(make_business(), film_grant, as_of).status is EligibilityStatus.LIKELY_ELIGIBLE


def test_every_grant_warns_that_checks_are_partial(as_of):
    result = ge.classify_grant(make_business(), make_grant(), as_of)
    assert ge.UNCHECKED_CRITERIA_WARNING in result.warnings
    assert "not a guarantee" in result.summary


def test_stale_recurring_date_and_coming_soon_produce_warnings(as_of):
    stale = make_grant(deadline=date(2026, 9, 1), deadline_type="annually")
    assert any("has passed" in w for w in ge.classify_grant(make_business(), stale, as_of).warnings)
    upcoming = make_grant(listing_status="coming_soon")
    assert "Applications are not open yet." in ge.classify_grant(make_business(), upcoming, as_of).warnings
