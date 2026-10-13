"""Match result types. Eligibility and relevance are separate objects computed independently."""

from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Literal

from pydantic import BaseModel

from app.domain.models import Amount, NumericRange


class Outcome(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    NEEDS_VERIFICATION = "needs_verification"
    NOT_APPLICABLE = "not_applicable"


class EligibilityStatus(str, Enum):
    LIKELY_ELIGIBLE = "likely_eligible"
    NEEDS_VERIFICATION = "needs_verification"
    INELIGIBLE = "ineligible"


class RuleResult(BaseModel):
    rule: str
    label: str
    outcome: Outcome
    reason: str
    required: str | None = None
    actual: str | None = None


class Eligibility(BaseModel):
    status: EligibilityStatus
    summary: str
    checks: list[RuleResult]
    warnings: list[str]


class ScoreComponent(BaseModel):
    name: str
    label: str
    points: int
    max: int
    reason: str


class Relevance(BaseModel):
    score: int  # 0-100
    summary: str
    components: list[ScoreComponent]


class DeadlineInfo(BaseModel):
    date: date | None
    kind: str
    label: str


class Match(BaseModel):
    opportunity_id: str
    kind: Literal["grant", "loan"]
    category: str
    listing_status: Literal["open", "coming_soon"]
    name: str
    provider: str | None
    amount: Amount
    deadline: DeadlineInfo | None
    url: str
    eligibility: Eligibility
    relevance: Relevance
    details: dict[str, str]  # display-only facts: rates, terms, fee, location
    limitations: list[str]
    description: str | None
    criteria_text: str | None


def compare_minimum(actual: NumericRange | None, minimum: float) -> Outcome:
    """Compare a business's band to a minimum. A band straddling the minimum is borderline."""
    if actual is None:
        return Outcome.NEEDS_VERIFICATION
    if actual.min >= minimum:
        return Outcome.PASS
    if actual.max is not None and actual.max < minimum:
        return Outcome.FAIL
    return Outcome.NEEDS_VERIFICATION


def build_eligibility(checks: list[RuleResult], warnings: list[str]) -> Eligibility:
    """Any fail -> ineligible; else any unresolved check -> needs verification; else likely eligible."""
    failed = [c for c in checks if c.outcome is Outcome.FAIL]
    unresolved = [c for c in checks if c.outcome is Outcome.NEEDS_VERIFICATION]
    passed = [c for c in checks if c.outcome is Outcome.PASS]
    def names(checks: list[RuleResult]) -> str:
        return "; ".join(dict.fromkeys(c.label.lower() for c in checks))

    passed_part = f"Passed: {names(passed)}. " if passed else ""
    if failed:
        status = EligibilityStatus.INELIGIBLE
        summary = f"Does not meet: {names(failed)}."
    elif unresolved:
        status = EligibilityStatus.NEEDS_VERIFICATION
        summary = f"{passed_part}To verify: {names(unresolved)}."
    else:
        status = EligibilityStatus.LIKELY_ELIGIBLE
        summary = f"{passed_part}Nothing left to verify from the listing. This is not a guarantee of eligibility."
    return Eligibility(status=status, summary=summary, checks=checks, warnings=warnings)
