from datetime import date
from pathlib import Path

import pytest

from app.data import normalize as n
from app.domain.models import (
    Amount,
    BusinessProfile,
    Grant,
    LoanOffer,
    NumericRange,
    StateRule,
    TriState,
)

FIXTURES = Path(__file__).parent / "fixtures"
AS_OF = date(2026, 10, 13)


def make_business(**overrides) -> BusinessProfile:
    values = dict(
        profile_id="MONA-TEST",
        city="Chicago",
        state="IL",
        state_name="Illinois",
        locality_keys=["chicago"],
        industries=["Food & Beverage"],
        unmapped_industries=[],
        industry_label="Food & Beverage",
        years_in_business=NumericRange(min=2, max=3.99),
        years_in_business_label="2-3 years",
        revenue=NumericRange(min=100_000, max=249_999),
        revenue_label="$100,000 - $249,999",
        credit_score=NumericRange(min=680, max=719),
        credit_score_label="680 - 719",
        employees=NumericRange(min=2, max=5),
        employees_label="2 to 5 employees",
        funding_uses=["Inventory", "Hiring and payroll"],
        funding_timing="Within a month",
        business_type="Limited Liability Company (LLC)",
        woman_owned=TriState.YES,
        black_owned=TriState.NO,
        bipoc_owned=TriState.NO,
        veteran_owned=TriState.NO,
        nonprofit=TriState.NO,
        brick_and_mortar=TriState.YES,
        unknown_fields=[],
    )
    values.update(overrides)
    return BusinessProfile(**values)


def make_grant(**overrides) -> Grant:
    location = overrides.pop("location", "US")
    deadline = overrides.pop("deadline", date(2026, 11, 15))
    deadline_type = overrides.pop("deadline_type", None)
    values = dict(
        id="G-0001",
        name="Test Grant",
        description="",
        category="grant",
        support_types=["Grant"],
        listing_status="open",
        amount=Amount(max=5000, raw="up to $5,000"),
        deadline=deadline,
        deadline_kind=n.deadline_kind(deadline, deadline_type),
        deadline_type_label=deadline_type,
        locations=n.parse_grant_locations(location),
        location_label=location or None,
        industries=[],
        all_industries=True,
        tags=[],
        requirements=[],
        eligibility_text="",
        application_fee=None,
        url="https://example.org/grant",
    )
    values.update(overrides)
    return Grant(**values)


def make_offer(**overrides) -> LoanOffer:
    states = overrides.pop("states", "All")
    values = dict(
        id="L-test",
        lender="Test Lender",
        product_label="All listed products",
        products=["Term loans"],
        product_level=False,
        url="https://example.org/loan",
        state_rule=n.parse_state_rule(states),
        min_credit_score=620,
        credit_note=None,
        credit_flexible=False,
        min_revenue=50_000,
        revenue_rule_text=None,
        min_years=1,
        loan_size=Amount(min=5000, max=250_000, raw="$5k - $250k"),
        interest_rates="8% to 12%",
        min_interest_rate=8.0,
        loan_terms="12 to 36 months",
        limitations=[],
    )
    values.update(overrides)
    return LoanOffer(**values)


@pytest.fixture
def as_of() -> date:
    return AS_OF
