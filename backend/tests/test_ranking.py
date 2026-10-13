from datetime import date, timedelta

import pytest

from app.domain import config as cfg
from app.domain import ranking as rk
from app.domain.grant_eligibility import classify_grant
from app.domain.matcher import match_business, match_grant
from app.domain.models import NumericRange, Requirement, TriState
from tests.conftest import AS_OF, make_business, make_grant, make_offer


def test_weights_total_100_and_bound_every_point_table():
    assert sum(cfg.GRANT_WEIGHTS.values()) == 100
    assert sum(cfg.LOAN_WEIGHTS.values()) == 100
    assert max(cfg.INDUSTRY_POINTS.values()) == cfg.GRANT_WEIGHTS["industry_fit"]
    assert max(cfg.AUDIENCE_POINTS.values()) == cfg.GRANT_WEIGHTS["audience_fit"]
    assert max(cfg.LOCAL_POINTS.values()) == cfg.GRANT_WEIGHTS["local_fit"]
    assert max(cfg.TIMING_POINTS.values()) == cfg.GRANT_WEIGHTS["timing_fit"]
    assert max(cfg.USE_POINTS.values()) == cfg.GRANT_WEIGHTS["use_of_funds_fit"]
    assert max(cfg.COST_POINTS.values()) == cfg.LOAN_WEIGHTS["cost"]
    assert max(cfg.LOAN_TIMING_POINTS.values()) == cfg.LOAN_WEIGHTS["timing_fit"]


@pytest.mark.parametrize(
    "grant_kwargs, business_kwargs, key",
    [
        (dict(industries=["Food & Beverage"], all_industries=False), {}, "match"),
        (dict(all_industries=True), {}, "all_industries"),
        (dict(industries=[], all_industries=False), {}, "none_listed"),
        (dict(industries=["Technology"], all_industries=False), dict(industries=[]), "cannot_compare"),
        (dict(industries=["Technology"], all_industries=False), {}, "mismatch"),
    ],
)
def test_industry_score(grant_kwargs, business_kwargs, key):
    component = rk.score_industry(make_business(**business_kwargs), make_grant(**grant_kwargs))
    assert component.points == cfg.INDUSTRY_POINTS[key]
    assert component.reason


def test_audience_score():
    woman_grant = make_grant(requirements=[Requirement(kind="founder", groups=["woman"], source="x")])
    points = cfg.AUDIENCE_POINTS
    assert rk.score_audience(make_business(woman_owned=TriState.YES), woman_grant).points == points["targeted_match"]
    assert rk.score_audience(make_business(woman_owned=TriState.UNKNOWN), woman_grant).points == points["unknown"]
    assert rk.score_audience(make_business(woman_owned=TriState.NO), woman_grant).points == points["mismatch"]
    assert rk.score_audience(make_business(), make_grant()).points == points["general"]


def test_startup_tag_matches_young_business_only():
    startup_grant = make_grant(tags=["Startup"])
    young = make_business(years_in_business=NumericRange(min=0, max=0.99))
    assert rk.score_audience(young, startup_grant).points == cfg.AUDIENCE_POINTS["targeted_match"]
    assert rk.score_audience(make_business(), startup_grant).points == cfg.AUDIENCE_POINTS["mismatch"]


@pytest.mark.parametrize(
    "location, key",
    [
        ("IL (Chicago)", "city"),
        ("IL", "state"),
        ("IL,IN,WI,MI,OH,MN", "multi_state"),
        ("US", "national"),
        ("US (select states)", "select_states"),
        ("Global", "global"),
        ("NY", "none"),
    ],
)
def test_local_score(location, key):
    assert rk.score_local(make_business(), make_grant(location=location)).points == cfg.LOCAL_POINTS[key]


@pytest.mark.parametrize(
    "grant_kwargs, timing, key",
    [
        (dict(deadline=None, deadline_type="rolling"), "Within a week", "rolling_urgent"),
        (dict(deadline=None, deadline_type="rolling"), "Unsure, just browsing rates", "rolling"),
        (dict(deadline=None, deadline_type="rolling"), None, "rolling"),
        (dict(deadline=AS_OF + timedelta(days=5)), None, "closing_soon"),
        (dict(deadline=AS_OF + timedelta(days=30)), None, "window_ideal"),
        (dict(deadline=AS_OF + timedelta(days=120)), None, "far_out"),
        (dict(deadline=None), None, "unknown"),
        (dict(deadline=AS_OF - timedelta(days=30), deadline_type="annually"), None, "unknown"),
        (dict(listing_status="coming_soon"), None, "coming_soon"),
    ],
)
def test_grant_timing_score(grant_kwargs, timing, key):
    component = rk.score_grant_timing(make_business(funding_timing=timing), make_grant(**grant_kwargs), AS_OF)
    assert component.points == cfg.TIMING_POINTS[key]


def test_grant_use_score():
    renovating = make_business(funding_uses=["Expansion and renovation"])
    assert rk.score_grant_use(renovating, make_grant(tags=["Brick-and-Mortar"])).points == cfg.USE_POINTS["match"]
    assert rk.score_grant_use(renovating, make_grant()).points == cfg.USE_POINTS["general"]
    assert rk.score_grant_use(make_business(funding_uses=[]), make_grant()).points == cfg.USE_POINTS["unknown"]


def test_grant_score_is_sum_of_components_and_within_range():
    relevance = rk.rank_grant(make_business(), make_grant(), AS_OF)
    assert relevance.score == sum(c.points for c in relevance.components)
    assert 0 <= relevance.score <= 100
    assert all(0 <= c.points <= c.max for c in relevance.components)
    assert relevance.summary


def test_loan_use_score_is_proportional():
    weight = cfg.LOAN_WEIGHTS["use_of_funds_fit"]
    offer = make_offer(products=["truck financing"])
    assert rk.score_loan_use(make_business(funding_uses=["Vehicles"]), offer).points == weight
    assert rk.score_loan_use(make_business(funding_uses=["Vehicles", "Inventory"]), offer).points == weight // 2
    assert rk.score_loan_use(make_business(funding_uses=["Inventory"]), offer).points == 0
    assert rk.score_loan_use(make_business(funding_uses=[]), offer).points == round(weight * cfg.USE_UNKNOWN_SHARE)


def test_headroom_score():
    weight = cfg.LOAN_WEIGHTS["qualification_headroom"]
    assert rk.score_headroom(make_business(), make_offer()).points == weight
    borderline = make_business(credit_score=NumericRange(min=600, max=649))
    assert rk.score_headroom(borderline, make_offer()).points < weight
    no_minimums = make_offer(min_credit_score=None, min_revenue=0, min_years=None)
    assert rk.score_headroom(make_business(credit_score=None), no_minimums).points == weight


@pytest.mark.parametrize("rate, key", [(0, "zero"), (6, "low"), (9.99, "mid"), (15, "high"), (None, "unpublished")])
def test_cost_score(rate, key):
    assert rk.score_cost(make_offer(min_interest_rate=rate)).points == cfg.COST_POINTS[key]


def test_loan_timing_score():
    credit_line = make_offer(products=["Term loans", "lines of credit"])
    points = cfg.LOAN_TIMING_POINTS
    assert rk.score_loan_timing(make_business(funding_timing="Within a week"), credit_line).points == points["fast_product"]
    assert rk.score_loan_timing(make_business(funding_timing="Within a week"), make_offer()).points == points["neutral"]
    assert rk.score_loan_timing(make_business(funding_timing="Within a month"), make_offer()).points == points["within_month"]
    assert rk.score_loan_timing(make_business(funding_timing=None), make_offer()).points == points["neutral"]


def test_relevance_is_independent_of_eligibility():
    """An out-of-state grant is ineligible, yet its industry and audience scores are unchanged."""
    business = make_business()
    local = make_grant(industries=["Food & Beverage"], all_industries=False, location="IL")
    remote = make_grant(industries=["Food & Beverage"], all_industries=False, location="NY")
    assert classify_grant(business, remote, AS_OF).status.value == "ineligible"
    for name in ("industry_fit", "audience_fit", "timing_fit", "use_of_funds_fit"):
        local_points = next(c.points for c in rk.rank_grant(business, local, AS_OF).components if c.name == name)
        remote_points = next(c.points for c in rk.rank_grant(business, remote, AS_OF).components if c.name == name)
        assert local_points == remote_points


def test_matches_sorted_by_status_then_score_then_deadline_then_name():
    business = make_business(woman_owned=TriState.UNKNOWN)
    grants = [
        make_grant(id="G-1", name="Zeta", location="NY", industries=["Food & Beverage"], all_industries=False),
        make_grant(id="G-2", name="Beta"),
        make_grant(id="G-3", name="Alpha"),
        make_grant(id="G-4", name="Early", deadline=date(2026, 11, 1)),
        make_grant(id="G-5", name="Top", industries=["Food & Beverage"], all_industries=False),
        make_grant(id="G-6", name="Verify", requirements=[Requirement(kind="founder", groups=["woman"], source="x")],
                   industries=["Food & Beverage"], all_industries=False),
    ]
    ordered = [m.opportunity_id for m in match_business(business, grants, [], AS_OF)]
    assert ordered == ["G-5", "G-4", "G-3", "G-2", "G-6", "G-1"]
    assert ordered == [m.opportunity_id for m in match_business(business, list(reversed(grants)), [], AS_OF)]


def test_match_business_drops_expired_and_keeps_loans():
    grants = [make_grant(id="G-1", deadline=date(2026, 10, 1)), make_grant(id="G-2")]
    ids = [m.opportunity_id for m in match_business(make_business(), grants, [make_offer()], AS_OF)]
    assert "G-1" not in ids and {"G-2", "L-test"} <= set(ids)


def test_match_carries_both_explanations():
    match = match_grant(make_business(), make_grant(), AS_OF)
    assert match.eligibility.checks and match.eligibility.summary
    assert match.relevance.components and match.relevance.summary
    assert match.deadline.label == "Nov 15, 2026"
