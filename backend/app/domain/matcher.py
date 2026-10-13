"""Combine eligibility and relevance into ordered matches for one business."""

from __future__ import annotations

from datetime import date

from app.domain.grant_eligibility import classify_grant, is_expired
from app.domain.loan_eligibility import classify_loan
from app.domain.models import BusinessProfile, Grant, LoanOffer
from app.domain.ranking import rank_grant, rank_loan
from app.domain.results import DeadlineInfo, EligibilityStatus, Match

_STATUS_ORDER = {
    EligibilityStatus.LIKELY_ELIGIBLE: 0,
    EligibilityStatus.NEEDS_VERIFICATION: 1,
    EligibilityStatus.INELIGIBLE: 2,
}


def _deadline_info(grant: Grant, as_of: date) -> DeadlineInfo:
    if grant.deadline_kind == "rolling":
        label = "Rolling"
    elif grant.deadline and grant.deadline >= as_of:
        label = f"{grant.deadline:%b %d, %Y}"
        if grant.deadline_kind == "recurring":
            label += f" ({grant.deadline_type_label})"
    elif grant.deadline_kind == "recurring":
        label = f"Recurring ({grant.deadline_type_label}); next date not listed"
    else:
        label = "No deadline listed"
    return DeadlineInfo(date=grant.deadline, kind=grant.deadline_kind, label=label)


def match_grant(business: BusinessProfile, grant: Grant, as_of: date) -> Match:
    details = {"Location": grant.location_label, "Support": ", ".join(grant.support_types), "Application fee": grant.application_fee}
    return Match(
        opportunity_id=grant.id,
        kind="grant",
        category=grant.category,
        listing_status=grant.listing_status,
        name=grant.name,
        provider=None,
        amount=grant.amount,
        deadline=_deadline_info(grant, as_of),
        url=grant.url,
        eligibility=classify_grant(business, grant, as_of),
        relevance=rank_grant(business, grant, as_of),
        details={k: v for k, v in details.items() if v},
        limitations=[],
        description=grant.description or None,
        criteria_text=grant.eligibility_text or None,
    )


def match_loan(business: BusinessProfile, offer: LoanOffer) -> Match:
    details = {"Products": "; ".join(offer.products), "Interest rates": offer.interest_rates, "Loan terms": offer.loan_terms}
    return Match(
        opportunity_id=offer.id,
        kind="loan",
        category="loan",
        listing_status="open",
        name=f"{offer.lender} — {offer.product_label}" if offer.product_level else offer.lender,
        provider=offer.lender,
        amount=offer.loan_size,
        deadline=None,
        url=offer.url,
        eligibility=classify_loan(business, offer),
        relevance=rank_loan(business, offer),
        details={k: v for k, v in details.items() if v},
        limitations=offer.limitations,
        description=None,
        criteria_text=None,
    )


def sort_key(match: Match) -> tuple:
    """Status first, then score, then earliest deadline, then name: fully deterministic."""
    deadline = match.deadline.date if match.deadline and match.deadline.date else date.max
    return (_STATUS_ORDER[match.eligibility.status], -match.relevance.score, deadline, match.name.lower(), match.opportunity_id)


def match_business(business: BusinessProfile, grants: list[Grant], offers: list[LoanOffer], as_of: date) -> list[Match]:
    """All in-scope matches for a business, including ineligible ones, best first.

    Grants whose fixed deadline has passed are left out entirely.
    """
    matches = [match_grant(business, g, as_of) for g in grants if not is_expired(g, as_of)]
    matches += [match_loan(business, o) for o in offers]
    return sorted(matches, key=sort_key)
