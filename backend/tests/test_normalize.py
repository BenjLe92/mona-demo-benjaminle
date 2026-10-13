from datetime import date

import pytest

from app.data import normalize as n
from app.domain.models import TriState


@pytest.mark.parametrize(
    "raw, low, high",
    [
        ("$10,000 - $49,999", 10_000, 49_999),
        ("$50,000 to $99,999", 50_000, 99_999),
        ("420000", 420_000, 420_000),
        ("720 or above", 720, None),
        ("500 -549", 500, 549),
        ("600 - 649", 600, 649),
        ("724", 724, 724),
        ("2 to 5 employees", 2, 5),
        ("1 employee", 1, 1),
    ],
)
def test_parse_band(raw, low, high):
    band = n.parse_band(raw)
    assert (band.min, band.max) == (low, high)


@pytest.mark.parametrize("raw", ["", "   ", None, "unknown"])
def test_parse_band_missing_is_none(raw):
    assert n.parse_band(raw) is None


@pytest.mark.parametrize(
    "raw, low, high",
    [
        ("I have not yet started my business", 0, 0),
        ("Less than 1 year", 0, 0.99),
        ("1 year", 1, 1.99),
        ("2-3 years", 2, 3.99),
        ("More than 5 years", 5, None),
    ],
)
def test_parse_time_in_business(raw, low, high):
    band = n.parse_time_in_business(raw)
    assert (band.min, band.max) == (low, high)


def test_parse_time_in_business_blank_is_none():
    assert n.parse_time_in_business("") is None


@pytest.mark.parametrize(
    "raw, expected",
    [("Eligible", TriState.YES), ("Not eligible", TriState.NO), ("", TriState.UNKNOWN), ("maybe", TriState.UNKNOWN)],
)
def test_parse_flag_blank_is_unknown_not_no(raw, expected):
    assert n.parse_flag(raw) is expected


@pytest.mark.parametrize(
    "raw, expected",
    [("Illinois", "IL"), ("District of Columbia", "DC"), ("new york", "NY"), ("ND", "ND"), ("Atlantis", None)],
)
def test_state_code(raw, expected):
    assert n.state_code(raw) == expected


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("DETROIT", "Detroit"),
        ("smyrna", "Smyrna"),
        ("LA", "Los Angeles"),
        ("Washington, DC", "Washington"),
        ("Washington DC", "Washington"),
        ("McHenry", "McHenry"),
        ("  St. Clair Shores ", "St. Clair Shores"),
    ],
)
def test_normalize_city(raw, expected):
    assert n.normalize_city(raw) == expected


def test_locality_keys_adds_metro_for_borough():
    assert n.locality_keys("NY", "Brooklyn") == ["brooklyn", "nyc"]
    assert n.locality_keys("NY", "Astoria") == ["astoria", "nyc", "queens"]
    assert n.locality_keys("IL", "Naperville") == ["naperville"]


def test_parse_grant_locations():
    scopes = n.parse_grant_locations("US,IL (Chicago),NY,Canada,DMV,Hybrid,US (select states)")
    assert [(s.kind, s.state, s.city) for s in scopes] == [
        ("national", None, None),
        ("city", "IL", "Chicago"),
        ("state", "NY", None),
        ("foreign", None, None),
        ("state", "DC", None),
        ("state", "MD", None),
        ("state", "VA", None),
        ("select_states", None, None),
    ]
    assert n.parse_grant_locations("") == []


def test_map_business_industries():
    assert n.map_business_industries("Health & Wellness, Retail") == (["Health & Wellness", "Retail"], [])
    assert n.map_business_industries("Education") == (["Education & Child Care"], [])
    assert n.map_business_industries("Transportation & Automotive Services") == ([], [])
    assert n.map_business_industries("Underwater Basketry") == ([], ["Underwater Basketry"])


def test_split_grant_industries_separates_tags_from_industries():
    industries, tags, is_all = n.split_grant_industries("Health / Wellness,Nonprofit,Brick-and-Mortar")
    assert industries == ["Health & Wellness"]
    assert tags == ["Nonprofit", "Brick-and-Mortar"]
    assert is_all is False
    assert n.split_grant_industries("All,Startup") == ([], ["Startup"], True)


@pytest.mark.parametrize(
    "raw, low, high",
    [
        ("$5,000", 5000, 5000),
        ("up to $50,000", None, 50_000),
        ("$500 - $10,000", 500, 10_000),
        ("10000", 10_000, 10_000),
        ("$1k - $15k", 1000, 15_000),
        ("$25k - $5M", 25_000, 5_000_000),
        ("$50K - $300K", 50_000, 300_000),
        ("varies", None, None),
        ("£150,000", None, None),
    ],
)
def test_parse_amount(raw, low, high):
    amount = n.parse_amount(raw)
    assert (amount.min, amount.max, amount.raw) == (low, high, raw)


def test_parse_amount_blank():
    assert n.parse_amount("").raw is None


@pytest.mark.parametrize(
    "raw, expected",
    [("free advising (no cash award)", True), ("Free advising", True), ("$5,000", False), ("", False)],
)
def test_is_non_cash(raw, expected):
    assert n.is_non_cash(raw) is expected


def test_parse_date():
    assert n.parse_date("10/4/2026") == date(2026, 10, 4)
    assert n.parse_date("") is None
    assert n.parse_date("soon") is None


@pytest.mark.parametrize(
    "deadline, label, expected",
    [
        (date(2026, 11, 1), "", "fixed"),
        (date(2026, 11, 1), "Rolling", "rolling"),
        (None, "rolling", "rolling"),
        (date(2026, 11, 1), "annually", "recurring"),
        (date(2026, 11, 1), "twice yearly (spring and fall)", "recurring"),
        (None, "", "none"),
    ],
)
def test_deadline_kind(deadline, label, expected):
    assert n.deadline_kind(deadline, label) == expected


def test_parse_state_rule():
    assert n.parse_state_rule("All").mode == "all"
    rule = n.parse_state_rule("All except DC, MT, ND, SD, TN, VT")
    assert (rule.mode, rule.states) == ("all_except", ["DC", "MT", "ND", "SD", "TN", "VT"])
    rule = n.parse_state_rule("Eligible: Alabama, New Mexico, and Wyoming")
    assert (rule.mode, rule.states) == ("only", ["AL", "NM", "WY"])


def test_parse_product_values():
    assert n.parse_product_values("575 (MCA); 650 (term)") == {"mca": 575, "term": 650}
    assert n.parse_product_values("1 (MCA); 1.5 (term)") == {"mca": 1, "term": 1.5}
    assert n.parse_product_values("640 (ideally 680)") == {}
    assert n.parse_product_values("") == {}


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("$250,000.00", (250_000, None)),
        ("$0 (startups welcomed)", (0, "startups welcomed")),
        ("620 (some exceptions)", (620, "some exceptions")),
        ("None", (None, None)),
        ("-", (None, None)),
        ("", (None, None)),
        ("YoY revenue growth", (None, "YoY revenue growth")),
    ],
)
def test_parse_leading_number(raw, expected):
    assert n.parse_leading_number(raw) == expected


@pytest.mark.parametrize(
    "raw, expected",
    [("0% (fixed)", 0), ("9.99% to 28.24%", 9.99), ("WSJ Prime + 2-6% (variable)", None), ("", None)],
)
def test_parse_min_rate(raw, expected):
    assert n.parse_min_rate(raw) == expected


def test_clean_long_text_strips_export_artifacts():
    assert n.clean_long_text("'- 30 years in business​ ") == "- 30 years in business"
