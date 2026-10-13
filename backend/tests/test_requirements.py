import pytest

from app.data.requirements import extract_requirements


def kinds(text: str, description: str = "") -> list[tuple[str, list[str]]]:
    return [(r.kind, r.groups) for r in extract_requirements(text, description)]


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Michigan-based for-profit business, at least 51% woman-owned.", [("founder", ["woman"])]),
        ("Be founded or co-founded and led by a woman", [("founder", ["woman"])]),
        ("You have a Black-owned business", [("founder", ["black"])]),
        ("Be at least 51% Hispanic owned business", [("founder", ["bipoc"])]),
        ("Must be a veteran-owned small business.", [("founder", ["veteran"])]),
        ("Must be a minority- or woman-owned business.", [("founder", ["woman", "bipoc"])]),
    ],
)
def test_clear_ownership_requirements(text, expected):
    assert kinds(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "Women entrepreneurs are encouraged to apply.",
        "Priority is given to minority-owned businesses.",
        "Open to small businesses, including women-owned and veteran-owned firms.",
        "Optional self-identification is offered for businesses at least 51% owned by women.",
        "Awards are $750, rising to $1,000 for businesses that are at least 51% veteran-owned.",
        "Our mission is to champion women in business.",
        "Open to all eligible entrepreneurs, regardless of background.",
    ],
)
def test_incidental_mentions_create_no_requirement(text):
    assert extract_requirements(text) == []


def test_requirement_keeps_its_source_sentence():
    [requirement] = extract_requirements("Based in Ohio. Must be at least 51% woman-owned. Apply online.")
    assert requirement.source == "Must be at least 51% woman-owned."


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Must be a for-profit business.", "for_profit"),
        ("For-profit small businesses only — nonprofits are not eligible.", "for_profit"),
        ("Must be a 501(c)3 serving the region.", "nonprofit"),
        ("NOT open to for-profit businesses - community organizations only.", "nonprofit"),
        ("Your business must have a physical storefront.", "brick_and_mortar"),
        ("Home-based businesses are not eligible at this time.", "brick_and_mortar"),
    ],
)
def test_entity_and_premises_requirements(text, expected):
    assert [r.kind for r in extract_requirements(text)] == [expected]


@pytest.mark.parametrize(
    "text",
    [
        "For-profit small businesses (and qualifying nonprofits) in eligible areas.",
        "Nonprofits or small businesses with a fiscal sponsor may apply.",
        "Applicants must be a nonprofit or an individual artist.",
    ],
)
def test_mixed_entity_wording_creates_no_requirement(text):
    assert extract_requirements(text) == []


def test_description_needs_rule_wording():
    assert extract_requirements("", "A fund created by a woman-owned bakery in Austin.") == []
    assert kinds("", "Eligible businesses must be at least 51% woman-owned.") == [("founder", ["woman"])]


def test_criteria_column_overrides_for_profit_wording_in_description():
    description = "The program funds eligible for-profit small businesses in the two cities."
    assert [r.kind for r in extract_requirements("", description)] == ["for_profit"]
    assert extract_requirements("For-profit small businesses (and qualifying nonprofits).", description) == []


def test_blank_text():
    assert extract_requirements("", "") == []
