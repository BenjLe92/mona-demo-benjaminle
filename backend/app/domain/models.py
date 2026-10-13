"""Normalized domain models. Built by `app.data`; nothing here reads files."""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Literal

from pydantic import BaseModel


class TriState(str, Enum):
    YES = "yes"
    NO = "no"
    UNKNOWN = "unknown"


class NumericRange(BaseModel):
    """Inclusive band. `max=None` means open-ended ("720 or above")."""

    min: float
    max: float | None = None


class BusinessProfile(BaseModel):
    profile_id: str
    city: str
    state: str  # two-letter code
    state_name: str
    # Lower-cased city plus any metro areas it belongs to (e.g. "brooklyn", "nyc").
    locality_keys: list[str]
    industries: list[str]  # canonical labels
    unmapped_industries: list[str]
    industry_label: str | None
    years_in_business: NumericRange | None
    years_in_business_label: str | None
    revenue: NumericRange | None
    revenue_label: str | None
    credit_score: NumericRange | None
    credit_score_label: str | None
    employees: NumericRange | None
    employees_label: str | None
    funding_uses: list[str]
    funding_timing: str | None
    business_type: str | None
    woman_owned: TriState
    black_owned: TriState
    bipoc_owned: TriState
    veteran_owned: TriState
    nonprofit: TriState
    brick_and_mortar: TriState
    unknown_fields: list[str]


class Amount(BaseModel):
    min: float | None = None
    max: float | None = None
    raw: str | None = None


LocationKind = Literal["global", "national", "select_states", "state", "city", "foreign"]


class LocationScope(BaseModel):
    kind: LocationKind
    state: str | None = None
    city: str | None = None
    raw: str


FounderGroup = Literal["woman", "black", "bipoc", "veteran"]
RequirementKind = Literal["founder", "nonprofit", "for_profit", "brick_and_mortar"]


class Requirement(BaseModel):
    """A requirement found in a grant's text, with the wording it came from.

    `strict=False` marks an ambiguous statement: a business that does not match is asked to
    verify, never failed.
    """

    kind: RequirementKind
    groups: list[FounderGroup] = []  # for kind="founder": any one of these satisfies it
    strict: bool = True
    source: str


CriterionTopic = Literal["revenue", "employees", "tenure", "personal", "registration", "area", "other"]


class UncheckedCriterion(BaseModel):
    """A requirement the listing states but the matcher does not evaluate, with its wording."""

    topic: CriterionTopic
    source: str


DeadlineKind = Literal["fixed", "rolling", "recurring", "none"]


class Grant(BaseModel):
    id: str
    name: str
    description: str
    category: Literal["grant", "cash_award", "pitch_competition"]
    support_types: list[str]
    listing_status: Literal["open", "coming_soon"]
    amount: Amount
    deadline: date | None
    deadline_kind: DeadlineKind
    deadline_type_label: str | None
    locations: list[LocationScope]
    location_label: str | None
    industries: list[str]  # canonical labels
    all_industries: bool
    tags: list[str]  # non-industry tokens from the Industry column, e.g. "Nonprofit"
    requirements: list[Requirement]
    unchecked_criteria: list[UncheckedCriterion] = []
    # False when the criteria column is blank or holds only process notes (dates, fees, how to apply).
    criteria_say_who_qualifies: bool = True
    eligibility_text: str
    application_fee: str | None
    url: str


class StateRule(BaseModel):
    mode: Literal["all", "all_except", "only"]
    states: list[str] = []
    raw: str


class LoanOffer(BaseModel):
    """One lender, or one lender product where the dataset gives product-level minimums."""

    id: str
    lender: str
    product_label: str
    products: list[str]
    product_level: bool
    url: str
    state_rule: StateRule
    min_credit_score: int | None
    credit_note: str | None  # e.g. "some exceptions", "ideally 680"
    credit_flexible: bool
    min_revenue: float | None
    revenue_rule_text: str | None  # a requirement the dataset states in prose
    min_years: float | None
    loan_size: Amount
    interest_rates: str | None
    min_interest_rate: float | None
    loan_terms: str | None
    limitations: list[str]
