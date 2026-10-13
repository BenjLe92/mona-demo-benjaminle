"""HTTP layer: parameter handling and response shaping only. Matching lives in `app.domain`."""

from __future__ import annotations

import os
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from app.data.repository import Repository
from app.domain.matcher import match_business
from app.domain.models import BusinessProfile
from app.domain.results import EligibilityStatus, Match

router = APIRouter(prefix="/api")

AS_OF_ENV = "MONA_AS_OF_DATE"


def get_repository(request: Request) -> Repository:
    return request.app.state.repository


def get_as_of() -> date:
    """Today, unless MONA_AS_OF_DATE (YYYY-MM-DD) pins the date for tests and demos."""
    pinned = os.environ.get(AS_OF_ENV)
    return date.fromisoformat(pinned) if pinned else date.today()


class FileReport(BaseModel):
    file: str
    rows: int
    loaded: int
    skipped: list[str]
    excluded: dict[str, int]


class Meta(BaseModel):
    as_of: date
    businesses: int
    grants: int
    loan_offers: int
    files: list[FileReport]


class BusinessSummary(BaseModel):
    profile_id: str
    city: str
    state: str
    industry_label: str | None
    business_type: str | None
    unknown_count: int


class StatusCounts(BaseModel):
    likely_eligible: int = 0
    needs_verification: int = 0
    ineligible: int = 0


class MatchResponse(BaseModel):
    profile_id: str
    as_of: date
    counts: dict[str, StatusCounts]  # keyed by "grant", "loan", "coming_soon"
    total: int  # results matching the filters, before paging
    results: list[Match]


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/meta", response_model=Meta)
def meta(repo: Repository = Depends(get_repository), as_of: date = Depends(get_as_of)) -> Meta:
    return Meta(
        as_of=as_of,
        businesses=len(repo.businesses),
        grants=len(repo.grants),
        loan_offers=len(repo.offers),
        files=[FileReport(**vars(report)) for report in repo.reports],
    )


@router.get("/businesses", response_model=list[BusinessSummary])
def list_businesses(
    search: str = "",
    state: str | None = None,
    repo: Repository = Depends(get_repository),
) -> list[BusinessSummary]:
    needle = search.strip().lower()
    summaries = []
    for b in repo.businesses.values():
        haystack = f"{b.profile_id} {b.city} {b.state} {b.state_name} {b.industry_label or ''}".lower()
        if needle and needle not in haystack:
            continue
        if state and b.state != state.upper():
            continue
        summaries.append(
            BusinessSummary(
                profile_id=b.profile_id,
                city=b.city,
                state=b.state,
                industry_label=b.industry_label,
                business_type=b.business_type,
                unknown_count=len(b.unknown_fields),
            )
        )
    return summaries


def _business(profile_id: str, repo: Repository) -> BusinessProfile:
    business = repo.businesses.get(profile_id.upper())
    if business is None:
        raise HTTPException(status_code=404, detail=f"No business profile {profile_id!r}.")
    return business


@router.get("/businesses/{profile_id}", response_model=BusinessProfile)
def get_business(profile_id: str, repo: Repository = Depends(get_repository)) -> BusinessProfile:
    return _business(profile_id, repo)


def _bucket(match: Match) -> str:
    return "coming_soon" if match.listing_status == "coming_soon" else match.kind


@router.get("/businesses/{profile_id}/matches", response_model=MatchResponse)
def get_matches(
    profile_id: str,
    kind: Literal["grant", "loan", "coming_soon"] | None = None,
    status: EligibilityStatus | None = None,
    include_ineligible: bool = False,
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    repo: Repository = Depends(get_repository),
    as_of: date = Depends(get_as_of),
) -> MatchResponse:
    """Ranked matches. `kind` selects open grants, loans, or grants that are not open yet."""
    business = _business(profile_id, repo)
    matches = match_business(business, repo.grants, repo.offers, as_of)

    counts = {bucket: StatusCounts() for bucket in ("grant", "loan", "coming_soon")}
    for match in matches:
        bucket_counts = counts[_bucket(match)]
        setattr(bucket_counts, match.eligibility.status.value, getattr(bucket_counts, match.eligibility.status.value) + 1)

    selected = [
        m
        for m in matches
        if (kind is None or _bucket(m) == kind)
        and (status is None or m.eligibility.status is status)
        and (include_ineligible or status is not None or m.eligibility.status is not EligibilityStatus.INELIGIBLE)
    ]
    return MatchResponse(
        profile_id=business.profile_id,
        as_of=as_of,
        counts=counts,
        total=len(selected),
        results=selected[offset : offset + limit],
    )
