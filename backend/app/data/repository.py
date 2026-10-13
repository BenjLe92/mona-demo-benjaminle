"""In-memory store, loaded once at startup and injected into routes."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.data import loaders
from app.domain.models import BusinessProfile, Grant, LoanOffer


@dataclass
class Repository:
    businesses: dict[str, BusinessProfile]
    grants: list[Grant]
    offers: list[LoanOffer]
    reports: list[loaders.LoadReport]


def load_repository(data_dir: Path) -> Repository:
    businesses, business_report = loaders.load_businesses(data_dir / loaders.BUSINESS_FILE)
    grants, grant_report = loaders.load_grants(data_dir / loaders.GRANT_FILE)
    offers, loan_report = loaders.load_loans(data_dir / loaders.LOAN_FILE)
    return Repository(
        businesses={b.profile_id: b for b in businesses},
        grants=grants,
        offers=offers,
        reports=[business_report, grant_report, loan_report],
    )
