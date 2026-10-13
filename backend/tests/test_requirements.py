import pytest

from app.data.requirements import extract_requirements


def parsed(text: str, description: str = "", name: str = "") -> list[tuple[str, list[str], bool]]:
    return [(r.kind, r.groups, r.strict) for r in extract_requirements(text, description, name)]


# --- Firm ownership requirements ---------------------------------------------


@pytest.mark.parametrize(
    "text, groups",
    [
        ("Michigan-based business, at least 51% woman-owned.", ["woman"]),
        ("Be founded or co-founded and led by a woman", ["woman"]),
        ("You have a Black-owned business", ["black"]),
        ("Be at least 51% Hispanic owned business", ["bipoc"]),
        ("Must be a veteran-owned small business.", ["veteran"]),
        ("Must be a minority- or woman-owned business.", ["woman", "bipoc"]),
        ("The business must have a woman founder or at least one active woman co-founder.", ["woman"]),
        ("U.S. military veteran serving as CEO, President or Business Owner", ["veteran"]),
        ("Female founders 22 years of age and older with businesses registered in the United States.", ["woman"]),
        ("Emerging Black designer / Black-owned fashion business", ["black"]),
        ("Applicants must be for-profit OR nonprofit Black businesses or entrepreneurs in Berkshire County.", ["black"]),
    ],
)
def test_firm_ownership_requirements(text, groups):
    assert parsed(text) == [("founder", groups, True)]


def test_requirement_keeps_its_source_clause():
    [requirement] = extract_requirements("Based in Ohio. Must be at least 51% woman-owned. Apply online.")
    assert requirement.source == "Must be at least 51% woman-owned."


# --- Ambiguous statements: flagged for verification, never a hard rule --------


@pytest.mark.parametrize(
    "text, groups",
    [
        ("All women and minority business owners are eligible.", ["woman", "bipoc"]),
        ("Grant allocation of up to $2,000 per veteran entrepreneur", ["veteran"]),
        ("Open to women entrepreneurs in Michigan.", ["woman"]),
        ("Must be woman-owned OR located in a designated corridor.", ["woman"]),
        ("Must be at least 51% owned by women, veterans, or people with disabilities.", ["woman", "veteran"]),
    ],
)
def test_ambiguous_ownership_statements_are_not_strict(text, groups):
    assert parsed(text) == [("founder", groups, False)]


def test_description_naming_who_the_grant_supports_is_ambiguous():
    description = "The grant was created to support women entrepreneurs seeking resources to grow."
    assert parsed("", description) == [("founder", ["woman"], False)]


def test_programme_name_alone_is_ambiguous():
    assert parsed("Residence must be in Duval County.", name="City Veteran Grant Program") == [("founder", ["veteran"], False)]
    assert extract_requirements("Residence must be in Duval County.", name="City Small Business Grant") == []


def test_firm_rule_outranks_hints_from_description_and_name():
    result = parsed(
        "The business must have a woman founder.",
        "An awards programme honoring 100 women founders across all stages.",
        "Women Founders Awards",
    )
    assert result == [("founder", ["woman"], True)]


# --- Preferences and incidental mentions create nothing -------------------------


@pytest.mark.parametrize(
    "text",
    [
        "Women entrepreneurs are encouraged to apply.",
        "Priority is given to minority-owned businesses.",
        "Open to small businesses, including women-owned and veteran-owned firms.",
        "Optional self-identification is offered for businesses at least 51% owned by women.",
        "Awards are $750, rising to $1,000 for businesses that are at least 51% veteran-owned.",
        "Plus a $2,500 booster for businesses 50%+ owned by minorities, women or veterans.",
        "Our mission is to champion women in business.",
        "Open to all eligible entrepreneurs, regardless of background.",
        "Formal nonprofit status is not required.",
        "Non-profit organizations that are revenue-generating are eligible for our grants.",
        "Supports groups historically excluded from funding, working with local nonprofits.",
    ],
)
def test_incidental_mentions_create_no_requirement(text):
    assert extract_requirements(text) == []


def test_organisation_names_are_not_ownership_requirements():
    text = (
        "Must be affiliated with one of the partner organizations: Southwest Detroit Business Association, "
        "Michigan Black Business Alliance, and Michigan Women Forward."
    )
    assert extract_requirements(text) == []


def test_funder_described_as_veteran_owned_is_not_a_requirement():
    description = "Microgrants for small businesses from Seated Together, LLC, a veteran-owned company in Florida."
    assert extract_requirements("", description) == []
    assert extract_requirements("", "A fund created by a woman-owned bakery in Austin.") == []


# --- Entity type: positive requirements ------------------------------------------


@pytest.mark.parametrize(
    "text, kind",
    [
        ("Must be a for-profit business.", "for_profit"),
        ("Be a registered for-profit entity", "for_profit"),
        ("For-profit businesses with an operating address within City of Sacramento limits.", "for_profit"),
        ("Direct application: https://example.org/apply - For-profit business operating in Texas;", "for_profit"),
        ("NONPROFITS ONLY. Apply through the portal.", "nonprofit"),
        ("Must be a 501(c)3 serving the region.", "nonprofit"),
        ("You must be a recognized 501(C)(3) nonprofit by the IRS", "nonprofit"),
        ("Be a small or mid-size non-profit with 50 employees or less.", "nonprofit"),
        ("501(c)(3) nonprofits focused on food systems and community health.", "nonprofit"),
    ],
)
def test_firm_entity_requirements(text, kind):
    assert parsed(text) == [(kind, [], True)]


# --- Entity type: explicit exclusions (negation) ---------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "For-profit businesses are ineligible.",
        "FOR-PROFIT BUSINESSES ARE NOT ELIGIBLE.",
        "INELIGIBLE: individuals, for-profit businesses, political entities.",
        "NOT open to for-profit businesses - community organizations only.",
        "For-profit companies are outside the stated applicant types.",
        "Not eligible: for-profit companies and individuals.",
    ],
)
def test_excluding_for_profits_never_becomes_a_for_profit_requirement(text):
    assert parsed(text) == [("nonprofit", [], True)]


@pytest.mark.parametrize(
    "text",
    [
        "National franchises and nonprofits ineligible.",
        "Nonprofits cannot apply",
        "Ineligible: nonprofits, national franchises, and food carts.",
        "Excluded: nonprofits, tech companies and others.",
        "Nonprofits, student projects, and arts festivals are not eligible, and previous grantees must wait two years.",
        "For-profit small businesses only — nonprofits are not eligible.",
        "For-profit small businesses; nonprofits not named as eligible.",
    ],
)
def test_excluding_nonprofits_never_becomes_a_nonprofit_requirement(text):
    assert parsed(text) == [("for_profit", [], True)]


def test_excluding_one_tax_class_says_nothing_about_nonprofits_in_general():
    assert extract_requirements("Organizations such as 501(c)(4)s and 501(c)(6)s are not eligible.") == []


# --- Entity type: both admitted, or ambiguous ------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "For-profit small businesses (and qualifying nonprofits) in eligible areas.",
        "Open to private for-profit or nonprofit business owners in the United States.",
        "Nonprofits or small businesses with a fiscal sponsor may apply.",
        "The partnering institution must be a qualified nonprofit institution of higher education.",
    ],
)
def test_wording_that_admits_both_entity_types_creates_no_requirement(text):
    assert extract_requirements(text) == []


@pytest.mark.parametrize(
    "text, kind",
    [
        ("Applicants must be a nonprofit or an individual artist.", "nonprofit"),
        ("Must be 501(c)(3) or fiscally sponsored.", "nonprofit"),
        ("Open to for-profit small businesses.", "for_profit"),
        ("Is a non-profit organization, OR", "nonprofit"),
    ],
)
def test_ambiguous_entity_statements_are_not_strict(text, kind):
    assert parsed(text) == [(kind, [], False)]


def test_firm_entity_rule_softens_when_the_listing_also_admits_the_other_type():
    text = "Nonprofits only as lead applicant — must be a U.S.-based 501(c)(3). FOR-PROFITS MAY PARTICIPATE IN COLLABORATIONS."
    assert parsed(text) == [("nonprofit", [], False)]


def test_implied_entity_rule_is_dropped_when_the_listing_admits_the_other_type():
    description = "The program funds eligible for-profit small businesses in the two cities."
    assert parsed("", description) == [("for_profit", [], False)]
    assert extract_requirements("For-profit small businesses (and qualifying nonprofits).", description) == []


# --- Several requirements in one clause ---------------------------------------------


def test_one_clause_can_carry_ownership_and_entity_requirements():
    assert parsed("Michigan-based for-profit business, at least 51% woman-owned.") == [
        ("founder", ["woman"], True),
        ("for_profit", [], True),
    ]


def test_independent_ownership_rules_are_all_kept():
    text = "Must be at least 51% woman-owned. Must also be a veteran-owned business."
    assert parsed(text) == [("founder", ["woman"], True), ("founder", ["veteran"], True)]


def test_ownership_entity_and_premises_together():
    text = "Must be a for-profit, woman-owned business. Your business must have a physical storefront."
    assert [kind for kind, _, _ in parsed(text)] == ["founder", "for_profit", "brick_and_mortar"]


# --- Premises and other basics --------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    ["Your business must have a physical storefront.", "Home-based businesses are not eligible at this time."],
)
def test_premises_requirements(text):
    assert parsed(text) == [("brick_and_mortar", [], True)]


def test_description_needs_rule_wording():
    assert parsed("", "Eligible businesses must be at least 51% woman-owned.") == [("founder", ["woman"], True)]


def test_blank_text():
    assert extract_requirements("", "", "") == []
