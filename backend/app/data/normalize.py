"""Turn raw CSV cell text into domain values. Pure functions, no file access."""

from __future__ import annotations

import re
from datetime import date, datetime

from app.data import mappings
from app.domain.models import Amount, DeadlineKind, LocationScope, NumericRange, StateRule, TriState

_INVISIBLE = dict.fromkeys(map(ord, "​‌‍﻿"), None)
_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")
_DOLLARS = re.compile(r"\$\s?(\d[\d,]*(?:\.\d+)?)\s*([kKmM])?(?![\w])")
_LOCATION_SPLIT = re.compile(r",(?![^(]*\))")
_STATE_TOKEN = re.compile(r"^([A-Z]{2})(?:\s*\((.+)\))?$")


def clean(value: str | None) -> str:
    """Trim and remove invisible characters left by spreadsheet exports."""
    text = (value or "").translate(_INVISIBLE).replace(" ", " ").replace("\xa0", " ")
    return text.strip()


def clean_long_text(value: str | None) -> str:
    """`clean`, plus drop the leading apostrophe spreadsheets add to cells starting with '-'."""
    text = clean(value)
    return text[1:].lstrip() if text.startswith("'") else text


def split_list(value: str | None, separator: str) -> list[str]:
    return [part for part in (clean(p) for p in clean(value).split(separator)) if part]


def _to_number(text: str) -> float:
    return float(text.replace(",", ""))


def parse_band(value: str | None) -> NumericRange | None:
    """Parse "$10,000 - $49,999", "420000", "720 or above", "500 -549" into a band."""
    text = clean(value).lower()
    numbers = [_to_number(n) for n in _NUMBER.findall(text)]
    if not numbers:
        return None
    if "or above" in text or "more than" in text:
        return NumericRange(min=numbers[0])
    if len(numbers) >= 2:
        low, high = sorted(numbers[:2])
        return NumericRange(min=low, max=high)
    return NumericRange(min=numbers[0], max=numbers[0])


def parse_time_in_business(value: str | None) -> NumericRange | None:
    band = mappings.TIME_IN_BUSINESS.get(clean(value).lower())
    return NumericRange(min=band[0], max=band[1]) if band else None


def parse_flag(value: str | None) -> TriState:
    text = clean(value).lower()
    if text == "eligible":
        return TriState.YES
    if text == "not eligible":
        return TriState.NO
    return TriState.UNKNOWN


def state_code(value: str | None) -> str | None:
    """Accept a full state name or a two-letter code."""
    text = clean(value)
    if text.upper() in mappings.STATE_NAMES:
        return text.upper()
    return mappings.STATE_CODES.get(text.title()) or mappings.STATE_CODES.get(text)


def normalize_city(value: str | None) -> str:
    text = re.sub(r"\s+", " ", clean(value))
    return mappings.CITY_ALIASES.get(text.lower(), text.title() if text.isupper() or text.islower() else text)


def locality_keys(state: str, city: str) -> list[str]:
    """The business's own city plus every metro area that contains it."""
    own = city.lower()
    keys = {own}
    for (metro_state, metro), members in mappings.METRO_MEMBERS.items():
        if metro_state == state and own in members:
            keys.add(metro)
    return sorted(keys)


def parse_grant_locations(value: str | None) -> list[LocationScope]:
    scopes: list[LocationScope] = []
    for token in (clean(t) for t in _LOCATION_SPLIT.split(clean(value))):
        if not token or token in mappings.IGNORED_LOCATION_TOKENS:
            continue
        if token == "Global":
            scopes.append(LocationScope(kind="global", raw=token))
        elif token == "US":
            scopes.append(LocationScope(kind="national", raw=token))
        elif token.startswith("US ("):
            scopes.append(LocationScope(kind="select_states", raw=token))
        elif token in mappings.REGION_STATES:
            scopes.extend(LocationScope(kind="state", state=s, raw=token) for s in mappings.REGION_STATES[token])
        elif (m := _STATE_TOKEN.match(token)) and m.group(1) in mappings.STATE_NAMES:
            if m.group(2):
                scopes.append(LocationScope(kind="city", state=m.group(1), city=clean(m.group(2)), raw=token))
            else:
                scopes.append(LocationScope(kind="state", state=m.group(1), raw=token))
        elif token in mappings.STATE_CODES:
            scopes.append(LocationScope(kind="state", state=mappings.STATE_CODES[token], raw=token))
        else:
            scopes.append(LocationScope(kind="foreign", raw=token))
    return scopes


def map_business_industries(value: str | None) -> tuple[list[str], list[str]]:
    """Return (canonical industries, labels with no mapping)."""
    canonical: list[str] = []
    unmapped: list[str] = []
    for label in split_list(value, ","):
        if label in mappings.BUSINESS_INDUSTRY_MAP:
            for industry in mappings.BUSINESS_INDUSTRY_MAP[label]:
                if industry not in canonical:
                    canonical.append(industry)
        else:
            unmapped.append(label)
    return canonical, unmapped


def split_grant_industries(value: str | None) -> tuple[list[str], list[str], bool]:
    """Return (canonical industries, applicant tags, open to all industries)."""
    industries: list[str] = []
    tags: list[str] = []
    is_all = False
    for token in split_list(value, ","):
        if token == "All":
            is_all = True
        elif token in mappings.GRANT_ATTRIBUTE_TAGS:
            tags.append(token)
        else:
            industries.append(mappings.GRANT_INDUSTRY_ALIASES.get(token, token))
    return industries, tags, is_all


def parse_amount(value: str | None) -> Amount:
    """Parse "$5,000", "up to $50,000", "$1k - $15k", "10000". Unparseable text stays raw-only."""
    raw = clean(value)
    if not raw:
        return Amount()
    numbers = [
        _to_number(n) * {"k": 1_000, "m": 1_000_000}.get(suffix.lower(), 1)
        for n, suffix in _DOLLARS.findall(raw)
    ]
    if not numbers and re.fullmatch(r"\d[\d,]*(?:\.\d+)?", raw):
        numbers = [_to_number(raw)]
    if not numbers:
        return Amount(raw=raw)
    if raw.lower().startswith("up to"):
        return Amount(max=max(numbers), raw=raw)
    return Amount(min=min(numbers), max=max(numbers), raw=raw)


def is_non_cash(amount_text: str | None) -> bool:
    text = clean(amount_text).lower()
    return "no cash" in text or text.startswith("free") or text.startswith("in-kind")


def parse_date(value: str | None) -> date | None:
    text = clean(value)
    if not text:
        return None
    try:
        return datetime.strptime(text, "%m/%d/%Y").date()
    except ValueError:
        return None


def deadline_kind(deadline: date | None, type_label: str | None) -> DeadlineKind:
    label = clean(type_label).lower()
    if "rolling" in label:
        return "rolling"
    if re.search(r"annual|quarter|month|yearly|per year|cycles", label):
        return "recurring"
    return "fixed" if deadline else "none"


def parse_state_rule(value: str | None) -> StateRule:
    """Parse "All", "All except ND, NV", or "Eligible: Alabama, Arizona, ... and Wyoming"."""
    raw = clean(value)
    lowered = raw.lower()
    if lowered == "all":
        return StateRule(mode="all", raw=raw)
    listed = re.sub(r"^(all except|eligible:)", "", raw, flags=re.IGNORECASE)
    names = [clean(re.sub(r"^and\s+", "", clean(part))) for part in listed.split(",")]
    states = [code for code in (state_code(name) for name in names) if code]
    mode = "all_except" if lowered.startswith("all except") else "only"
    return StateRule(mode=mode, states=states, raw=raw)


def parse_product_values(value: str | None) -> dict[str, float]:
    """Parse "575 (MCA); 650 (term)" into {"mca": 575, "term": 650}. Empty when not per-product."""
    parts = split_list(value, ";")
    if len(parts) < 2:
        return {}
    values: dict[str, float] = {}
    for part in parts:
        m = re.match(r"^(\d+(?:\.\d+)?)\s*\(([^)]+)\)$", part)
        if not m:
            return {}
        values[m.group(2).strip().lower()] = float(m.group(1))
    return values


def parse_leading_number(value: str | None) -> tuple[float | None, str | None]:
    """Split "$250,000.00" / "620 (some exceptions)" into (number, note). No leading number -> (None, text)."""
    text = clean(value)
    if not text or text in {"-", "None"}:
        return None, None
    m = re.match(r"^\$?(\d[\d,]*(?:\.\d+)?)\s*(?:\((.+)\))?$", text)
    if not m:
        return None, text
    return _to_number(m.group(1)), (m.group(2) or None)


def parse_min_rate(value: str | None) -> float | None:
    """Lowest published fixed rate. Variable, index-linked rates return None."""
    text = clean(value)
    if not text or "prime" in text.lower():
        return None
    m = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
    return float(m.group(1)) if m else None
