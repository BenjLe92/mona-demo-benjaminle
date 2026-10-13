"""Relevance scoring. Independent of eligibility: nothing here reads an eligibility result."""

from __future__ import annotations

from datetime import date

from app.domain import config as cfg
from app.domain.models import BusinessProfile, Grant, LoanOffer, TriState
from app.domain.results import Outcome, Relevance, ScoreComponent, compare_minimum


def _relevance(components: list[ScoreComponent]) -> Relevance:
    score = sum(c.points for c in components)
    strongest = sorted(components, key=lambda c: (-c.points / c.max, c.name))[:2]
    summary = " ".join(c.reason for c in strongest if c.points > 0) or "Few signals link this to your profile."
    return Relevance(score=score, summary=summary, components=components)


# --- Grants -----------------------------------------------------------------


def score_industry(business: BusinessProfile, grant: Grant) -> ScoreComponent:
    points = cfg.INDUSTRY_POINTS
    overlap = [i for i in grant.industries if i in business.industries]
    if overlap:
        key, reason = "match", f"Targets your industry ({', '.join(overlap)})."
    elif grant.all_industries:
        key, reason = "all_industries", "Open to all industries."
    elif not grant.industries:
        key, reason = "none_listed", "No industry focus is listed."
    elif not business.industries:
        key, reason = "cannot_compare", "Your industry is missing or has no equivalent in the grant index."
    else:
        key, reason = "mismatch", f"Aimed at other industries ({', '.join(grant.industries[:3])})."
    return ScoreComponent(name="industry_fit", label="Industry fit", points=points[key], max=cfg.GRANT_WEIGHTS["industry_fit"], reason=reason)


def _is_startup(business: BusinessProfile) -> TriState:
    years = business.years_in_business
    if years is None:
        return TriState.UNKNOWN
    return TriState.YES if years.max is not None and years.max < cfg.STARTUP_MAX_YEARS else TriState.NO


def score_audience(business: BusinessProfile, grant: Grant) -> ScoreComponent:
    """Does the grant target a group or attribute this business has?"""
    targets: dict[str, TriState] = {}
    group_fields = {"woman": business.woman_owned, "black": business.black_owned, "bipoc": business.bipoc_owned, "veteran": business.veteran_owned}
    group_names = {"woman": "woman-owned businesses", "black": "Black-owned businesses", "bipoc": "minority-owned businesses", "veteran": "veteran-owned businesses"}
    for requirement in grant.requirements:
        if requirement.kind == "founder":
            for group in requirement.groups:
                targets[group_names[group]] = group_fields[group]
        elif requirement.kind == "nonprofit":
            targets["nonprofits"] = business.nonprofit
        elif requirement.kind == "brick_and_mortar":
            targets["brick-and-mortar businesses"] = business.brick_and_mortar
    if "Nonprofit" in grant.tags:
        targets["nonprofits"] = business.nonprofit
    if "Brick-and-Mortar" in grant.tags:
        targets["brick-and-mortar businesses"] = business.brick_and_mortar
    if "Startup" in grant.tags:
        targets["startups"] = _is_startup(business)

    points = cfg.AUDIENCE_POINTS
    matched = [name for name, state in targets.items() if state is TriState.YES]
    if matched:
        key, reason = "targeted_match", f"Designed for {', '.join(matched)}, which matches your profile."
    elif not targets:
        key, reason = "general", "Not aimed at a specific type of business."
    elif any(state is TriState.UNKNOWN for state in targets.values()):
        key, reason = "unknown", f"Aimed at {', '.join(targets)}; your profile does not say whether that applies."
    else:
        key, reason = "mismatch", f"Aimed at {', '.join(targets)}, which does not match your profile."
    return ScoreComponent(name="audience_fit", label="Audience fit", points=points[key], max=cfg.GRANT_WEIGHTS["audience_fit"], reason=reason)


def score_local(business: BusinessProfile, grant: Grant) -> ScoreComponent:
    scopes = grant.locations
    state_scopes = {s.state for s in scopes if s.kind == "state"}
    if any(s.kind == "city" and s.state == business.state and (s.city or "").lower() in business.locality_keys for s in scopes):
        key, reason = "city", f"Local to {business.city}; fewer businesses can apply."
    elif business.state in state_scopes and len(state_scopes) > cfg.MULTI_STATE_THRESHOLD:
        key, reason = "multi_state", f"Regional programme that covers {business.state_name}."
    elif business.state in state_scopes:
        key, reason = "state", f"Specific to {business.state_name}."
    elif any(s.kind == "national" for s in scopes):
        key, reason = "national", "Nationwide programme."
    elif any(s.kind == "select_states" for s in scopes):
        key, reason = "select_states", "Available in selected states."
    elif any(s.kind == "global" for s in scopes):
        key, reason = "global", "Global programme with a wide applicant pool."
    else:
        key, reason = "none", "Not focused on your area."
    return ScoreComponent(name="local_fit", label="Local fit", points=cfg.LOCAL_POINTS[key], max=cfg.GRANT_WEIGHTS["local_fit"], reason=reason)


def score_grant_timing(business: BusinessProfile, grant: Grant, as_of: date) -> ScoreComponent:
    days = (grant.deadline - as_of).days if grant.deadline else None
    if grant.listing_status == "coming_soon":
        key, reason = "coming_soon", "Not open for applications yet."
    elif grant.deadline_kind == "rolling":
        if business.funding_timing in cfg.SOON_TIMINGS:
            key, reason = "rolling_urgent", f"Rolling applications suit your timeline ({business.funding_timing.lower()})."
        else:
            key, reason = "rolling", "Rolling applications; apply any time."
    elif days is None or days < 0:
        key, reason = "unknown", "No current deadline is listed."
    elif days < cfg.CLOSING_SOON_DAYS:
        key, reason = "closing_soon", f"Closes in {days} day{'s' if days != 1 else ''}; little time to apply."
    elif days <= cfg.IDEAL_WINDOW_DAYS:
        key, reason = "window_ideal", f"Closes in {days} days; enough time to prepare an application."
    else:
        key, reason = "far_out", f"Closes in {days} days."
    return ScoreComponent(name="timing_fit", label="Timing", points=cfg.TIMING_POINTS[key], max=cfg.GRANT_WEIGHTS["timing_fit"], reason=reason)


def score_grant_use(business: BusinessProfile, grant: Grant) -> ScoreComponent:
    signals = [*grant.tags, *grant.support_types]
    matched = sorted({use for s in signals for use in cfg.GRANT_USE_SIGNALS.get(s, ()) if use in business.funding_uses})
    if not business.funding_uses:
        key, reason = "unknown", "Your intended use of funds is not on file."
    elif matched:
        key, reason = "match", f"Suits your planned use of funds ({', '.join(matched).lower()})."
    else:
        key, reason = "general", "No specific use of funds is indicated."
    return ScoreComponent(name="use_of_funds_fit", label="Use of funds", points=cfg.USE_POINTS[key], max=cfg.GRANT_WEIGHTS["use_of_funds_fit"], reason=reason)


def rank_grant(business: BusinessProfile, grant: Grant, as_of: date) -> Relevance:
    return _relevance(
        [
            score_industry(business, grant),
            score_audience(business, grant),
            score_local(business, grant),
            score_grant_timing(business, grant, as_of),
            score_grant_use(business, grant),
        ]
    )


# --- Loans ------------------------------------------------------------------


def score_loan_use(business: BusinessProfile, offer: LoanOffer) -> ScoreComponent:
    weight = cfg.LOAN_WEIGHTS["use_of_funds_fit"]
    if not business.funding_uses:
        return ScoreComponent(name="use_of_funds_fit", label="Use of funds", points=round(weight * cfg.USE_UNKNOWN_SHARE), max=weight, reason="Your intended use of funds is not on file.")
    products = " ".join(offer.products).lower()
    served = set().union(*(uses for keyword, uses in cfg.PRODUCT_USES.items() if keyword in products))
    covered = [use for use in business.funding_uses if use in served]
    points = round(weight * len(covered) / len(business.funding_uses))
    if covered:
        reason = f"Products cover {len(covered)} of your {len(business.funding_uses)} planned uses ({', '.join(covered).lower()})."
    else:
        reason = "Listed products do not clearly cover your planned uses."
    return ScoreComponent(name="use_of_funds_fit", label="Use of funds", points=points, max=weight, reason=reason)


def score_headroom(business: BusinessProfile, offer: LoanOffer) -> ScoreComponent:
    """How comfortably the business clears each published numeric minimum."""
    weight = cfg.LOAN_WEIGHTS["qualification_headroom"]
    minimums = [
        ("credit score", business.credit_score, offer.min_credit_score),
        ("revenue", business.revenue, offer.min_revenue),
        ("time in business", business.years_in_business, offer.min_years),
    ]
    shares: list[float] = []
    notes: list[str] = []
    for name, actual, minimum in minimums:
        if minimum is None or minimum <= 0:
            shares.append(cfg.HEADROOM_SHARE["clear"])
            continue
        outcome = compare_minimum(actual, minimum)
        if actual is None:
            shares.append(cfg.HEADROOM_SHARE["unknown"])
            notes.append(f"{name} not on file")
        elif outcome is Outcome.PASS:
            shares.append(cfg.HEADROOM_SHARE["clear"])
        elif outcome is Outcome.FAIL:
            shares.append(cfg.HEADROOM_SHARE["below"])
            notes.append(f"{name} below the minimum")
        else:
            shares.append(cfg.HEADROOM_SHARE["borderline"])
            notes.append(f"{name} close to the minimum")
    points = round(weight * sum(shares) / len(shares))
    reason = "Comfortably above the published minimums." if not notes else "Published minimums: " + "; ".join(notes) + "."
    return ScoreComponent(name="qualification_headroom", label="Qualification headroom", points=points, max=weight, reason=reason)


def score_cost(offer: LoanOffer) -> ScoreComponent:
    rate = offer.min_interest_rate
    if rate is None:
        key, reason = "unpublished", "No fixed interest rate is published."
    elif rate == 0:
        key, reason = "zero", "0% interest."
    elif rate <= cfg.COST_LOW_RATE:
        key, reason = "low", f"Rates start at {rate:g}%."
    elif rate <= cfg.COST_MID_RATE:
        key, reason = "mid", f"Rates start at {rate:g}%."
    else:
        key, reason = "high", f"Rates start at {rate:g}%."
    return ScoreComponent(name="cost", label="Cost", points=cfg.COST_POINTS[key], max=cfg.LOAN_WEIGHTS["cost"], reason=reason)


def score_loan_timing(business: BusinessProfile, offer: LoanOffer) -> ScoreComponent:
    products = " ".join(offer.products).lower()
    fast = any(keyword in products for keyword in cfg.FAST_PRODUCT_KEYWORDS)
    if business.funding_timing in cfg.URGENT_TIMINGS and fast:
        key, reason = "fast_product", f"Includes credit lines or advances, which typically fund faster; you need funds {business.funding_timing.lower()}."
    elif business.funding_timing == "Within a month":
        key, reason = "within_month", "Your one-month timeline is workable for most loan products."
    else:
        key, reason = "neutral", "Funding speed is not published for this lender."
    return ScoreComponent(name="timing_fit", label="Timing", points=cfg.LOAN_TIMING_POINTS[key], max=cfg.LOAN_WEIGHTS["timing_fit"], reason=reason)


def rank_loan(business: BusinessProfile, offer: LoanOffer) -> Relevance:
    return _relevance(
        [
            score_loan_use(business, offer),
            score_headroom(business, offer),
            score_cost(offer),
            score_loan_timing(business, offer),
        ]
    )
