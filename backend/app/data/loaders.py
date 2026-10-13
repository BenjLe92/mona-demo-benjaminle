"""Read the three CSVs into domain models. Invalid rows are skipped and reported, never dropped silently."""

from __future__ import annotations

import csv
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

from app.data import mappings
from app.data import normalize as n
from app.data.requirements import extract_requirements
from app.domain.models import BusinessProfile, Grant, LoanOffer, TriState

logger = logging.getLogger(__name__)

BUSINESS_FILE = "Mona Anonymized Sample of Small Businesses.csv"
GRANT_FILE = "Mona Grant Index - Oct 2026.csv"
LOAN_FILE = "Mona Loan Index - Oct 2026.csv"


@dataclass
class LoadReport:
    file: str
    rows: int = 0
    loaded: int = 0
    skipped: list[str] = field(default_factory=list)  # "row N: reason"
    excluded: dict[str, int] = field(default_factory=dict)  # deliberate scope exclusions

    def skip(self, row_number: int, reason: str) -> None:
        self.skipped.append(f"row {row_number}: {reason}")
        logger.warning("%s row %d skipped: %s", self.file, row_number, reason)

    def exclude(self, reason: str) -> None:
        self.excluded[reason] = self.excluded.get(reason, 0) + 1


def _read(path: Path, required: set[str]) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{path.name} is missing columns: {sorted(missing)}")
        return list(reader)


# --- Businesses -------------------------------------------------------------

_BUSINESS_COLUMNS = {
    "profile_id", "city", "state", "industry", "time_in_business", "annual_revenue_usd_or_range",
    "credit_score_or_range", "funding_uses", "funding_timing", "business_type",
    "employee_count_or_range", "woman_founder_eligibility", "black_founder_eligibility",
    "bipoc_founder_eligibility", "veteran_founder_eligibility", "nonprofit_eligibility",
    "brick_and_mortar_eligibility",
}


def _nonprofit_state(flag: TriState, business_type: str | None) -> TriState:
    """The explicit flag wins; otherwise the legal entity type decides."""
    if flag is not TriState.UNKNOWN:
        return flag
    entity = mappings.ENTITY_TYPES.get(business_type or "")
    if entity == "nonprofit":
        return TriState.YES
    if entity == "for_profit":
        return TriState.NO
    return TriState.UNKNOWN


def build_business(row: dict[str, str]) -> BusinessProfile:
    """Raises ValueError when the row cannot identify or locate a business."""
    profile_id = n.clean(row["profile_id"])
    if not profile_id:
        raise ValueError("missing profile_id")
    state = n.state_code(row["state"])
    if not state:
        raise ValueError(f"unrecognised state {row['state']!r}")
    city = n.normalize_city(row["city"])
    industries, unmapped = n.map_business_industries(row["industry"])

    raw_type = n.clean(row["business_type"]) or None
    business_type = raw_type if raw_type in mappings.ENTITY_TYPES else None

    black = n.parse_flag(row["black_founder_eligibility"])
    bipoc = n.parse_flag(row["bipoc_founder_eligibility"])
    if bipoc is TriState.UNKNOWN and black is TriState.YES:
        bipoc = TriState.YES  # a Black-owned business is BIPOC-owned

    profile = BusinessProfile(
        profile_id=profile_id,
        city=city,
        state=state,
        state_name=mappings.STATE_NAMES[state],
        locality_keys=n.locality_keys(state, city),
        industries=industries,
        unmapped_industries=unmapped,
        industry_label=n.clean(row["industry"]) or None,
        years_in_business=n.parse_time_in_business(row["time_in_business"]),
        years_in_business_label=n.clean(row["time_in_business"]) or None,
        revenue=n.parse_band(row["annual_revenue_usd_or_range"]),
        revenue_label=n.clean(row["annual_revenue_usd_or_range"]) or None,
        credit_score=n.parse_band(row["credit_score_or_range"]),
        credit_score_label=n.clean(row["credit_score_or_range"]) or None,
        employees=n.parse_band(row["employee_count_or_range"]),
        employees_label=n.clean(row["employee_count_or_range"]) or None,
        funding_uses=n.split_list(row["funding_uses"], ";"),
        funding_timing=n.clean(row["funding_timing"]) or None,
        business_type=business_type,
        woman_owned=n.parse_flag(row["woman_founder_eligibility"]),
        black_owned=black,
        bipoc_owned=bipoc,
        veteran_owned=n.parse_flag(row["veteran_founder_eligibility"]),
        nonprofit=_nonprofit_state(n.parse_flag(row["nonprofit_eligibility"]), business_type),
        brick_and_mortar=n.parse_flag(row["brick_and_mortar_eligibility"]),
        unknown_fields=[],
    )
    checks = {
        "Industry": profile.industry_label,
        "Time in business": profile.years_in_business,
        "Annual revenue": profile.revenue,
        "Credit score": profile.credit_score,
        "Employees": profile.employees,
        "Funding uses": profile.funding_uses,
        "Funding timing": profile.funding_timing,
        "Business type": profile.business_type,
    }
    flags = {
        "Woman-owned": profile.woman_owned,
        "Black-owned": profile.black_owned,
        "BIPOC-owned": profile.bipoc_owned,
        "Veteran-owned": profile.veteran_owned,
        "Nonprofit status": profile.nonprofit,
        "Brick-and-mortar": profile.brick_and_mortar,
    }
    profile.unknown_fields = [name for name, value in checks.items() if not value] + [
        name for name, value in flags.items() if value is TriState.UNKNOWN
    ]
    return profile


def load_businesses(path: Path) -> tuple[list[BusinessProfile], LoadReport]:
    report = LoadReport(file=path.name)
    profiles: list[BusinessProfile] = []
    seen: set[str] = set()
    for number, row in enumerate(_read(path, _BUSINESS_COLUMNS), start=2):
        report.rows += 1
        try:
            profile = build_business(row)
        except ValueError as error:
            report.skip(number, str(error))
            continue
        if profile.profile_id in seen:
            report.skip(number, f"duplicate profile_id {profile.profile_id}")
            continue
        seen.add(profile.profile_id)
        profiles.append(profile)
    report.loaded = len(profiles)
    return profiles, report


# --- Grants -----------------------------------------------------------------

_GRANT_COLUMNS = {
    "Name", "Description", "Amount", "Deadline", "Deadline Type", "Location", "Type of Support",
    "Website / Application Link", "Eligibility Criteria / Additional Info", "Application Status",
    "Industry", "Application Fee",
}
_LISTING_STATUS = {"open": "open", "coming soon": "coming_soon"}


def _category(support_types: list[str]) -> str:
    if "Grant" in support_types or "Reimbursement" in support_types:
        return "grant"
    if "Award" in support_types or "Awards" in support_types:
        return "cash_award"
    return "pitch_competition"


def load_grants(path: Path) -> tuple[list[Grant], LoadReport]:
    """Keep Open and Coming Soon rows that offer a grant, cash award or pitch competition."""
    report = LoadReport(file=path.name)
    grants: list[Grant] = []
    for index, row in enumerate(_read(path, _GRANT_COLUMNS), start=1):
        report.rows += 1
        name = n.clean(row["Name"])
        url = n.clean(row["Website / Application Link"])
        if not name or not url:
            report.skip(index + 1, "missing name or link")
            continue
        status = _LISTING_STATUS.get(n.clean(row["Application Status"]).lower())
        if status is None:
            report.exclude("closed")
            continue
        support_types = n.split_list(row["Type of Support"], ",")
        if not mappings.IN_SCOPE_SUPPORT.intersection(support_types):
            report.exclude("support type out of scope")
            continue
        if n.is_non_cash(row["Amount"]):
            report.exclude("no cash award")
            continue

        deadline_text = n.clean(row["Deadline"])
        deadline = n.parse_date(deadline_text)
        if deadline_text and deadline is None:
            report.skip(index + 1, f"unparseable deadline {deadline_text!r}")
            continue
        description = n.clean_long_text(row["Description"])
        eligibility_text = n.clean_long_text(row["Eligibility Criteria / Additional Info"])
        industries, tags, is_all = n.split_grant_industries(row["Industry"])
        grants.append(
            Grant(
                id=f"G-{index:04d}",
                name=name,
                description=description,
                category=_category(support_types),
                support_types=support_types,
                listing_status=status,
                amount=n.parse_amount(row["Amount"]),
                deadline=deadline,
                deadline_kind=n.deadline_kind(deadline, row["Deadline Type"]),
                deadline_type_label=n.clean(row["Deadline Type"]) or None,
                locations=n.parse_grant_locations(row["Location"]),
                location_label=n.clean(row["Location"]) or None,
                industries=industries,
                all_industries=is_all,
                tags=tags,
                requirements=extract_requirements(eligibility_text, description),
                eligibility_text=eligibility_text,
                application_fee=n.clean(row["Application Fee"]) or None,
                url=url,
            )
        )
    report.loaded = len(grants)
    return grants, report


# --- Loans ------------------------------------------------------------------

_LOAN_COLUMNS = {
    "Lender", "Products", "Referral Link", "Eligible States", "Min credit score",
    "Min annual revenue", "Min years in business", "Loan sizes", "Interest rates", "Loan terms",
}
LENDER_LEVEL_NOTE = "Requirements are published for the lender as a whole, not for each product."


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def build_loan_offers(row: dict[str, str]) -> list[LoanOffer]:
    """One offer per lender, or one per product when minimums are given per product."""
    lender = n.clean(row["Lender"])
    url = n.clean(row["Referral Link"])
    if not lender or not url:
        raise ValueError("missing lender or referral link")
    products = n.split_list(row["Products"], ";")
    revenue, revenue_note = n.parse_leading_number(row["Min annual revenue"])
    rates = n.clean(row["Interest rates"]) or None
    shared = dict(
        lender=lender,
        url=url,
        state_rule=n.parse_state_rule(row["Eligible States"]),
        min_revenue=revenue,
        revenue_rule_text=revenue_note if revenue is None else None,
        loan_size=n.parse_amount(row["Loan sizes"]),
        interest_rates=rates,
        min_interest_rate=n.parse_min_rate(rates),
        loan_terms=n.clean(row["Loan terms"]) or None,
    )

    credit_by_product = n.parse_product_values(row["Min credit score"])
    years_by_product = n.parse_product_values(row["Min years in business"])
    keys = list(dict.fromkeys([*credit_by_product, *years_by_product]))
    if keys:
        offers = []
        covered: set[str] = set()
        for key in keys:
            matching = [p for p in products if key in p.lower()]
            covered.update(matching)
            offers.append((key, matching))
        uncovered = [p for p in products if p not in covered]
        limitations = (
            [f"{lender} also lists {', '.join(uncovered)}, with no published requirements for them."]
            if uncovered
            else []
        )
        return [
            LoanOffer(
                id=f"L-{_slug(lender)}-{_slug(key)}",
                product_label=", ".join(matching) or key,
                products=matching or [key],
                product_level=True,
                min_credit_score=int(credit_by_product[key]) if key in credit_by_product else None,
                credit_note=None,
                credit_flexible=False,
                min_years=years_by_product.get(key),
                limitations=limitations,
                **shared,
            )
            for key, matching in offers
        ]

    credit, credit_note = n.parse_leading_number(row["Min credit score"])
    years, _ = n.parse_leading_number(row["Min years in business"])
    return [
        LoanOffer(
            id=f"L-{_slug(lender)}",
            product_label="All listed products",
            products=products,
            product_level=False,
            min_credit_score=int(credit) if credit is not None else None,
            credit_note=credit_note,
            credit_flexible=bool(credit_note and "exception" in credit_note.lower()),
            min_years=years,
            limitations=[LENDER_LEVEL_NOTE] if len(products) > 1 else [],
            **shared,
        )
    ]


def load_loans(path: Path) -> tuple[list[LoanOffer], LoadReport]:
    report = LoadReport(file=path.name)
    offers: list[LoanOffer] = []
    for number, row in enumerate(_read(path, _LOAN_COLUMNS), start=2):
        report.rows += 1
        try:
            offers.extend(build_loan_offers(row))
        except ValueError as error:
            report.skip(number, str(error))
    report.loaded = len(offers)
    return offers, report
