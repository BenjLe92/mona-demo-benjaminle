"""Explicit lookup tables used by the normalizers. Plain data, no logic."""

STATE_CODES = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR", "California": "CA",
    "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE", "District of Columbia": "DC",
    "Florida": "FL", "Georgia": "GA", "Hawaii": "HI", "Idaho": "ID", "Illinois": "IL",
    "Indiana": "IN", "Iowa": "IA", "Kansas": "KS", "Kentucky": "KY", "Louisiana": "LA",
    "Maine": "ME", "Maryland": "MD", "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN",
    "Mississippi": "MS", "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV",
    "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY",
    "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK", "Oregon": "OR",
    "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC", "South Dakota": "SD",
    "Tennessee": "TN", "Texas": "TX", "Utah": "UT", "Vermont": "VT", "Virginia": "VA",
    "Washington": "WA", "West Virginia": "WV", "Wisconsin": "WI", "Wyoming": "WY",
    "Puerto Rico": "PR",
}
STATE_NAMES = {code: name for name, code in STATE_CODES.items()}

# Business city spellings that need more than trimming and title-casing.
CITY_ALIASES = {
    "la": "Los Angeles",
    "washington, dc": "Washington",
    "washington dc": "Washington",
}

# (state, grant city label lower-cased) -> business cities (lower-cased) inside that area.
METRO_MEMBERS = {
    ("NY", "nyc"): {
        "new york", "new york city", "nyc", "manhattan", "brooklyn", "bronx", "queens",
        "staten island", "astoria", "howard beach", "maspeth", "rockaway park",
    },
    ("NY", "queens"): {"queens", "astoria", "howard beach", "maspeth", "rockaway park"},
    ("CA", "los angeles"): {"los angeles", "woodland hills"},
}

# Grant location tokens that stand for several states.
REGION_STATES = {"DMV": ["DC", "MD", "VA"]}

# Grant location tokens that carry no geographic restriction.
IGNORED_LOCATION_TOKENS = {"Hybrid"}

# Business industry label -> canonical industries (the grant index vocabulary).
# An empty list means the label is recognised but has no grant-side equivalent.
BUSINESS_INDUSTRY_MAP = {
    "Agriculture": ["Agriculture"],
    "Apparel & Accessories": ["Apparel & Accessories"],
    "Arts": ["Visual & Fine Arts", "Arts & Crafts", "Creative Economy"],
    "Beauty & Personal Care": ["Beauty & Personal Care"],
    "Cleaning Services": ["Home Services"],
    "Communications & Media": ["Film & Media", "Journalism", "Marketing & Brand Management"],
    "Construction": ["Construction"],
    "Education": ["Education & Child Care"],
    "Entertainment": ["Film & Media", "Music", "Creative Economy"],
    "Food & Beverage": ["Food & Beverage"],
    "Health & Wellness": ["Health & Wellness"],
    "Home Repair & Maintenance": ["Home Services", "Construction"],
    "Licensed DayCare": ["Education & Child Care"],
    "Manufacturing": ["Manufacturing"],
    "Nonprofit": [],  # an entity type, carried by the nonprofit flag instead
    "Professional Services": ["Consulting"],
    "Retail": ["Retail"],
    "Social Impact": ["Social Impact"],
    "Sports": ["Sports"],
    "Technology": ["Technology"],
    "Transportation & Automotive Services": [],
    "Wholesaler": [],
}

# Grant `Industry` tokens that are spelled differently from the canonical label.
GRANT_INDUSTRY_ALIASES = {"Health / Wellness": "Health & Wellness"}

# Grant `Industry` tokens that describe the applicant, not an industry.
GRANT_ATTRIBUTE_TAGS = {
    "Nonprofit", "Brick-and-Mortar", "Startup", "Economic Empowerment",
    "Community-Based Organization", "NGO",
}

# Time-in-business labels -> years band. "1 year" covers 1 up to (not including) 2.
TIME_IN_BUSINESS = {
    "i have not yet started my business": (0.0, 0.0),
    "less than 1 year": (0.0, 0.99),
    "1 year": (1.0, 1.99),
    "2-3 years": (2.0, 3.99),
    "4-5 years": (4.0, 5.99),
    "more than 5 years": (5.0, None),
}

ENTITY_TYPES = {
    "Limited Liability Company (LLC)": "for_profit",
    "Sole Proprietor": "for_profit",
    "C Corporation": "for_profit",
    "S Corporation": "for_profit",
    "Partnership": "for_profit",
    "Nonprofit Corporation": "nonprofit",
}

# Grant `Type of Support` tokens that put a row in scope.
IN_SCOPE_SUPPORT = {"Grant", "Reimbursement", "Award", "Awards", "Pitch Competition"}
