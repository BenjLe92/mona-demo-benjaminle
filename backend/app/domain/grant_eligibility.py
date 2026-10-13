"""Hard requirements for a grant. Only location and clearly stated text requirements are checked."""

from __future__ import annotations

from datetime import date

from app.domain.models import BusinessProfile, Grant, Requirement, TriState
from app.domain.results import Eligibility, Outcome, RuleResult, build_eligibility

GROUP_LABELS = {"woman": "woman-owned", "black": "Black-owned", "bipoc": "minority/BIPOC-owned", "veteran": "veteran-owned"}
_GROUP_FIELDS = {"woman": "woman_owned", "black": "black_owned", "bipoc": "bipoc_owned", "veteran": "veteran_owned"}
_STATE_WORDS = {TriState.YES: "yes", TriState.NO: "no", TriState.UNKNOWN: "not on file"}

UNCHECKED_CRITERIA_WARNING = (
    "Only location and clearly stated ownership or entity requirements were checked. "
    "Read the full criteria before applying."
)


def is_expired(grant: Grant, as_of: date) -> bool:
    """A fixed deadline in the past. Rolling and recurring programmes are never treated as expired."""
    return grant.deadline_kind == "fixed" and grant.deadline is not None and grant.deadline < as_of


def check_location(business: BusinessProfile, grant: Grant) -> RuleResult:
    place = f"{business.city}, {business.state}"
    base = dict(rule="location", label="Location", required=grant.location_label or "not listed", actual=place)
    scopes = grant.locations
    if not scopes:
        return RuleResult(**base, outcome=Outcome.NEEDS_VERIFICATION, reason="No location is listed for this opportunity.")
    if any(s.kind in ("national", "global") for s in scopes):
        return RuleResult(**base, outcome=Outcome.PASS, reason="Open to businesses anywhere in the United States.")
    if any(s.kind == "state" and s.state == business.state for s in scopes):
        return RuleResult(**base, outcome=Outcome.PASS, reason=f"Open to businesses in {business.state_name}.")
    same_state_cities = [s for s in scopes if s.kind == "city" and s.state == business.state]
    for scope in same_state_cities:
        if scope.city and scope.city.lower() in business.locality_keys:
            return RuleResult(**base, outcome=Outcome.PASS, reason=f"Open to businesses in {scope.city}, {scope.state}.")
    if any(s.kind == "select_states" for s in scopes):
        return RuleResult(
            **base,
            outcome=Outcome.NEEDS_VERIFICATION,
            reason=f"Available in selected states only; check whether {business.state_name} is included.",
        )
    if same_state_cities:
        cities = ", ".join(sorted({s.city for s in same_state_cities if s.city}))
        return RuleResult(
            **base,
            outcome=Outcome.FAIL,
            reason=f"Limited to {cities} in {business.state_name}; your business is in {business.city}.",
        )
    return RuleResult(**base, outcome=Outcome.FAIL, reason=f"Not available in {business.state_name} ({grant.location_label}).")


def _quote(requirement: Requirement) -> str:
    return f' Stated as: "{requirement.source}"'


def check_founder_requirement(business: BusinessProfile, requirement: Requirement) -> RuleResult:
    states = {group: getattr(business, _GROUP_FIELDS[group]) for group in requirement.groups}
    wanted = " or ".join(GROUP_LABELS[g] for g in requirement.groups)
    actual = ", ".join(f"{GROUP_LABELS[g]}: {_STATE_WORDS[s]}" for g, s in states.items())
    base = dict(rule="founder_requirement", label=f"Ownership: {wanted}", required=wanted, actual=actual)
    if TriState.YES in states.values():
        met = next(GROUP_LABELS[g] for g, s in states.items() if s is TriState.YES)
        return RuleResult(**base, outcome=Outcome.PASS, reason=f"Requires a {wanted} business; yours is {met}." + _quote(requirement))
    if all(s is TriState.NO for s in states.values()):
        return RuleResult(**base, outcome=Outcome.FAIL, reason=f"Requires a {wanted} business; your profile says it is not." + _quote(requirement))
    return RuleResult(
        **base,
        outcome=Outcome.NEEDS_VERIFICATION,
        reason=f"Requires a {wanted} business; this is not on file for your profile." + _quote(requirement),
    )


def check_entity_requirement(business: BusinessProfile, requirement: Requirement) -> RuleResult:
    wants_nonprofit = requirement.kind == "nonprofit"
    wanted = "nonprofit organization" if wants_nonprofit else "for-profit business"
    actual = {TriState.YES: "nonprofit", TriState.NO: "for-profit", TriState.UNKNOWN: "not on file"}[business.nonprofit]
    base = dict(rule="entity_requirement", label=f"Entity type: {wanted}", required=wanted, actual=actual)
    if business.nonprofit is TriState.UNKNOWN:
        return RuleResult(**base, outcome=Outcome.NEEDS_VERIFICATION, reason=f"Requires a {wanted}; your entity type is not on file." + _quote(requirement))
    matches = (business.nonprofit is TriState.YES) == wants_nonprofit
    if matches:
        return RuleResult(**base, outcome=Outcome.PASS, reason=f"Requires a {wanted}; yours is one." + _quote(requirement))
    return RuleResult(**base, outcome=Outcome.FAIL, reason=f"Requires a {wanted}; your business is {actual}." + _quote(requirement))


def check_brick_and_mortar(business: BusinessProfile, requirement: Requirement) -> RuleResult:
    base = dict(
        rule="brick_and_mortar",
        label="Physical location",
        required="brick-and-mortar location",
        actual=_STATE_WORDS[business.brick_and_mortar],
    )
    if business.brick_and_mortar is TriState.YES:
        return RuleResult(**base, outcome=Outcome.PASS, reason="Requires a physical location; you have one." + _quote(requirement))
    if business.brick_and_mortar is TriState.NO:
        return RuleResult(**base, outcome=Outcome.FAIL, reason="Requires a physical location; your profile says you do not have one." + _quote(requirement))
    return RuleResult(**base, outcome=Outcome.NEEDS_VERIFICATION, reason="Requires a physical location; this is not on file for your profile." + _quote(requirement))


def check_nonprofit_listing(business: BusinessProfile, grant: Grant) -> RuleResult | None:
    """A grant listed only under "Nonprofit" is flagged for verification, never failed outright.

    The index tags the audience but states no rule, so a for-profit business is asked to confirm.
    """
    listed_for_nonprofits = "Nonprofit" in grant.tags and not grant.industries and not grant.all_industries
    stated = any(r.kind in ("nonprofit", "for_profit") for r in grant.requirements)
    if not listed_for_nonprofits or stated or business.nonprofit is TriState.YES:
        return None
    return RuleResult(
        rule="nonprofit_listing",
        label="Listed for nonprofits",
        outcome=Outcome.NEEDS_VERIFICATION,
        required="nonprofit (listing category)",
        actual="for-profit" if business.nonprofit is TriState.NO else "not on file",
        reason="This opportunity is listed for nonprofits. Confirm whether for-profit businesses can apply.",
    )


_REQUIREMENT_CHECKS = {
    "founder": check_founder_requirement,
    "nonprofit": check_entity_requirement,
    "for_profit": check_entity_requirement,
    "brick_and_mortar": check_brick_and_mortar,
}


def classify_grant(business: BusinessProfile, grant: Grant, as_of: date) -> Eligibility:
    checks = [check_location(business, grant)]
    checks += [_REQUIREMENT_CHECKS[r.kind](business, r) for r in grant.requirements]
    listing = check_nonprofit_listing(business, grant)
    if listing:
        checks.append(listing)

    warnings = [UNCHECKED_CRITERIA_WARNING]
    if grant.listing_status == "coming_soon":
        warnings.append("Applications are not open yet.")
    if grant.deadline and grant.deadline < as_of:
        warnings.append(
            f"The listed date ({grant.deadline:%b %d, %Y}) has passed and the programme is "
            f"{grant.deadline_type_label or grant.deadline_kind}; confirm the next application window."
        )
    return build_eligibility(checks, warnings)
