"""Scoring weights and thresholds. Every number used for ranking lives here."""

# --- Grant relevance: component maximums must total 100 ---------------------
GRANT_WEIGHTS = {
    "industry_fit": 35,
    "audience_fit": 20,
    "local_fit": 20,
    "timing_fit": 15,
    "use_of_funds_fit": 10,
}

# Points awarded within each grant component.
INDUSTRY_POINTS = {"match": 35, "all_industries": 15, "none_listed": 10, "cannot_compare": 5, "mismatch": 0}
AUDIENCE_POINTS = {"targeted_match": 20, "general": 8, "unknown": 4, "mismatch": 0}
LOCAL_POINTS = {"city": 20, "state": 15, "multi_state": 12, "national": 10, "select_states": 8, "global": 6, "none": 0}
TIMING_POINTS = {
    "rolling_urgent": 15,
    "window_ideal": 15,
    "rolling": 12,
    "far_out": 10,
    "closing_soon": 8,
    "unknown": 6,
    "coming_soon": 5,
}
USE_POINTS = {"match": 10, "general": 5, "unknown": 3}

MULTI_STATE_THRESHOLD = 5  # more state scopes than this counts as a regional programme
CLOSING_SOON_DAYS = 14
IDEAL_WINDOW_DAYS = 60

# --- Loan relevance: component maximums must total 100 ----------------------
LOAN_WEIGHTS = {
    "use_of_funds_fit": 40,
    "qualification_headroom": 25,
    "cost": 20,
    "timing_fit": 15,
}

USE_UNKNOWN_SHARE = 0.375  # share of the use-of-funds weight when uses are not on file
HEADROOM_SHARE = {"clear": 1.0, "borderline": 0.5, "unknown": 0.33, "below": 0.0}
COST_POINTS = {"zero": 20, "low": 16, "mid": 12, "high": 8, "unpublished": 8}
COST_LOW_RATE = 7.0
COST_MID_RATE = 10.0
LOAN_TIMING_POINTS = {"fast_product": 15, "within_month": 12, "neutral": 8}

URGENT_TIMINGS = {"Within a week", "Within 2 weeks"}
SOON_TIMINGS = URGENT_TIMINGS | {"Within a month"}

# Loan product keyword -> funding uses it serves (business `funding_uses` vocabulary).
PRODUCT_USES = {
    "commercial real estate": {"Commercial real estate", "Expansion and renovation"},
    "truck": {"Vehicles"},
    "line of credit": {"Inventory", "Hiring and payroll", "Marketing and advertising"},
    "lines of credit": {"Inventory", "Hiring and payroll", "Marketing and advertising"},
    "mca": {"Inventory", "Hiring and payroll", "Marketing and advertising"},
    "purchase order": {"Inventory"},
    "sba 7(a)": {"Debt refinancing", "Equipment and machinery", "Expansion and renovation", "Commercial real estate"},
    "term loan": {
        "Hiring and payroll",
        "Marketing and advertising",
        "Inventory",
        "Equipment and machinery",
        "Expansion and renovation",
        "Business launch",
        "Debt refinancing",
    },
}
FAST_PRODUCT_KEYWORDS = ("mca", "line of credit", "lines of credit")

# Grant tag / support type -> funding uses it suggests.
GRANT_USE_SIGNALS = {
    "Brick-and-Mortar": {"Expansion and renovation", "Commercial real estate", "Equipment and machinery"},
    "Reimbursement": {"Expansion and renovation", "Equipment and machinery", "Commercial real estate"},
    "Startup": {"Business launch"},
}

STARTUP_MAX_YEARS = 2  # a business counts as a startup when its whole band is under this
