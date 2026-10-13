import logging

import pytest

from app.data import loaders
from app.domain.models import TriState
from tests.conftest import FIXTURES


@pytest.fixture(scope="module")
def businesses():
    return loaders.load_businesses(FIXTURES / loaders.BUSINESS_FILE)


@pytest.fixture(scope="module")
def grants():
    return loaders.load_grants(FIXTURES / loaders.GRANT_FILE)


@pytest.fixture(scope="module")
def loans():
    return loaders.load_loans(FIXTURES / loaders.LOAN_FILE)


def test_businesses_loaded_and_bad_rows_reported(businesses):
    profiles, report = businesses
    assert [p.profile_id for p in profiles] == ["MONA-0001", "MONA-0002", "MONA-0004"]
    assert report.rows == 5 and report.loaded == 3
    assert report.skipped == [
        "row 4: unrecognised state 'Atlantis'",
        "row 5: duplicate profile_id MONA-0001",
    ]


def test_skipped_rows_are_logged(caplog):
    with caplog.at_level(logging.WARNING):
        loaders.load_businesses(FIXTURES / loaders.BUSINESS_FILE)
    assert "row 4 skipped" in caplog.text


def test_business_normalization(businesses):
    first = businesses[0][0]
    assert (first.city, first.state, first.state_name) == ("Chicago", "IL", "Illinois")
    assert first.industries == ["Food & Beverage"]
    assert (first.revenue.min, first.revenue.max) == (100_000, 249_999)
    assert first.funding_uses == ["Inventory", "Hiring and payroll"]
    assert first.woman_owned is TriState.YES and first.nonprofit is TriState.NO
    assert first.unknown_fields == []


def test_sparse_business_keeps_unknowns_explicit(businesses):
    sparse = businesses[0][1]
    assert sparse.locality_keys == ["brooklyn", "nyc"]
    assert sparse.revenue is None and sparse.credit_score is None and sparse.years_in_business is None
    assert sparse.woman_owned is TriState.UNKNOWN
    assert sparse.business_type is None  # "Retail" is not a legal entity type
    assert sparse.nonprofit is TriState.UNKNOWN
    assert {"Annual revenue", "Credit score", "Woman-owned", "Business type"} <= set(sparse.unknown_fields)


def test_blank_bipoc_flag_is_not_inferred_from_black_owned(businesses):
    sparse = businesses[0][1]
    assert sparse.black_owned is TriState.YES
    assert sparse.bipoc_owned is TriState.UNKNOWN
    assert "BIPOC-owned" in sparse.unknown_fields


def test_blank_nonprofit_flag_is_not_inferred_from_entity_type(businesses):
    profiles = businesses[0]
    nonprofit_corporation = profiles[2]
    assert nonprofit_corporation.business_type == "Nonprofit Corporation"
    assert nonprofit_corporation.nonprofit is TriState.UNKNOWN
    assert "Nonprofit status" in nonprofit_corporation.unknown_fields

    llc = profiles[0]
    assert llc.business_type == "Limited Liability Company (LLC)"
    assert llc.nonprofit is TriState.NO  # recorded explicitly in the row, not derived


def test_llc_with_blank_nonprofit_flag_stays_unknown():
    row = dict.fromkeys(loaders._BUSINESS_COLUMNS, "")
    row.update(profile_id="MONA-X", city="Austin", state="Texas", business_type="Limited Liability Company (LLC)")
    assert loaders.build_business(row).nonprofit is TriState.UNKNOWN
    row["nonprofit_eligibility"] = "Eligible"  # the real data has an LLC flagged as a nonprofit
    assert loaders.build_business(row).nonprofit is TriState.YES


def test_unmapped_industry_kept(businesses):
    nonprofit = businesses[0][2]
    assert nonprofit.industries == ["Education & Child Care"]
    assert nonprofit.unmapped_industries == ["Underwater Basketry"]
    assert (nonprofit.revenue.min, nonprofit.credit_score.max) == (420_000, None)


def test_grant_scope_and_status_filters(grants):
    loaded, report = grants
    assert [g.name for g in loaded] == [
        "National Food Grant", "Chicago Women Grant", "Expired Grant", "Upcoming Pitch", "Nonprofit Fund",
        "Revenue Cap Grant", "Silent Grant",
    ]
    assert report.excluded == {"closed": 1, "support type out of scope": 2, "no cash award": 1}
    assert report.skipped == ["row 7: unparseable deadline 'sometime soon'", "row 11: missing name or link"]


def test_grant_normalization(grants):
    by_name = {g.name: g for g in grants[0]}
    chicago = by_name["Chicago Women Grant"]
    assert chicago.id == "G-0004"  # ids follow file position, including excluded rows
    assert chicago.deadline_kind == "rolling"
    assert [(s.kind, s.state, s.city) for s in chicago.locations] == [("city", "IL", "Chicago")]
    assert chicago.all_industries and chicago.tags == ["Brick-and-Mortar"]
    assert chicago.eligibility_text == "- Must be at least 51% woman-owned."
    assert [(r.kind, r.groups) for r in chicago.requirements] == [("founder", ["woman"])]
    assert chicago.application_fee == "$20"

    pitch = by_name["Upcoming Pitch"]
    assert (pitch.listing_status, pitch.category) == ("coming_soon", "pitch_competition")
    assert by_name["Nonprofit Fund"].deadline_kind == "recurring"
    assert [r.kind for r in by_name["Nonprofit Fund"].requirements] == ["nonprofit"]
    assert by_name["National Food Grant"].amount.max == 10_000


def test_grant_unchecked_criteria_are_loaded(grants):
    by_name = {g.name: g for g in grants[0]}
    assert [c.topic for c in by_name["Revenue Cap Grant"].unchecked_criteria] == ["revenue", "employees", "tenure"]
    assert by_name["Revenue Cap Grant"].criteria_say_who_qualifies is True
    assert by_name["Silent Grant"].criteria_say_who_qualifies is False
    assert by_name["National Food Grant"].unchecked_criteria == []
    assert by_name["Chicago Women Grant"].unchecked_criteria == []  # its only criterion is evaluated


def test_loans_expand_to_product_level_offers(loans):
    offers, report = loans
    assert [o.id for o in offers] == ["L-kiva", "L-biz2credit-mca", "L-biz2credit-term", "L-lendistry", "L-honeycomb"]
    assert report.skipped == ["row 6: missing lender or referral link"]

    by_id = {o.id: o for o in offers}
    mca, term = by_id["L-biz2credit-mca"], by_id["L-biz2credit-term"]
    assert (mca.min_credit_score, mca.min_years, mca.products) == (575, 1, ["MCAs"])
    assert (term.min_credit_score, term.min_years, term.products) == (650, 1.5, ["Term loans"])
    assert mca.product_level and mca.min_revenue == 250_000
    assert "lines of credit" in mca.limitations[0]


def test_loan_field_parsing(loans):
    by_id = {o.id: o for o in loans[0]}
    kiva = by_id["L-kiva"]
    assert (kiva.min_credit_score, kiva.min_revenue, kiva.min_years, kiva.min_interest_rate) == (None, 0, 0, 0)
    assert (kiva.state_rule.mode, kiva.state_rule.states) == ("all_except", ["ND", "NV"])
    assert (kiva.loan_size.min, kiva.loan_size.max) == (1000, 15_000)

    lendistry = by_id["L-lendistry"]
    assert lendistry.min_revenue is None
    assert lendistry.revenue_rule_text == "YoY revenue/cash flow growth trend for two years"
    assert (lendistry.credit_note, lendistry.credit_flexible) == ("ideally 680", False)
    assert lendistry.min_interest_rate is None
    assert lendistry.limitations == [loaders.LENDER_LEVEL_NOTE]

    honeycomb = by_id["L-honeycomb"]
    assert (honeycomb.min_credit_score, honeycomb.credit_flexible) == (620, True)
    assert honeycomb.min_revenue is None and honeycomb.revenue_rule_text is None


def test_missing_column_fails_loudly(tmp_path):
    path = tmp_path / "loans.csv"
    path.write_text("Lender,Products\nKiva,Term loans\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing columns"):
        loaders.load_loans(path)
